from concurrent.futures import process
from datetime import timedelta
from functools import reduce
import satscheduler.aoi as aoi
import satscheduler.preprocessor as pre_processor
from satscheduler.satellite import Satellites

import logging

from satscheduler.utils import DateInterval, string_to_absolutedate, OrekitUtils
from org.orekit.data import DataContext

import folium


def preprocess(args=None, config=None, vm=None):
    """Load the AOIs, generating a summary + map plot.

    Args:
        args (argparse.Namespace, optional): The command line arguments. Defaults to None.
        config (dict, optional): A dictionary loaded with the application configuration file's contents. Defaults to None.
        vm (_type_, optional): A reference to the orekit virtual machine. Defaults to None.
    """
    logger = logging.getLogger(__name__)

    logger.info("Starting preprocessor tool.")

    results = pre_processor.execute(args=args, config=config, vm=vm)

    processed_aois: list[pre_processor.PreprocessedAoi] = []
    for r in results:
        processed_aois.extend(r.aois)

    logger.critical(
        "Preprocessing successfully completed. Loaded %d processed aois.",
        len(processed_aois),
    )

    map = folium.Map()

    zero_count = 0

    for pa in processed_aois:
        sum = reduce(lambda d, ivl: d + ivl.duration, pa.intervals, timedelta())

        if sum.total_seconds():
            print(
                f"aoi {pa.aoi.id} loaded with {len(pa.intervals)} total accesses totalling {sum}."
            )
        else:
            zero_count = zero_count + 1

        folium.GeoJson(
            pa.aoi.to_gdf(), name=pa.aoi.id, popup=pa.aoi.id, zoom_on_click=True
        ).add_to(map)

    logger.critical(
        "After processing, %d/%d aois have no access.", zero_count, len(processed_aois)
    )

    map.save("preprocessed_aoi.html")
