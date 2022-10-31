"""Execute the pre-processor, provide stats on results."""
import argparse
import math
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
from orekitfactory.time import DateInterval, DateIntervalList

from java.util import List
from org.orekit.bodies import GeodeticPoint
from org.orekit.time import AbsoluteDate
from org.orekit.frames import Transform

from .preprocessor import (
    PreprocessedAoi,
    PreprocessingResult,
)
from .runner import execute as preprocessor_execute
from ..aoi.tool import aoi_to_czml
from ..configuration import get_config
from ..utils.czml import Polygon as OutlinedPolygon

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


def populate_dataframes(results: list[PreprocessingResult]) -> tuple[pd.DataFrame, pd.DataFrame]:
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
        columns=["aoi_id", "satellite", "sensor", "area", "continent", "country"]
    )

    aidx = 0
    pidx = 0
    for a in iterate_results(results):
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


def iterate_results(results: list[PreprocessingResult]) -> Iterator[PreprocessedAoi]:
    """Iterate over the preprocessed aois in the provided result sequence.

    Args:
        results (Sequence[PreprocessingResult]): The iterable preprocessing results

    Yields:
        Iterator[PreprocessedAoi]: An iterator over all pre-processed AOIs in the result list.
    """
    for r in results:
        yield from r.aois


def execute(args=None) -> int:
    """Load the AOIs, generating a summary + map plot.

    Args:
        args (argparse.Namespace, optional): The command line arguments. Defaults to None.
    
    Returns:
        int: The return code to provide back to the OS.
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
        print(proc_aoi)
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
                *[
                    aoi_to_czml(aoi.aoi, config=config["aois"])
                    for aoi in iterate_results(results)
                ],
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

        total_interval = DateIntervalList(
            interval=DateInterval(
                datetime_to_absolutedate(sat_start), datetime_to_absolutedate(sat_stop)
            )
        )

        sensor_packets = generate_sensor_czml(
            r, total_interval.span.start, total_interval.span.stop, config
        )

        sat_doc = czml3.Document(
            [
                czml3.Preamble(
                    name=f"{r.sat.name} preprocessing aoi results",
                    clock=czml3.types.IntervalValue(
                        start=sat_start,
                        end=sat_stop,
                        value=czml3.properties.Clock(
                            currentTime=sat_start, multiplier=10
                        ),
                    ),
                ),
                sat_packet,
                *[
                    generate_paoi_czml(aoi, total_interval, config.get("aois", {}))
                    for aoi in r.aois
                ],
                *sensor_packets,
            ]
        )

        with open(f"{args.prefix}_sat_{r.sat.id}.czml", "w") as f:
            sat_doc.dump(f)
    
    return 0


def generate_sensor_czml(
    result: PreprocessingResult, start: AbsoluteDate, stop: AbsoluteDate, config: dict
) -> tuple[czml3.Packet]:
    sat = result.sat
    fov = sat.sensor("camera").createFovInBodyFrame()

    default_config = config
    orbit_config = config["satellites"][result.sat.id]
    defaults = lambda x, v: orbit_config.get(x, default_config.get(x, v))

    interval = (
        result.interval
    )  # DateInterval(start=result.ephemeris.getMinDate(), stop=result.ephemeris.getMaxDate())

    frame = orekitfactory.factory.get_frame(
        "itrf", iersConventions="2010", simpleEop=False
    )
    earth = orekitfactory.factory.get_reference_ellipsoid(
        model="wgs84", frameName="itrf", simpleEop=False
    )

    p0_coords = []
    p1_coords = []
    p2_coords = []
    p3_coords = []

    t = interval.start
    step_secs: float = 300.0
    while t.isBeforeOrEqualTo(interval.stop):
        state = result.ephemeris.propagate(t)
        inertialToBody_tx = state.getFrame().getTransformTo(
            earth.getBodyFrame(), state.getDate()
        )
        fovToBody_tx = Transform(
            state.getDate(), state.toTransform().getInverse(), inertialToBody_tx
        )

        footprint = fov.getFootprint(fovToBody_tx, earth, math.radians(10))
        locs = List.cast_(footprint.get(0))

        p0: GeodeticPoint = GeodeticPoint.cast_(locs.get(0))
        p1: GeodeticPoint = GeodeticPoint.cast_(locs.get(1))
        p2: GeodeticPoint = GeodeticPoint.cast_(locs.get(2))
        p3: GeodeticPoint = GeodeticPoint.cast_(locs.get(3))

        dt = t.durationFrom(interval.start)
        p0_coords.extend((dt, p0.getLongitude(), p0.getLatitude(), p0.getAltitude()))
        p1_coords.extend((dt, p1.getLongitude(), p1.getLatitude(), p1.getAltitude()))
        p2_coords.extend((dt, p2.getLongitude(), p2.getLatitude(), p2.getAltitude()))
        p3_coords.extend((dt, p3.getLongitude(), p3.getLatitude(), p3.getAltitude()))

        t = t.shiftedBy(step_secs)

    interval_czml = czml3.types.TimeInterval(
        start=interval.start_dt, end=interval.stop_dt
    )
    return [
        czml3.Packet(
            id=f"footprint/{sat.id}/camera-0",
            position=czml3.properties.Position(
                interpolationAlgorithm=czml3.enums.InterpolationAlgorithms.LINEAR,
                interpolationDegree=1,
                interval=interval_czml,
                epoch=interval.start_dt,
                cartographicRadians=p0_coords,
            ),
        ),
        czml3.Packet(
            id=f"footprint/{sat.id}/camera-1",
            position=czml3.properties.Position(
                interpolationAlgorithm=czml3.enums.InterpolationAlgorithms.LINEAR,
                interpolationDegree=1,
                interval=interval_czml,
                epoch=interval.start_dt,
                cartographicRadians=p1_coords,
            ),
        ),
        czml3.Packet(
            id=f"footprint/{sat.id}/camera-2",
            position=czml3.properties.Position(
                interpolationAlgorithm=czml3.enums.InterpolationAlgorithms.LINEAR,
                interpolationDegree=1,
                interval=interval_czml,
                epoch=interval.start_dt,
                cartographicRadians=p2_coords,
            ),
        ),
        czml3.Packet(
            id=f"footprint/{sat.id}/camera-3",
            position=czml3.properties.Position(
                interpolationAlgorithm=czml3.enums.InterpolationAlgorithms.LINEAR,
                interpolationDegree=1,
                interval=interval_czml,
                epoch=interval.start_dt,
                cartographicRadians=p3_coords,
            ),
        ),
        czml3.Packet(
            id=f"footprint/{sat.id}/camera",
            name=f"{sat.id}/camera",
            availability=interval_czml,
            polygon=czml3.properties.Polygon(
                show=True,
                positions=czml3.properties.PositionList(
                    references=[
                        czml3.types.ReferenceValue(
                            string=f"footprint/{sat.id}/camera-0#position"
                        ),
                        czml3.types.ReferenceValue(
                            string=f"footprint/{sat.id}/camera-1#position"
                        ),
                        czml3.types.ReferenceValue(
                            string=f"footprint/{sat.id}/camera-2#position"
                        ),
                        czml3.types.ReferenceValue(
                            string=f"footprint/{sat.id}/camera-3#position"
                        ),
                    ]
                ),
                material=czml3.properties.Material(
                    solidColor=czml3.properties.SolidColorMaterial(
                        color=czml3.properties.Color.from_str(
                            config.get("color", "#0000FF")
                        )
                    ),
                ),
                arcType=czml3.enums.ArcTypes.GEODESIC,
                zIndex=10,
            ),
        ),
    ]


def generate_satellite_czml(
    result: PreprocessingResult, config: dict
) -> tuple[czml3.Packet, dt.datetime, dt.datetime]:
    """Generate a czml packet for the satellite in the results

    Args:
        result (PreprocessingResult): The preprocessing result

    Returns:
        tuple[czml3.Packet, dt.datetime, dt.datetime]: A 3-tuple of the czml packet, the start time, and the stop time
    """
    default_config = config
    orbit_config = config["satellites"][result.sat.id]
    defaults = lambda x, v: orbit_config.get(x, default_config.get(x, v))

    interval = (
        result.interval
    )  # DateInterval(start=result.ephemeris.getMinDate(), stop=result.ephemeris.getMaxDate())

    frame = orekitfactory.factory.get_frame(
        "itrf", iersConventions="2010", simpleEop=False
    )
    # function to generate the cartesian position array
    def generate_carts():
        t: AbsoluteDate = interval.start
        step_secs: float = 300.0
        while t.isBeforeOrEqualTo(interval.stop):
            try:
                pv = result.ephemeris.getPVCoordinates(t, frame)
            except:
                print(f"Error at a time: {t}")
                raise

            yield t.durationFrom(interval.start)
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
        outlineColor=czml3.properties.Color.from_str(defaults("color", "#000000")),
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
                czml3.types.IntervalValue(start=ivl.start_dt, end=ivl.stop_dt, value=5)
            )

    path = czml3.properties.Path(
        show=czml3.types.Sequence(
            [
                czml3.types.IntervalValue(
                    start=interval.start_dt, end=interval.stop_dt, value=True
                )
            ]
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
        epoch=interval.start_dt,
        cartesian=list(generate_carts()),
    )

    return (
        czml3.Packet(
            id=result.sat.id,
            name=result.sat.name,
            availability=czml3.types.TimeInterval(
                start=interval.start_dt, end=interval.stop_dt
            ),
            billboard=bb,
            label=label,
            path=path,
            position=pos,
        ),
        interval.start_dt,
        interval.stop_dt,
    )


def generate_paoi_czml(
    aoi: PreprocessedAoi, total_interval: DateIntervalList, config: dict
) -> czml3.Packet:

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
        if math.isfinite(c[0]) and math.isfinite(c[1]):
            coords.extend(c)
            coords.append(10)  # 0m elevation
    positions = czml3.properties.PositionList(cartographicDegrees=coords)

    no_access = total_interval - aoi.intervals

    show_intervals = []
    hide_intervals = []
    for ivl in aoi.intervals:
        show_intervals.append(
            czml3.types.IntervalValue(
                start=absolutedate_to_datetime(ivl.start),
                end=absolutedate_to_datetime(ivl.stop),
                value=True,
            )
        )
        hide_intervals.append(
            czml3.types.IntervalValue(
                start=absolutedate_to_datetime(ivl.start),
                end=absolutedate_to_datetime(ivl.stop),
                value=False,
            )
        )
    for ivl in no_access:
        show_intervals.append(
            czml3.types.IntervalValue(
                start=absolutedate_to_datetime(ivl.start),
                end=absolutedate_to_datetime(ivl.stop),
                value=False,
            )
        )
        hide_intervals.append(
            czml3.types.IntervalValue(
                start=absolutedate_to_datetime(ivl.start),
                end=absolutedate_to_datetime(ivl.stop),
                value=True,
            )
        )

    if aoi.aoi.polygon.centroid.bounds:
        position = czml3.properties.Position(
            cartographicDegrees=[
                aoi.aoi.polygon.centroid.coords[0][0],
                aoi.aoi.polygon.centroid.coords[0][1],
                1000,
            ]
        )
    else:
        position = None

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
            zIndex=10,
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
            zIndex=1,
        ),
        position=position,
    )
