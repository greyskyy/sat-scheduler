"""Execute the pre-processor, provide stats on results."""
import argparse
import math
import czml3
import czml3.enums
import czml3.properties
import czml3.types
import datetime as dt
import itertools
import logging
import pandas as pd

from orekit.pyhelpers import absolutedate_to_datetime

from .core import PreprocessingResult, aois_from_results
from .runner import create_uows, run_units_of_work

from ..aoi.czml import aoi_czml
from ..configuration import get_config
from ..models.czml import platform_czml, sensor_czml
from ..utils.czml import write_czml

# patch cml3
czml3.types.TYPE_MAPPING[int] = "number"
czml3.types.TYPE_MAPPING[float] = "number"

SUBCOMMAND = "preprocess"
ALIASES = ["prep"]
LOGGER_NAME = "satscheduler"


def config_args(parser):
    """Add command line arguments to the provided parser.

    Args:
        parser (argparse.ArgumentParser): The parser to which arguments will be added.
    """
    parser.add_argument(
        "--multi-threading",
        action=argparse.BooleanOptionalAction,
        dest="threading",
        help="Run with multi-threading. Overrides the value set in the config.",
    )
    parser.add_argument(
        "--test",
        help="Run in test-mode.",
        action=argparse.BooleanOptionalAction,
        default=False,
    )

    parser.add_argument(
        "--console",
        help="Print output to the console.",
        action=argparse.BooleanOptionalAction,
        default=True,
    )

    parser.add_argument(
        "--prefix",
        dest="prefix",
        nargs="?",
        default="preproc",
        const="preproc",
        metavar="FILENAME",
        help="File path prefix for output files. If no file path specified, then `./preproc` will be used.",
    )

    parser.add_argument(
        "--aoi-czml",
        dest="aoi_czml",
        default=True,
        action=argparse.BooleanOptionalAction,
        help="Toggle the generation of a czml document with the AOIs.",
    )

    parser.add_argument(
        "--csv",
        dest="paoi_csv",
        default=True,
        action=argparse.BooleanOptionalAction,
        help="Toggle generation of access CSV file.",
    )


def populate_dataframes(
    results: list[PreprocessingResult],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Populate the result dataframes.

    Args:
        results (list[PreprocessingResult]): The list of results from the preprocessors.

    Returns:
        tuple[pd.DataFrame, pd.DataFrame]: The dataframes. The first data frame lists the AOIs processed, the
        second provides the access times.
    """
    logging.getLogger(__name__).debug("Populating dataframes.")
    paoi_df = pd.DataFrame(
        columns=[
            "aoi_id",
            "satellite",
            "sensor",
            "start",
            "stop",
            "duration",
        ]
    )

    aoi_df = pd.DataFrame(columns=["aoi_id", "satellite", "sensor", "area", "continent", "country"])

    aidx = 0
    pidx = 0
    for a in aois_from_results(results):
        aoi_df.loc[pidx] = [
            a.aoi.id,
            a.sat.id,
            a.sensor.id,
            a.aoi.area,
            a.aoi.continent,
            a.aoi.country,
        ]
        pidx += 1
        for ivl in a.intervals:
            paoi_df.loc[aidx] = [
                a.aoi.id,
                a.sat.id,
                a.sensor.id,
                absolutedate_to_datetime(ivl.start),
                absolutedate_to_datetime(ivl.stop),
                ivl.duration,
            ]
            aidx += 1

    if paoi_df.empty:
        paoi_df["duration_secs"] = []
    else:
        paoi_df["duration_secs"] = paoi_df["duration"].dt.total_seconds()

    return aoi_df, paoi_df


def execute(args=None) -> int:
    """Load the AOIs, generating a summary + map plot.

    Args:
        args (argparse.Namespace, optional): The command line arguments. Defaults to None.

    Returns:
        int: The return code to provide back to the OS.
    """
    logger = logging.getLogger(__name__)
    config = get_config()

    # Execute preprocessing
    logger.info("Starting preprocessor tool.")
    uows = create_uows(args, config=config)
    results: list[PreprocessingResult] = run_units_of_work(uows=uows, args=args, config=config)
    logger.info("Preprocessing complete.")

    # Populate dataframes
    aoi_df, paoi_df = populate_dataframes(results)
    logger.info(
        "Produced %d preprocessed aois",
        len(aoi_df.groupby(["aoi_id", "satellite", "sensor"])),
    )

    # Produce summary output
    total_aoi = len(aoi_df["aoi_id"].unique())
    proc_aoi = len(paoi_df["aoi_id"].unique())

    total_sum = paoi_df[["aoi_id", "duration"]].groupby(["aoi_id"]).sum()
    total_sum.rename(columns={"duration": "total access duration"}, inplace=True)

    if args.console:
        print(total_sum)

    logger.info("After processing, %d/%d aois have no access.", total_aoi - proc_aoi, total_aoi)

    # Write the aoi czml
    if args.aoi_czml:
        write_czml(
            fname=f"{args.prefix}_aois.czml",
            name="Aois",
            packets=[aoi_czml(aoi.aoi, config=config.aois) for aoi in aois_from_results(results)],
        )

    # Write the access csv
    if args.paoi_csv:
        paoi_df.to_csv(f"{args.prefix}_access.csv")

    # Write the satellite processing czml
    for r in results:
        unique_sensor_ids = {a.sensor.id for a in r.aois}

        sensors = filter(lambda s: s.id in unique_sensor_ids and s.has_fov, r.platform.model.sensors)

        sensor_packets = list(
            itertools.chain.from_iterable(
                [sensor_czml(platform=r.platform, sensor=s, show=r.interval) for s in sensors]
            )
        )

        write_czml(
            fname=f"{args.prefix}_sat_{r.sat.id}.czml",
            name=f"{r.sat.name} preprocessing aoi results",
            clock=czml3.types.IntervalValue(
                start=config.run.start,
                end=config.run.stop,
                value=czml3.properties.Clock(currentTime=config.run.start, multiplier=10),
            ),
            packets=[
                platform_czml(r.platform),
                *[
                    aoi_czml(aoi.aoi, config=config.aois, zones=True, show=True, fill_show=aoi.intervals)
                    for aoi in r.aois
                ],
                *sensor_packets,
            ],
        )

    return 0
