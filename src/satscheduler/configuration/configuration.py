"""Load the configuration."""
import argparse
import logging
import yaml

from .core import Configuration

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


def load_config(args: argparse.Namespace = None, file: str = None):
    """Py-rebar post-init hook to load the configuration file.
    
    Either args or file must be specified.

    Args:
        args (argparse.Namespace, optional): the parsed command line arguments
        file (str, optional): The configuration file path.
    """
    global raw_config
    logger = logging.getLogger(__name__)

    if (args is None or "config" not in args) and file is None:
        raise ValueError("No configuration file path specified.")
    
    if not file and "config" in args:
        file = args.config

    try:
        with open(args.config, "r") as file:
            set_config(yaml.safe_load(file))
            logger.info("Loaded configuration file path=%s", args.config)
    except BaseException:
        logger.warn("Failed to load configuration path=%s", args.config, exc_info=1)
        set_config({})


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


def set_config(value: dict|Configuration):
    """Assign the raw configuration dictionary.

    Args:
        value (dict|Configuration): The configuration data.
    """
    global raw_config
    global config
    
    if isinstance(value, Configuration):
        config = value
        raw_config = None
    else:
        raw_config = value
        config = None    
