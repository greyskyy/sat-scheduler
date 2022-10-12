"""Load the configuration."""
import argparse
import logging
import yaml

config = {}
"""Global configuration."""


def add_args(parser: argparse.ArgumentParser):
    """Pyrebar pre-init hook to add the config-file command line parameter.

    Args:
        parser (argparse.ArgumentParser): The command line parser.
    """
    parser.add_argument(
        "-c",
        "--config",
        help="Path to the configuration yaml file",
        dest="config",
        type=str,
        default="config.yaml",
    )


def load_config(args: argparse.Namespace):
    """Py-rebar post-init hook to load the configuration file.

    Args:
        args (argparse.Namespace): _description_
    """
    global config
    logger = logging.getLogger(__name__)
    if "config" in args:
        try:
            with open(args.config, "r") as file:
                config = yaml.safe_load(file)
                logger.info("Loaded configuration file path=%s", args.config)
        except:
            logger.warn("Failed to load configuration path=%s", args.config, exc_info=1)
            config = {}
    else:
        logger.warn("No configuration file found in command line arguments.")


def get_config() -> dict:
    global config
    return config
