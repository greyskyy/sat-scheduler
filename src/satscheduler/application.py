"""Satellite analytics engine."""

import argparse
from typing import Any
import orekit
import yaml

import satscheduler.utils as utils

from inspect import getmembers, isfunction


from satscheduler.dataloader import download
from orekit.pyhelpers import setup_orekit_curdir

import satscheduler.tools as tools


def parseArgs() -> tuple[argparse.Namespace, dict]:
    """Parse commandline arguments.

    Returns:
        argparse.Namespace: the parsed arguments
    """
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-o", "--output", help="Output html file.", type=str, default="index.html"
    )
    parser.add_argument(
        "-c",
        "--config",
        help="path to the configuration yaml file",
        type=str,
        default="config.yaml",
    )
    parser.add_argument(
        "-t",
        "--run-tool",
        help="Run a specific tool (default=scheduler)",
        metavar="tool",
        choices=[m[0] for m in getmembers(tools, isfunction)],
        dest="tool",
    )
    parser.add_argument(
        "--test", help="Run in test-mode.", action="store_true", default=False
    )

    loglevel = parser.add_mutually_exclusive_group()
    loglevel.add_argument(
        "--quiet", action="store_const", const="CRITICAL", dest="loglevel"
    )
    loglevel.add_argument(
        "--terse", action="store_const", const="ERROR", dest="loglevel"
    )
    loglevel.add_argument(
        "--warn", action="store_const", const="WARNING", dest="loglevel"
    )
    loglevel.add_argument("--info", action="store_const", const="INFO", dest="loglevel")
    loglevel.add_argument(
        "--debug", action="store_const", const="DEBUG", dest="loglevel"
    )

    threadgroup = parser.add_mutually_exclusive_group()
    threadgroup.add_argument(
        "--multi-threading",
        action="store_true",
        dest="threading",
        help="Run with multi-threading. Overrides the value set in the config.",
    )
    threadgroup.add_argument(
        "--no-multi-threading",
        action="store_false",
        dest="threading",
        help="Disable multi-threaded processing. Overrides the value set in configuration.",
    )

    args = parser.parse_args()

    with open(args.config, "r") as file:
        config = yaml.safe_load(file)

    return (args, config)


def initOrekit(config):
    """
    Initialize the orekit data, download if necessary.
    """
    filePath = download(config["data"])

    setup_orekit_curdir(filename=filePath)


def runApp(vm=None):
    """Run the specified application.

    Args:
        vm (Any): The orekit vm handle.

    Raises:
        ValueError: When an unknown application is specified.

    Returns:
        _type_: _description_
    """
    if vm is None:
        vm = orekit.initVM()

    (args, config) = parseArgs()

    utils.configure_logging(args.loglevel or "INFO")

    initOrekit(config["orekit"])

    for name, method in getmembers(tools, isfunction):
        if name == args.tool:
            return method(vm=vm, args=args, config=config)

    raise ValueError(f"cannot run unknown tool: {args.tool}")
