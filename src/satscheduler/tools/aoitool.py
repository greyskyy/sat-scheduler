"""Load and visualize AOIs."""
from satscheduler.aoi import loadAois

import folium
import logging


def list_aoi(args=None, config=None, vm=None):
    """Load the AOIs, generating a summary + map plot.

    Args:
        args (argparse.Namespace, optional): The command line arguments. Defaults to None.
        config (dict, optional): A dictionary loaded with the application configuration file's contents. Defaults to None.
        vm (_type_, optional): A reference to the orekit virtual machine. Defaults to None.
    """
    logger = logging.getLogger(__name__)
    aois = loadAois()

    map = folium.Map()

    zones = []
    logger.info("loaded %d aois", len(aois))
    for aoi in aois:
        folium.GeoJson(
            data=aoi.to_gdf().to_json(), name=aoi.id, popup=aoi.id, zoom_on_click=True
        ).add_to(map)
        zones.extend(aoi.createZones())

    logger.info("loaded %d zones", len(zones))
    map.save("test.html")

    # todo print the zones

    return 0
