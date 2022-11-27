"""Validate the configuration files."""
import logging
from .configuration import get_config
from ..models import load_satellite_models

SUBCOMMAND = "check-config"
ALIASES = ["check", "config"]
LOGGER_NAME = "satscheduler"


def execute(args=None) -> int:
    """Load the AOIs, generating a summary + map plot.

    Args:
        args (argparse.Namespace, optional): The command line arguments. Defaults to None.

    Returns:
        int: The return code to provide back to the OS.
    """
    logger = logging.getLogger(__name__)
    config = get_config()

    satellites = load_satellite_models()
    filtered = 0
    for id, sat in config.satellites.items():
        if sat.filter:
            filtered += 1

    if len(satellites) == len(config.satellites) - filtered:
        logger.info("loaded %d satellites (filtered %d) successfully", len(satellites), filtered)
    else:
        raise RuntimeError("Failed to correctly load satellites")
    return 0
