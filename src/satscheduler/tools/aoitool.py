"""Load and visualize AOIs, mapping AOIs as HTML and/or CZML."""
import czml3
import czml3.enums
import czml3.properties
import czml3.types
import folium
import math
import logging

from org.hipparchus.geometry.spherical.twod import Vertex

from ..aoi import Aoi, loadAois
from ..configuration import get_config
from ..utils.czml import Polygon as OutlinedPolygon

SUBCOMMAND = "list-aois"
ALIASES = ["aois", "la"]
LOGGER_NAME = "satscheduler"


def config_args(parser):
    """Add command line arguments

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
        help="Path where to write a czml output holding AOIs. If no file path specified, then `aois.czml` will be used.",
    )


def execute(args=None):
    """Load the AOIs, generating a summary + map plot.

    Args:
        args (argparse.Namespace, optional): The command line arguments. Defaults to None.
    """
    logger = logging.getLogger(__name__)
    config = get_config()

    if config and "aois" in config:
        aois = loadAois(**config["aois"])
    else:
        aois = loadAois()
    logger.info("loaded %d aois", len(aois))

    zones = [aoi.createZone() for aoi in aois]
    logger.info("loaded %d zones", len(zones))

    if args.html:
        map = folium.Map()

        zones = []
        for aoi in aois:
            folium.GeoJson(
                data=aoi.to_gdf().to_json(),
                name=aoi.id,
                popup=aoi.id,
                zoom_on_click=True,
            ).add_to(map)

        map.save(args.html)

        logger.info("Folium map written to %s", args.html)

    if args.czml:
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
                *[aoi_to_czml(aoi, config=config["aois"]) for aoi in aois],
            ]
        )
        with open(fname, "w") as f:
            doc.dump(f)

        doc = czml3.Document(
            [
                czml3.Preamble(
                    name="Aoi Zones",
                ),
                *[aoi_to_czml(aoi, zones=True, config=config["aois"]) for aoi in aois],
            ]
        )
        with open(fname2, "w") as f:
            doc.dump(f)

        logger.info(
            "AOI boundaries written to %s and scheduling boundaries written to %s",
            fname,
            fname2,
        )

    return 0


def aoi_to_czml(aoi: Aoi, zones: bool = False, config: dict = {}) -> czml3.Packet:
    """Generate a czml packet for the provided aoi

    Args:
        aoi (Aoi): The aoi
        zones (bool, optional): Flag indicating whether to use the aoi boundary (False) or the schedulable zone (True). Defaults to False.
        config (dict, optional): Configuration dictionary. Defaults to {}.

    Returns:
        czml3.Packet: _description_
    """
    label = czml3.properties.Label(
        horizontalOrigin=czml3.enums.HorizontalOrigins.LEFT,
        show=config.get("labels", True),
        font=config.get("font", "11pt Lucida Console"),
        style=czml3.enums.LabelStyles.FILL_AND_OUTLINE,
        outlineWidth=2,
        text=f"{aoi.country} ({aoi.id})",
        verticalOrigin=czml3.enums.VerticalOrigins.CENTER,
        fillColor=czml3.properties.Color.from_str(config.get("color", "#FF0000")),
        outlineColor=czml3.properties.Color.from_str(config.get("color", "#000000")),
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

            coords.extend([lon, lat, 10])

        positions = czml3.properties.PositionList(cartographicRadians=coords)

    else:
        coords = []
        for c in aoi.polygon.boundary.coords:
            coords.extend(c)
            coords.append(10)  # 0m elevation
        positions = czml3.properties.PositionList(cartographicDegrees=coords)

    return czml3.Packet(
        id=f"aoi/{aoi.id}",
        name=aoi.id,
        label=label,
        polyline=czml3.properties.Polyline(
            positions=positions,
            material=czml3.properties.Material(
                polylineOutline=czml3.properties.PolylineOutlineMaterial(
                    color=label.fillColor,
                    outlineColor=label.fillColor,
                    outlineWidth=3
                ),
            ),
            arcType=czml3.enums.ArcTypes.GEODESIC,
            zIndex=10
        ),
        position=czml3.properties.Position(
            cartographicDegrees=[
                aoi.polygon.centroid.coords[0][0],
                aoi.polygon.centroid.coords[0][1],
                0,
            ]
        ),
    )
