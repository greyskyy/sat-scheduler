"""Scheduling preprocessor. Load AOI and satellite ephemeris, then compute inviews."""
import logging
import isodate
import math
import numpy as np
import orekit
import orekitfactory.factory


from dataclasses import dataclass
from datetime import timedelta
from functools import cached_property
from typing import Iterable

from orekitfactory.time import DateIntervalList, DateIntervalListBuilder, DateInterval

from org.hipparchus.geometry.euclidean.threed import Rotation, Vector3D
from org.hipparchus.ode.events import Action
from org.hipparchus.util import FastMath
from org.orekit.data import DataContext
from org.orekit.models.earth import ReferenceEllipsoid
from org.orekit.propagation import BoundedPropagator, Propagator
from org.orekit.propagation.events import FootprintOverlapDetector
from org.orekit.propagation.events.handlers import PythonEventHandler
from org.orekit.time import AbsoluteDate

from ..aoi import Aoi
from ..satellite import CameraSensor, Satellite, ScheduleableSensor
from ..utils import EphemerisGenerator


@dataclass(frozen=True)
class PreprocessedAoi:
    """Preprocessing result for a single AOI."""

    aoi: Aoi
    sat: Satellite
    sensor: CameraSensor
    intervals: DateIntervalList


@dataclass(frozen=True)
class PreprocessingResult:
    """Result of preprocessing a single satellite/sensor pair."""

    sensor: ScheduleableSensor
    sat: Satellite
    ephemeris: BoundedPropagator
    aois: tuple[PreprocessedAoi]


class AoiHandler(PythonEventHandler):
    """Orbit event handler, handling events when the payload comes into view of an aoi."""

    def __init__(
        self,
        aoi: Aoi,
        sat: Satellite,
        sensor: CameraSensor,
        builder: DateIntervalListBuilder = None,
    ):
        super().__init__()
        self.__aoi = aoi
        self.__sat = sat
        self.__sensor = sensor
        self.__builder = builder if builder else DateIntervalListBuilder()
        self.__logger = logging.getLogger(self.__class__.__name__)

    def init(self, initialstate, target, detector):
        pass

    def resetState(self, detector, oldState):
        pass

    def eventOccurred(self, s, detector, increasing):
        try:
            if increasing:
                self.__logger.debug("Exiting aoi=%s at %s", self.__aoi.id, s.getDate())
                self.__builder.add_stop(s.getDate())
            else:
                self.__logger.debug("Entering aoi=%s at %s", self.__aoi.id, s.getDate())
                self.__builder.add_start(s.getDate())
            return Action.CONTINUE
        except BaseException as e:
            self.__logger.exception(
                "Caught exception processing aoi=%s", self.__aoi.id, exc_info=e
            )
            raise e

    def result(self) -> PreprocessedAoi:
        return PreprocessedAoi(
            aoi=self.__aoi,
            sat=self.__sat,
            sensor=self.__sensor,
            intervals=self.__builder.build_list(),
        )


class Preprocessor:
    """Satellite scheduler pre-processor.

    Execute this callable to run preprocessing for a single satellite.
    """

    def __init__(
        self,
        interval: DateInterval,
        sat: Satellite,
        aois: Iterable[Aoi],
        sensor_id: str = None,
        centralBody: ReferenceEllipsoid = None,
        context: DataContext = None,
        step: str = "PT10M",
    ):
        self.__interval = interval
        self.__sat = sat
        self.__aois = tuple(aois)
        self.__centralBody = centralBody
        self.__context = context
        self.__step = step or "PT10M"
        self.__last_result = None
        self.__sensor_id = sensor_id

    @property
    def sat(self) -> Satellite:
        return self.__sat

    @property
    def interval(self) -> DateInterval:
        return self.__interval

    @property
    def aois(self) -> tuple[Aoi]:
        return self.__aois

    @property
    def context(self) -> DataContext:
        if not self.__context:
            self.__context = DataContext.getDefault()
        return self.__context

    @property
    def centralBody(self) -> ReferenceEllipsoid:
        if not self.__centralBody:
            self.__centralBody = orekitfactory.factory.get_reference_ellipsoid(
                model="wgs84",
                frameName="itrf",
                simpleEop=False,
                iersConventions="iers2010",
                context=self.context,
            )
        return self.__centralBody

    @cached_property
    def stepSeconds(self) -> float:
        return float(isodate.parse_duration(self.__step).total_seconds())

    @cached_property
    def logger(self) -> logging.Logger:
        return logging.getLogger(__name__)

    @property
    def last_result(self) -> PreprocessingResult:
        """The result of the last time this preprocessor was executed.

        Returns:
            PreprocessingResult: The last result, or None if this object hasn't been executed.
        """
        return self.__last_result

    def __call__(self, test_mode: bool = False) -> PreprocessingResult:
        """Exeucte this preprocessor."""
        # initialize the satellite
        self.logger.info("Initializing satellite %s", self.sat.id)
        self.sat.init(context=self.context, earth=self.centralBody)

        self.logger.info(
            "Starting work for %s over timespan %s ", self.sat.id, self.interval
        )

        generator = EphemerisGenerator(self.sat.propagator)

        # set the propagator at the start time before we do anything else
        ephemerisInterval = self.interval.pad(timedelta(minutes=5))

        # propagate the initial period
        generator.propagate(
            DateInterval(ephemerisInterval.start, self.interval.start), self.stepSeconds
        )

        # filter sensors if necessary
        sensors = (
            [self.sat.sensor(self.__sensor_id)]
            if self.__sensor_id
            else self.sat.sensors
        )
        fovs = {s.id: s.createFovInBodyFrame() for s in sensors}

        # register aoi detectors per sensor
        handlers = []
        count = 0
        for aoi in self.aois:
            zone = aoi.createZone()
            if not zone:
                self.logger.debug("skipping aoi without zone aoi.id=%s", aoi.id)
                continue
            
            sample_dist = math.floor(math.sqrt(aoi.area / 1000))
            sample_dist = 10000.0 if sample_dist < 10000. else sample_dist

            for sensor in sensors:
                fov = fovs[sensor.id]

                handler = AoiHandler(
                    aoi=aoi,
                    sat=self.sat,
                    sensor=sensor,
                    builder=DateIntervalListBuilder(
                        self.interval.start, self.interval.stop
                    ),
                )
                handlers.append(handler)

                self.logger.debug("Registring for aoi: %s", aoi.id)

                try:
                    self.sat.propagator.addEventDetector(
                        FootprintOverlapDetector(
                            fov, self.centralBody, zone, float(sample_dist)
                        ).withHandler(handler)
                    )
                except orekit.JavaError:
                    self.logger.error("Caught exception while building footprint detector for aoi %s with area %f", aoi.id, aoi.area)

            count = count + 1
            if test_mode and count > 10:
                break

        generator.propagate(self.interval, self.stepSeconds)

        self.sat.propagator.clearEventsDetectors()
        generator.propagate(
            DateInterval(self.interval.stop, ephemerisInterval.stop), self.stepSeconds
        )

        self.logger.info("Completed work for %s", self.sat.id)
        self.__last_result = PreprocessingResult(
            ephemeris=generator.build(),
            sat=self.sat,
            aois=tuple(h.result() for h in handlers),
            sensor=None,
        )
        return self.__last_result
