"""Preprocessing executor.

Manage the loading and threaded execution of preprocessing across multiple satellites.
"""
import concurrent.futures
import logging
import orekitfactory.factory
import orekitfactory.initializer
import orekitfactory.time
import orekitfactory.utils
import typing

from .core import PreprocessingResult, UnitOfWork
from .preprocessor import preprocess

from ..aoi import load_aois, Aoi
from ..configuration import Configuration, get_config
from ..models import load_satellite_models, SatelliteModel
from ..utils import maybe_attach_thread

from org.orekit.data import DataContext
from org.orekit.models.earth import ReferenceEllipsoid

_logger: logging.Logger = None


def _get_logger() -> logging.Logger:
    global _logger
    if _logger is None:
        _logger = logging.getLogger(__name__)
    return _logger


def run_units_of_work(
    uows: typing.Sequence[UnitOfWork] = [], args=None, config: Configuration = None
) -> list[PreprocessingResult]:
    """Execute the provided preprocessing units of work.

    Args:
        uows (typing.Sequence[UnitOfWork], optional): _description_. Defaults to [].
        args (_type_, optional): _description_. Defaults to None.
        config (Configuration, optional): _description_. Defaults to None.

    Returns:
        list[PreprocessedAoi]: The preproessing results
    """
    shouldThread = True
    if args and "threading" in args and args.threading is not None:
        shouldThread = args.threading
    elif config and config.run.multithread:
        shouldThread = config.run.multithread

    if shouldThread and len(uows) < 2:
        shouldThread = False
        _get_logger().debug("Disabling preprocessing threading for a single unit of work.")

    _get_logger().debug(
        "Executing %d preprocessing units of work [multithreading=%s]",
        len(uows),
        shouldThread,
    )

    if shouldThread:
        with concurrent.futures.ThreadPoolExecutor(initializer=maybe_attach_thread) as executor:
            futures = [executor.submit(preprocess, uow) for uow in uows]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]
    else:
        results = [preprocess(uow) for uow in uows]

    _get_logger().info("Completed preprocessing for %d units of work", len(uows))
    return results


def create_uows(
    args=None,
    config: Configuration = None,
    aois: typing.Sequence[Aoi] = None,
    sat_models: typing.Sequence[SatelliteModel] = None,
    context: DataContext = None,
    earth: ReferenceEllipsoid = None,
) -> list[UnitOfWork]:
    """Generate a set of proprocessing units of work.

    Args:
        args (argparse.Namespace, optional): Command line arguments. Defaults to None.
        config (Configuration, optional): Application configuration. Defaults to None.

    Returns:
        list[UnitOfWork]: List of preprocessing units of work.
    """
    logger = _get_logger()
    if not config:
        config = get_config()

    if not context:
        context = DataContext.getDefault()

    if not earth:
        earth = orekitfactory.factory.get_reference_ellipsoid(context=context)

    if not aois:
        aois = load_aois(config.aois)
        logger.info("Loaded %d aois", len(aois))

    if not sat_models:
        sat_models = load_satellite_models(config=config, context=context, earth=earth)
        logger.info("Loaded %d satellite models", len(sat_models))

    test_mode = False
    if args and "test" in args:
        test_mode = args.test

    timespan = orekitfactory.time.DateInterval(
        orekitfactory.factory.to_absolute_date(config.run.start, context=context),
        orekitfactory.factory.to_absolute_date(config.run.stop, context=context),
    )

    return [
        UnitOfWork(
            aois=aois,
            interval=timespan,
            sat=sat,
            centralBody=earth,
            context=context,
            step=config.run.step,
            test_mode=test_mode,
        )
        for sat in sat_models
    ]
