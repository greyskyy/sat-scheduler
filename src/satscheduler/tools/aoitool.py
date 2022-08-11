"""Load and visualize AOIs."""
from satscheduler.aoi import loadAois

import folium


def list_aoi(args=None, config=None, vm=None):
    """Load the AOIs, generating a summary + map plot.

    Args:
        args (argparse.Namespace, optional): The command line arguments. Defaults to None.
        config (dict, optional): A dictionary loaded with the application configuration file's contents. Defaults to None.
        vm (_type_, optional): A reference to the orekit virtual machine. Defaults to None.
    """
    aois = loadAois()

    map = folium.Map()

    zones = []
    print(f"loaded {len(aois)} aois")
    for aoi in aois:
        folium.GeoJson(
            data=aoi.to_gdf().to_json(), name=aoi.id, popup=aoi.id, zoom_on_click=True
        ).add_to(map)
        zones.extend(aoi.createBufferedZone())

    print(f"loaded {len(zones)} zones")
    map.save("test.html")

    # todo print the zones

    return 0
