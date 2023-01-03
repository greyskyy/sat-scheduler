"""Scheduling preprocessor. Load AOI and satellite ephemeris, then compute inviews."""
import astropy.units as u
import logging
import datetime as dt
import orekit
import orekitfactory.factory
import orekitfactory.time

from org.hipparchus.geometry.euclidean.threed import Vector3D
from org.hipparchus.ode.events import Action
from org.orekit.geometry.fov import FieldOfView
from org.orekit.propagation.events import (
    EventDetector,
    FootprintOverlapDetector,
    GeographicZoneDetector,
)
from org.orekit.propagation.events.handlers import PythonEventHandler
from org.orekit.time import AbsoluteDate

from ..aoi import Aoi
from ..models import CameraSensorModel, SatelliteModel, SensorModel, Platform
from ..models.detectors import BoresightSunElevationDetector, IntervalBuilderEventHandler
from ..utils import EphemerisGenerator, get_reference_ellipsoid

from .core import PreprocessedAoi, PreprocessingResult, UnitOfWork

__logger = None


def _get_logger() -> logging.Logger:
    global __logger
    if __logger is None:
        __logger = logging.getLogger(__name__)
    return __logger


class AoiHandler(PythonEventHandler):
    """Orbit event handler, handling events when the payload comes into view of an aoi."""

    def __init__(
        self,
        aoi: Aoi,
        sat: SatelliteModel,
        sensor: CameraSensorModel,
        builder: orekitfactory.time.DateIntervalListBuilder = None,
    ):
        """Class constructor.

        Args:
            aoi (Aoi): The AOI being handled.
            sat (Satellite): The satellite being processed.
            sensor (CameraSensor): The sensor details
            builder (DateIntervalListBuilder, optional): The list builder to use when
            constructing the class. Defaults to None.
        """
        super().__init__()
        self.__aoi = aoi
        self.__sat = sat
        self.__sensor = sensor
        self.__builder = builder if builder else orekitfactory.time.DateIntervalListBuilder()
        self.__logger = logging.getLogger(__name__)

    def init(self, initialstate, target, detector):
        """Initialize the handler.

        Args:
            initialstate (SpacecraftState): The spacecraft state.
            target (Any): The target.
            detector (Any): The detector.
        """
        pass

    def resetState(self, detector, oldState):
        """Reset the state.

        Args:
            detector (Any): The detector.
            oldState (Any): The old state.
        """
        pass

    def eventOccurred(self, s, detector, increasing):
        """Process an event.

        Args:
            s (SpacecraftState): Thg spacecraft state at time of event.
            detector (EventDetector): The detector triggering the event.
            increasing (bool): Whether the value is increasing or decreasing.

        Returns:
            _type_: _description_
        """
        if increasing:
            self.__logger.debug("Exiting aoi=%s at %s", self.__aoi.id, s.getDate())
            self.__builder.add_stop(s.getDate())
        else:
            self.__logger.debug("Entering aoi=%s at %s", self.__aoi.id, s.getDate())
            self.__builder.add_start(s.getDate())
        return Action.CONTINUE

    def result(self) -> PreprocessedAoi:
        """Transform the data into the result object.

        Returns:
            PreprocessedAoi: The processed aoi.
        """
        return PreprocessedAoi(
            aoi=self.__aoi,
            sat=self.__sat,
            sensor=self.__sensor,
            intervals=self.__builder.build_list(),
        )


def _register_detector(uow: UnitOfWork, sensor: SensorModel, fov: FieldOfView, zone, handler: AoiHandler, aoi: Aoi):
    _get_logger().debug("Registring for aoi: %s %s", aoi.id, aoi.country)
    try:
        detector: EventDetector = None

        log_func = _get_logger().debug  # set here to adjust level after errors
        if not sensor.data.useNadirPointing and sensor.has_fov:
            _get_logger().debug("building footprint-zone detector for sensor=%s", sensor.id)
            sample_dist = 20000.0
            tries = 4
            while tries > 0:
                try:
                    _get_logger().debug("creating detector with sample_dist=%f", sample_dist)
                    detector = FootprintOverlapDetector(fov, uow.centralBody, zone, float(sample_dist))
                    break
                except BaseException:
                    tries -= 1
                    sample_dist *= 2

                    if tries <= 0:
                        log_func = _get_logger().warning
                    log_func(
                        "Caught and error building footprint detector [aoi=%s, country=%s, sensor=%s]",
                        aoi.id,
                        aoi.country,
                        sensor.id,
                        exc_info=1,
                    )

        if not detector:
            log_func("building nadir-zone detector for aoi=%s, country=%s, sensor=%s", aoi.id, aoi.country, sensor.id)
            detector = GeographicZoneDetector(uow.centralBody, zone, 1.0e-6)

        detector = detector.withHandler(handler).withMaxCheck(60.0)

        uow.sat.propagator.addEventDetector(detector)

    except orekit.JavaError:
        _get_logger().error(
            "Caught exception while building footprint detector for aoi %s (%s) with area %f",
            aoi.id,
            aoi.country,
            aoi.area,
            exc_info=1,
        )


def preprocess(uow: UnitOfWork) -> PreprocessingResult:
    """Execute preprocessing.

    Args:
        test_mode (bool, optional): Indicate to run in 'test' mode. Defaults to False.

    Returns:
        PreprocessingResult: Results of preprocessing.
    """
    _get_logger().info("Starting work for %s over timespan %s ", uow.sat.id, uow.interval)

    if uow.interval.duration <= dt.timedelta(seconds=0):
        raise RuntimeError("Cannot preprocess over an invalid duration.")

    generator = EphemerisGenerator(uow.sat.propagator)

    # set the propagator at the start time before we do anything else
    ephemerisInterval = uow.interval.pad(dt.timedelta(minutes=5))

    # enable ephemeris event list generation
    uow.sat.enable_event_generation()

    # propagate the initial period
    generator.propagate(orekitfactory.time.DateInterval(ephemerisInterval.start, uow.interval.start), uow.step)

    # filter sensors if necessary and build fields of view
    sensors = tuple((uow.sat.sensor(id) for id in uow.sensor_ids) if uow.sensor_ids else uow.sat.sensors)
    fovs = {s.id: s.createFovInBodyFrame() for s in sensors}

    sensor_constraint_handlers: dict[str:PythonEventHandler] = {}
    for s in sensors:
        if s.data.min_sun_elevation is not None:
            boresight = s.sensorToBodyTxProv.getStaticTransform(AbsoluteDate.ARBITRARY_EPOCH).transformVector(
                Vector3D.PLUS_K
            )
            handler = IntervalBuilderEventHandler()
            uow.sat.propagator.addEventDetector(
                BoresightSunElevationDetector(
                    boresight_in_sat=boresight,
                    body=get_reference_ellipsoid(uow.context),
                    sun=uow.context.getCelestialBodies().getSun(),
                    min_elevation=float(s.data.min_sun_elevation.to_value(u.rad)),
                ).withHandler(handler)
            )
            sensor_constraint_handlers[s.id] = handler

    # register aoi detectors per sensor
    handlers: list[AoiHandler] = []
    count = 0
    for aoi in uow.aois:
        _get_logger().debug("Building handlers for %s", aoi.id)
        zone = aoi.createZone()
        if not zone:
            _get_logger().debug("skipping aoi without zone aoi.id=%s", aoi.id)
            continue

        for sensor in sensors:
            fov = fovs[sensor.id]

            handler = AoiHandler(
                aoi=aoi,
                sat=uow.sat,
                sensor=sensor,
                builder=orekitfactory.time.DateIntervalListBuilder(uow.interval.start, uow.interval.stop),
            )
            handlers.append(handler)

            _register_detector(uow, sensor, fov, zone, handler, aoi)

        count = count + 1
        if uow.test_mode and count > 10:
            break

    _get_logger().info("propagating interval %s", uow.interval)
    generator.propagate(uow.interval, uow.step.total_seconds())

    uow.sat.propagator.clearEventsDetectors()
    generator.propagate(orekitfactory.time.DateInterval(uow.interval.stop, ephemerisInterval.stop), uow.step)

    constraint_intervals: dict[str, orekitfactory.time.DateIntervalList] = {
        k: v.get_results(uow.interval) for k, v in sensor_constraint_handlers.items()
    }

    aois = []
    for h in handlers:
        r = h.result()
        if r.sensor.id in constraint_intervals:
            aois.append(
                PreprocessedAoi(
                    aoi=r.aoi,
                    sat=r.sat,
                    sensor=r.sensor,
                    intervals=orekitfactory.time.list_intersection(r.intervals, constraint_intervals[r.sensor.id]),
                )
            )
        else:
            aois.append(r)

    _get_logger().info("Completed work for %s", uow.sat.id)
    return PreprocessingResult(
        platform=Platform(ephemeris=generator.build(atProv=uow.sat.getAttitudeProvider("mission")), model=uow.sat),
        aois=tuple(aois),
        interval=uow.interval,
    )
