"""Execute the pre-processor, provide stats on results."""
import argparse
import czml3
import czml3.enums
import czml3.properties
import czml3.types
import datetime as dt
import logging

import orekitfactory.factory
import orekitfactory.initializer
import pandas as pd

from typing import Iterator
from orekit.pyhelpers import absolutedate_to_datetime, datetime_to_absolutedate
from orekitfactory.time import (
    DateInterval,
    DateIntervalList,
    IntervalListOperations
)

from org.orekit.data import DataContext
from org.orekit.orbits import OrbitType
from org.orekit.time import AbsoluteDate

from .aoitool import aoi_to_czml
from ..configuration import get_config
from ..preprocessor import (
    execute as preprocessor_execute,
    PreprocessedAoi,
    PreprocessingResult,
)
from ..utils.czml import Polygon as OutlinedPolygon

# patch cml3
czml3.types.TYPE_MAPPING[int] = "number"
czml3.types.TYPE_MAPPING[float] = "number"

SUBCOMMAND = "preprocess"
ALIASES = ["prep"]
LOGGER_NAME = "satscheduler"


def config_args(parser):
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
        help="Toggle the generation of a czml document with the AOIs."
    )
    
    parser.add_argument(
        "--csv",
        dest="paoi_csv",
        default=True,
        action=argparse.BooleanOptionalAction,
        help="Toggle generation of access CSV file."
    )


def populate_dataframes(results:list[PreprocessingResult]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Populate the result dataframes.

    Args:
        results (list[PreprocessingResult]): The list of results from the preprocessors.

    Returns:
        tuple[pd.DataFrame, pd.DataFrame]: The dataframes. The first data frame lists the AOIs processed, the second provides the access times.
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
    
    aoi_df = pd.DataFrame(
        columns=[
            "aoi_id",
            "satellite",
            "sensor",
            "area",
            "continent",
            "country"
        ]
    )

    aidx = 0
    pidx = 0
    for a in iterate_results(results):
        aoi_df.loc[pidx] = [a.aoi.id, a.sat.id, a.sensor.id, a.aoi.area, a.aoi.continent, a.aoi.country]
        pidx += 1
        for ivl in a.intervals:
            paoi_df.loc[aidx] = [a.aoi.id, a.sat.id, a.sensor.id, absolutedate_to_datetime(ivl.start), absolutedate_to_datetime(ivl.stop), ivl.duration]
            aidx += 1
    
    paoi_df["duration_secs"] = paoi_df["duration"].dt.total_seconds()
    
    return aoi_df, paoi_df

def iterate_results(results:list[PreprocessingResult]) -> Iterator[PreprocessedAoi]:
    for r in results:
        yield from r.aois

def execute(args=None):
    """Load the AOIs, generating a summary + map plot.

    Args:
        args (argparse.Namespace, optional): The command line arguments. Defaults to None.
        config (dict, optional): A dictionary loaded with the application configuration file's contents. Defaults to None.
        vm (_type_, optional): A reference to the orekit virtual machine. Defaults to None.
    """
    logger = logging.getLogger(__name__)
    config = get_config()
    vm = orekitfactory.initializer.get_orekit_vm()

    # Execute preprocessing
    logger.info("Starting preprocessor tool.")
    results: list[PreprocessingResult] = preprocessor_execute(
        args=args, config=config, vm=vm
    )
    logger.info("Preprocessing complete.")
    
    # Populate dataframes
    aoi_df, paoi_df = populate_dataframes(results)
    logger.info("Produced %d preprocessed aois", len(aoi_df.groupby(["aoi_id", "satellite", "sensor"])))
    
    # Produce summary output
    total_aoi = len(aoi_df["aoi_id"].unique())
    proc_aoi = len(paoi_df["aoi_id"].unique())
    
    total_sum = paoi_df[["aoi_id", "duration"]].groupby(["aoi_id"]).sum()
    total_sum.rename(columns={"duration":"total access duration"}, inplace=True)
    print(total_sum)

    logger.info(
        "After processing, %d/%d aois have no access.", total_aoi - proc_aoi, total_aoi
    )
    
    # Write the aoi czml
    if args.aoi_czml:
        aoi_czml = czml3.Document(
            [
                czml3.Preamble(
                    name="Aois",
                ),
                *[aoi_to_czml(aoi.aoi, config=config["aois"]) for aoi in iterate_results(results)],
            ]
        )
        
        with open(f"{args.prefix}_aois.czml", "w") as f:
            aoi_czml.dump(f)
    
    # Write the access csv
    if args.paoi_csv:
        paoi_df.to_csv(f"{args.prefix}_access.csv")
    
    # Write the satellite processing czml
    for r in results:
        sat_packet, sat_start, sat_stop = generate_satellite_czml(r, config)
        
        total_interval = DateIntervalList(interval=DateInterval(
            datetime_to_absolutedate(sat_start),
            datetime_to_absolutedate(sat_stop)
        ))
        
        sat_doc = czml3.Document([
            czml3.Preamble(
                name=f"{r.sat.name} preprocessing aoi results",
                clock=czml3.types.IntervalValue(
                    start=sat_start,
                    end=sat_stop,
                    value=czml3.properties.Clock(currentTime=sat_start, multiplier=10)
                )
            ),
            sat_packet,
            *[generate_paoi_czml(aoi, total_interval, config.get("aois", {})) for aoi in r.aois]
        ])
        
        with open(f"{args.prefix}_sat_{r.sat.id}.czml", "w") as f:
            sat_doc.dump(f)

def generate_satellite_czml(result:PreprocessingResult, config:dict) -> tuple[czml3.Packet, dt.datetime, dt.datetime]:
    """Generate a czml packet for the satellite in the results

    Args:
        result (PreprocessingResult): The preprocessing result

    Returns:
        tuple[czml3.Packet, dt.datetime, dt.datetime]: A 3-tuple of the czml packet, the start time, and the stop time
    """
    default_config = config
    orbit_config = config["satellites"][result.sat.id]
    defaults = lambda x, v: orbit_config.get(x, default_config.get(x, v))
    
    start = absolutedate_to_datetime(result.ephemeris.getMinDate())
    stop = absolutedate_to_datetime(result.ephemeris.getMaxDate())
    
    frame = orekitfactory.factory.get_frame("itrf", iersConventions="2010", simpleEop=False)
    # function to generate the cartesian position array
    def generate_carts():
        t: AbsoluteDate = result.ephemeris.getMinDate()
        step_secs: float = 300.
        while t.isBeforeOrEqualTo(result.ephemeris.getMaxDate()):
            try:
                pv = result.ephemeris.getPVCoordinates(t, frame)
            except:
                print(f"Error at a time: {t}")
                raise

            yield t.durationFrom(result.ephemeris.getMinDate())
            yield pv.getPosition().getX()
            yield pv.getPosition().getY()
            yield pv.getPosition().getZ()

            t = t.shiftedBy(step_secs)
    
    label = czml3.properties.Label(
        horizontalOrigin=czml3.enums.HorizontalOrigins.LEFT,
        outlineWidth=defaults("outlineWidth", 2),
        show=True,
        font=defaults("font", "11pt Lucida Console"),
        style=czml3.enums.LabelStyles.FILL_AND_OUTLINE,
        text=result.sat.name,
        verticalOrigin=czml3.enums.VerticalOrigins.CENTER,
        fillColor=czml3.properties.Color.from_str(defaults("color", "#00FF00")),
        outlineColor=czml3.properties.Color.from_str(
            defaults("color", "#000000")
        ),
    )
    
    bb = czml3.properties.Billboard(
        horizontalOrigin=czml3.enums.HorizontalOrigins.CENTER,
        image=(
            "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9"
            "hAAAAAXNSR0IArs4c6QAAAARnQU1BAACxjwv8YQUAAAAJcEhZcwAADsMAAA7DAcdv"
            "qGQAAADJSURBVDhPnZHRDcMgEEMZjVEYpaNklIzSEfLfD4qNnXAJSFWfhO7w2Zc0T"
            "f9QG2rXrEzSUeZLOGm47WoH95x3Hl3jEgilvDgsOQUTqsNl68ezEwn1vae6lceSEE"
            "YvvWNT/Rxc4CXQNGadho1NXoJ+9iaqc2xi2xbt23PJCDIB6TQjOC6Bho/sDy3fBQT"
            "8PrVhibU7yBFcEPaRxOoeTwbwByCOYf9VGp1BYI1BA+EeHhmfzKbBoJEQwn1yzUZt"
            "yspIQUha85MpkNIXB7GizqDEECsAAAAASUVORK5CYII="
        ),
        scale=defaults("scale", 1.5),
        show=True,
        verticalOrigin=czml3.enums.VerticalOrigins.CENTER,
    )
    
    width_intervals = []
    
    for a in result.aois:
        for ivl in a.intervals:
            width_intervals.append(
                czml3.types.IntervalValue(
                    start=absolutedate_to_datetime(ivl.start),
                    end=absolutedate_to_datetime(ivl.stop),
                    value=5)   
            )
    
    path = czml3.properties.Path(
        show=czml3.types.Sequence(
            [czml3.types.IntervalValue(start=start, end=stop, value=True)]
        ),
        width=czml3.types.Sequence(width_intervals),
        resolution=120,
        material=czml3.properties.Material(
            solidColor=czml3.properties.SolidColorMaterial(color=label.fillColor)
        ),
    )

    pos = czml3.properties.Position(
        interpolationAlgorithm=czml3.enums.InterpolationAlgorithms.HERMITE,
        interpolationDegree=3,
        referenceFrame=czml3.enums.ReferenceFrames.FIXED,
        epoch=start,
        cartesian=list(generate_carts()),
    )
    
    return czml3.Packet(
        id=result.sat.id,
        name=result.sat.name,
        availability=czml3.types.TimeInterval(start=start, end=stop),
        billboard=bb,
        label=label,
        path=path,
        position=pos,
    ), start, stop


def generate_paoi_czml(aoi:PreprocessedAoi, total_interval:DateIntervalList, config:dict) -> czml3.Packet:
    
    
    label = czml3.properties.Label(
        horizontalOrigin=czml3.enums.HorizontalOrigins.LEFT,
        show=config.get("labels", True),
        font=config.get("font", "11pt Lucida Console"),
        style=czml3.enums.LabelStyles.FILL,
        outlineWidth=2,
        text=f"{aoi.aoi.country} ({aoi.aoi.id})",
        verticalOrigin=czml3.enums.VerticalOrigins.CENTER,
        fillColor=czml3.properties.Color.from_str(config.get("color", "#FF0000")),
        outlineColor=czml3.properties.Color.from_str(config.get("color", "#000000")),
    )
    
    coords = []
    for c in aoi.aoi.polygon.boundary.coords:
        coords.extend(c)
        coords.append(10)  # 0m elevation
    positions = czml3.properties.PositionList(cartographicDegrees=coords)
    
    no_access = IntervalListOperations.subtract(total_interval, aoi.intervals)
    
    show_intervals = []
    hide_intervals=[]
    for ivl in aoi.intervals:
        show_intervals.append(
            czml3.types.IntervalValue(
                start=absolutedate_to_datetime(ivl.start),
                end=absolutedate_to_datetime(ivl.stop),
                value=True)   
        )
        hide_intervals.append(
            czml3.types.IntervalValue(
                start=absolutedate_to_datetime(ivl.start),
                end=absolutedate_to_datetime(ivl.stop),
                value=False)   
        )
    for ivl in no_access:
        show_intervals.append(
            czml3.types.IntervalValue(
                start=absolutedate_to_datetime(ivl.start),
                end=absolutedate_to_datetime(ivl.stop),
                value=False)
        )
        hide_intervals.append(
            czml3.types.IntervalValue(
                start=absolutedate_to_datetime(ivl.start),
                end=absolutedate_to_datetime(ivl.stop),
                value=True)   
        )
        

    return czml3.Packet(
        id=f"p_aoi/{aoi.aoi.id}",
        name=f"{aoi.aoi.country} ({aoi.aoi.id})",
        label=label,
        polygon=czml3.properties.Polygon(
            positions=positions,
            material=czml3.properties.Material(
                solidColor=czml3.properties.SolidColorMaterial(color=label.fillColor)
            ),
            arcType=czml3.enums.ArcTypes.GEODESIC,
            show=czml3.types.Sequence(show_intervals),
            zIndex=10
        ),
        polyline=czml3.properties.Polyline(
            positions=positions,
            material=czml3.properties.Material(
                polylineOutline=czml3.properties.PolylineOutlineMaterial(
                    color=label.fillColor
                ),
            ),
            arcType=czml3.enums.ArcTypes.GEODESIC,
            show=True,
            zIndex=1
        ),
        position=czml3.properties.Position(
            cartographicDegrees=[
                aoi.aoi.polygon.centroid.coords[0][0],
                aoi.aoi.polygon.centroid.coords[0][1],
                0,
            ]
        ),
    )