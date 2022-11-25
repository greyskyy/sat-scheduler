"""Load the configuration."""
import argparse
import logging
import yaml

from .dataclasses import Configuration

config: Configuration = None
"""Global configuration."""

raw_config: dict = {}
"""Raw data configuration."""


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
        args (argparse.Namespace): the parsed command line arguments
    """
    global raw_config
    logger = logging.getLogger(__name__)
    if "config" in args:
        try:
            with open(args.config, "r") as file:
                raw_config = yaml.safe_load(file)
                logger.info("Loaded configuration file path=%s", args.config)
        except BaseException:
            logger.warn("Failed to load configuration path=%s", args.config, exc_info=1)
            raw_config = {}
    else:
        logger.warn("No configuration file found in command line arguments.")


def get_config() -> Configuration:
    """Retrieve the global application configuration, as loaded from the config file.

    Returns:
        configuration: The configuration.
    """
    global config

    if config is None:
        config = Configuration.from_dict(get_raw_config())

    return config


def get_raw_config() -> dict:
    """Retrieve the global application configuration, as the raw dictionary loaded from the config file.

    Returns:
        dict: The configuration dictionary.
    """
    global raw_config
    return raw_config
