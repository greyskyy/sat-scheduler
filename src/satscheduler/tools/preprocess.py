"""Execute the pre-processor, provide stats on results."""
import argparse
from datetime import timedelta
from functools import reduce
import satscheduler.preprocessor as pre_processor

import logging

import folium
import orekitfactory.initializer

from ..configuration import get_config

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
        "--test", help="Run in test-mode.", action="store_true", default=False
    )


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
