"""Pushbroom scheduler.

A pushbroom scheduler maintains a constant payload pointing without articulating 
during collection. It is the satellite motion which moves the payload across the
AOIs.
"""
import argparse
import logging

from .core import Platform, Platforms
from .reporting import init_access_report
from .score import score_aois, ScoredAoi
from ..configuration import get_config, Configuration
from ..preprocessor import create_uows, run_units_of_work, PreprocessingResult, PreprocessedAoi, aois_from_results

SUBCOMMAND = "pushbroom"
ALIASES = ["pb", "schedule", "sched"]
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

    # process results into scheduler data structures
    platforms = Platforms([Platform(model=r.sat, ephemeris=r.ephemeris) for r in results])
    report = init_access_report(aois_from_results(results))

    # sort the aois into priority order
    report["score"] = 0
    scored_aois: list[ScoredAoi] = []
    for value in score_aois(aois_from_results(results)):
        report.loc[
            report["aoi_id"] == value.aoi.aoi.id, "score"
        ] = value.score  #  x.aoi is known to be PreprocessedAoi

        if value.score > 0:
            scored_aois.append(value)

    scored_aois.sort(key=lambda x: (x.score, x.aoi.aoi.id))  #  x.aoi is known to be PreprocessedAoi
    report["order_index"] = -1

    for index, sa in enumerate(scored_aois):
        report.loc[report["aoi_id"] == sa.aoi.aoi.id, "order_index"] = index  #  x.aoi is known to be PreprocessedAoi

    # now, for the scheduling
