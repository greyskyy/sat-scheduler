"""Load and visualize AOIs."""
from satscheduler.aoi import loadAois

import folium
import logging

from ..configuration import get_config

SUBCOMMAND = "list-aois"
ALIASES = ["aois", "la"]


def config_args(parser):
    parser.add_argument(
        "-o",
        "--output",
        type=str,
        dest="output",
        metavar="OUTPUT",
        help="Path where to record the output html file.",
        default="aois.html",
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

    map = folium.Map()

    zones = []
    logger.info("loaded %d aois", len(aois))
    for aoi in aois:
        folium.GeoJson(
            data=aoi.to_gdf().to_json(), name=aoi.id, popup=aoi.id, zoom_on_click=True
        ).add_to(map)
        zones.append(aoi.createZones())

    logger.info("loaded %d zones", len(zones))
    map.save(args.output or "test.html")

    # todo print the zones

    return 0
