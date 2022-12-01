"""Load and visualize AOIs, mapping AOIs as HTML and/or CZML."""
import czml3
import czml3.enums
import czml3.properties
import czml3.types
import folium
import math
import logging
import pandas as pd
import os
import os.path

from org.hipparchus.geometry.spherical.twod import Vertex

from .aoi import Aoi, load_aois
from ..configuration import get_config, AoiConfiguration

SUBCOMMAND = "list-aois"
ALIASES = ["aois", "la"]
LOGGER_NAME = "satscheduler"


def config_args(parser):
    """Add command line arguments.

    Args:
        parser (argparse.ArgumentParser): the command line parser to which arguments will be added.
    """
    html_group = parser.add_mutually_exclusive_group()
    html_group.add_argument(
        "--html",
        type=str,
        nargs="?",
        dest="html",
        metavar="OUTPUT",
        help="Path where to record the output html file.",
        default="aois.html",
        const="aois.html",
    )

    html_group.add_argument(
        "--no-html",
        dest="html",
        action="store_const",
        const=None,
        help="Suppress the html output.",
    )

    parser.add_argument(
        "--czml",
        dest="czml",
        nargs="?",
        default=None,
        const="aois.czml",
        metavar="FILENAME",
        help="Path where to write a czml output holding AOIs. If no file path specified, then `aois.czml`"
        " will be used.",
    )

    parser.add_argument(
        "--csv",
        dest="csv",
        nargs="?",
        default=None,
        const="aois.csv",
        metavar="FILENAME",
        help="Path where to write a csv output holding AOIs. If no file path specified, then `aois.csv`"
        " will be used.",
    )

    parser.add_argument(
        "--border",
        dest="border",
        nargs="?",
        default=None,
        const="aoi_borders",
        metavar="AOI_DIRECTORY",
        help="Path to a directory in which aoi borders will be stored. In no path specified, then 'aoi_borders'"
        " will be used.",
    )


def execute(args=None):
    """Load the AOIs, generating a summary + map plot.

    Args:
        args (argparse.Namespace, optional): The command line arguments. Defaults to None.
    """
    logger = logging.getLogger(__name__)
    config = get_config()

    aois = load_aois(config.aois)
    logger.info("loaded %d aois", len(aois))

    zones = [aoi.createZone() for aoi in aois]
    logger.info("loaded %d zones", len(zones))

    if args.html:
        _create_aoi_folium_map(args, aois, logger)

    if args.czml:
        _create_aoi_czml(args, config.aois, aois, logger)

    if args.csv:
        _create_aoi_csv(args, aois, logger)

    if args.border:
        if not os.path.exists(args.border):
            os.makedirs(args.border, exist_ok=True)
        for aoi in aois:
            _write_aoi_border(aoi, prefix=args.border)

        logger.info("aoi borders written to %s", args.border)
    return 0


def aoi_to_czml(aoi: Aoi, config: AoiConfiguration, zones: bool = False) -> czml3.Packet:
    """Generate a czml packet for the provided aoi.

    Args:
        aoi (Aoi): The aoi
        zones (bool, optional): Flag indicating whether to use the aoi boundary (False) or the schedulable zone
        (True). Defaults to False.
        config (dict, optional): Configuration dictionary. Defaults to {}.

    Returns:
        czml3.Packet: The CZML packet
    """

    def defaults(k: str, v):
        if hasattr(config, k):
            if (value := getattr(config, k)) is not None:
                return value
        return v

    label = czml3.properties.Label(
        horizontalOrigin=czml3.enums.HorizontalOrigins.CENTER,
        show=defaults("labels", True),
        font=defaults("font", "11pt Lucida Console"),
        style=czml3.enums.LabelStyles.FILL_AND_OUTLINE,
        outlineWidth=2,
        text=f"{aoi.country} ({aoi.id})",
        verticalOrigin=czml3.enums.VerticalOrigins.BASELINE,
        fillColor=czml3.properties.Color.from_str(defaults("color", "#FF0000")),
    )

    if zones:
        zone = aoi.createZone()
        initialVert: Vertex = zone.getBoundaryLoops().get(0)
        nextVert: Vertex = initialVert.getOutgoing().getEnd()

        s2_points = [initialVert.getLocation()]

        while initialVert.getLocation().distance(nextVert.getLocation()) > 1e-10:
            s2_points.append(nextVert.getLocation())
            nextVert = nextVert.getOutgoing().getEnd()

        coords = []
        for p in s2_points:
            lat = 0.5 * math.pi - p.getPhi()
            lon = p.getTheta()

            coords.extend([lon, lat, 100])

        positions = czml3.properties.PositionList(cartographicRadians=coords)

    else:
        coords = []
        for c in aoi.polygon.boundary.coords:
            if math.isfinite(c[0]) and math.isfinite(c[1]):
                coords.extend(c)
                coords.append(100)  # 0m elevation

        positions = czml3.properties.PositionList(cartographicDegrees=coords)

    if aoi.polygon.centroid.bounds:
        position = czml3.properties.Position(
            cartographicDegrees=[
                aoi.polygon.centroid.coords[0][0],
                aoi.polygon.centroid.coords[0][1],
                1000,
            ]
        )
    else:
        position = None

    return czml3.Packet(
        id=f"aoi/{aoi.id}",
        name=aoi.id,
        label=label,
        polyline=czml3.properties.Polyline(
            positions=positions,
            material=czml3.properties.Material(
                polylineOutline=czml3.properties.PolylineOutlineMaterial(
                    color=label.fillColor, outlineColor=label.fillColor, outlineWidth=3
                ),
            ),
            arcType=czml3.enums.ArcTypes.GEODESIC,
            clampToGround=True,
            zIndex=10,
        ),
        position=position,
    )


def _write_aoi_border(aoi: Aoi, prefix: str = None, write_zone: bool = True):
    """Write the AOI border to a csv file.

    Args:
        aoi (Aoi): The AOI to record.
        prefix (str, optional): File prefix to pe prepended to the aoi id and country. Defaults to None.
        write_zone (bool, optional): Flag indicating whether to write the zone boundary in addition to the
        polygon. Defaults to True.
    """
    fname = os.path.join(f"{prefix if prefix else ''}", f"{aoi.id}_{aoi.country or ''}.csv")
    with open(fname, "w") as f:
        for c in aoi.polygon.boundary.coords:
            f.write(f"{c[0]}, {c[1]}{os.linesep}")

    if write_zone:
        zone = aoi.createZone()
        initialVert: Vertex = zone.getBoundaryLoops().get(0)
        nextVert: Vertex = initialVert.getOutgoing().getEnd()
        s2_points = [initialVert.getLocation()]

        while initialVert.getLocation().distance(nextVert.getLocation()) > 1e-10:
            s2_points.append(nextVert.getLocation())
            nextVert = nextVert.getOutgoing().getEnd()
        with open(f"{fname[:-4]}_zone.csv", "w") as f:
            for p in s2_points:
                lat = math.degrees(0.5 * math.pi - p.getPhi())
                lon = math.degrees(p.getTheta())

                f.write(f"{lon},{lat}{os.linesep}")


def _create_aoi_folium_map(args, aois, logger):
    map = folium.Map()

    for aoi in aois:
        folium.GeoJson(
            data=aoi.to_gdf().to_json(),
            name=aoi.id,
            popup=aoi.id,
            zoom_on_click=True,
        ).add_to(map)

    map.save(args.html)

    logger.info("Folium map written to %s", args.html)


def _create_aoi_czml(args, config, aois, logger):
    fname: str = args.czml
    if fname.endswith(".czml"):
        fname2 = fname.replace(".czml", "_zone.czml")
    else:
        fname2 = f"{fname}_zones.czml"
        fname = f"{fname}.czml"

    doc = czml3.Document(
        [
            czml3.Preamble(
                name="Aois",
            ),
            *[aoi_to_czml(aoi, config=config) for aoi in aois],
        ]
    )
    with open(fname, "w") as f:
        doc.dump(f)

    doc = czml3.Document(
        [
            czml3.Preamble(
                name="Aoi Zones",
            ),
            *[aoi_to_czml(aoi, config=config, zones=True) for aoi in aois],
        ]
    )
    with open(fname2, "w") as f:
        doc.dump(f)

    logger.info(
        "AOI boundaries written to %s and scheduling boundaries written to %s",
        fname,
        fname2,
    )


def _create_aoi_csv(args, aois, logger):
    aoi_df = pd.DataFrame(columns=["aoi_id", "country", "continent", "area", "alpha2", "alpha3", "priority"])
    idx = 0
    for aoi in aois:
        aoi_df.loc[idx] = [aoi.id, aoi.country, aoi.continent, aoi.area, aoi.alpha2, aoi.alpha3, aoi.priority]
        idx += 1

    aoi_df.to_csv(args.csv)

    logger.info("AOI summary written to %s", args.csv)
