"""Preprocessing executor.

Manage the loading and threaded execution of preprocessing across multiple satellites.
"""
from threading import Thread
from typing import Iterable
import satscheduler.aoi as aoi
from satscheduler.preprocessor import Preprocessor, PreprocessingResult
from satscheduler.satellite import Satellites

import logging

from org.orekit.data import DataContext

import orekitfactory.factory
import orekitfactory.utils
import orekitfactory.time


class Worker:
    def __init__(self, vm, callable, test_mode):
        self.vm = vm
        self.callable = callable
        self.test_mode = test_mode

    def __call__(self):
        try:
            self.vm.attachCurrentThread()
            self.callable(self.test_mode)
        except:
            logging.getLogger(__name__).error(
                "Caught exception during pre-processing", exc_info=1, stack_info=True
            )


def run_preprocessing(
    vm, preprocessors: Iterable[Preprocessor] = [], args=None, config=None
) -> list[PreprocessingResult]:
    """Execute the provided preprocessors.

    Execution may occur on multiple threads, or on the same thread, depending on the multithreading configuration.

    Args:
        vm (any): The orekit VM.
        preprocessors (Iterable[Preprocessor], optional): Preprocessors to execute. Defaults to [].
        args (argparse.Namespace, optional): The command line arguments. Defaults to None.
        config (dist, optional): The application configuration. Defaults to None.

    Returns:
        list[PreprocessedAoi]: The preproessing results
    """
    shouldThread = True
    if args and "threading" in args and args.threading is not None:
        shouldThread = args.threading
    elif config and "run" in config and "multithread" in config["run"]:
        shouldThread = config["run"]["multithread"]

    if shouldThread and len(preprocessors) < 2:
        shouldThread = False
        logging.getLogger(__name__).debug(
            "Disabling preprocessing threading for a single preprocessor."
        )

    logging.getLogger(__name__).debug(
        "Executing %d preprocessors [multithreading=%s]",
        len(preprocessors),
        shouldThread,
    )

    if shouldThread:
        threads = []
        for p in preprocessors:
            thread = Thread(target=Worker(vm, p, args.test))
            thread.start()
            threads.append(thread)

        for thread in threads:
            thread.join()
    else:
        for p in preprocessors:
            p(args.test)

    return [p.last_result for p in preprocessors]


def execute(
    args=None, config={}, vm=None, context: DataContext = None
) -> list[PreprocessingResult]:
    """Execute preprocessing.

    This function loads satellites and aois, then executes preprocessing

    Args:
        args (argparse.Namespace, optional): The command line arguments. Defaults to None.
        config (dict, optional): A dictionary loaded with the application configuration file's contents. Defaults to None.
        vm (_type_, optional): A reference to the orekit virtual machine. Defaults to None.
    """
    logger = logging.getLogger(__name__)
    if config is None:
        raise ValueError("config dictionary cannot be none.")

    logger.info("Loading aoi and satellite data.")

    # load the aois
    aois = aoi.loadAois(**config["aois"])
    logger.debug("Loaded %d aois", len(aois))

    # load the satellites
    sats = Satellites.load_from_config(config)
    logger.debug("Loaded %d satellites", len(sats))

    # set context and date interval
    if context is None:
        context = DataContext.getDefault()

    timespan = orekitfactory.time.DateInterval(
        orekitfactory.factory.to_absolute_date(config["run"]["start"], context=context),
        orekitfactory.factory.to_absolute_date(config["run"]["stop"], context=context),
    )

    # load the reference ellipsoid
    if "earth" in config:
        earth = orekitfactory.factory.get_reference_ellipsoid(
            context=context, **(config["earth"])
        )
    else:
        earth = orekitfactory.factory.get_reference_ellipsoid(
            model="wgs-84", context=context
        )

    # create the preprocessors
    step = config["control"]["step"]
    preprocessors = [
        Preprocessor(timespan, sat, aois, centralBody=earth, context=context, step=step)
        for sat in sats
    ]

    logger.info("Executing %d preprocessors.", len(preprocessors))

    # make the donuts
    results = run_preprocessing(
        vm, preprocessors=preprocessors, args=args, config=config
    )

    logger.critical("Preprocessing completed.")
    return results
