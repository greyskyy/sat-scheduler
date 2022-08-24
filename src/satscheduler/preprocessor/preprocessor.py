from dataclasses import dataclass
from datetime import timedelta
from typing import Iterable

from functools import cached_property
from satscheduler.utils import DateIntervalList, SafeListBuilder, DateInterval
from .linebuilder import LineBuilder
from .nadirtrace import NadirTrace
from satscheduler.aoi import Aoi

from satscheduler.utils import OrekitUtils, EphemerisGenerator

from org.hipparchus.ode.events import Action
from org.hipparchus.util import FastMath
from org.orekit.data import DataContext
from org.orekit.models.earth import ReferenceEllipsoid
from org.orekit.propagation import BoundedPropagator, Propagator
from org.orekit.time import AbsoluteDate
from satscheduler.satellite import CameraSensor, Satellite, ScheduleableSensor

from org.orekit.propagation.events import (
    LongitudeCrossingDetector,
    FootprintOverlapDetector,
    GeographicZoneDetector,
)
from org.orekit.propagation.events.handlers import PythonEventHandler

from org.hipparchus.geometry.euclidean.threed import Rotation, Vector3D

import logging
import isodate
import numpy as np


@dataclass(frozen=True)
class PreprocessedAoi:
    aoi: Aoi
    sat: Satellite
    sensor: CameraSensor
    intervals: DateIntervalList


class LongitudeWrapHandler(PythonEventHandler):
    """Orbit event handler, detecting a wrap around at 180 degrees longitude.

    This handler is used to split the nadir trace, so that it draws properly
    on the folium map.
    """

    def __init__(self, tracer: NadirTrace):
        """Class constructor

        Args:
            tracer (NadirTrace): The nadir tracer recording the sub-satellite point.
        """
        super().__init__()
        self.__tracer = tracer

    def init(self, initialstate, target, detector):
        pass

    def resetState(self, detector, oldState):
        pass

    def eventOccurred(self, s, detector, increasing):
        try:
            self.__tracer.addStateAndNewline(s)
            return Action.CONTINUE
        except BaseException as e:
            logging.getLogger(self.__class__.__name__).exception(
                "Caught exception in longitude handler.", exc_info=e
            )
            raise e


"""
class OrbitHandler(PythonEventHandler):
    def __init__(self):
        super().__init__()
        self.__times = []
      
    def init(self, initialstate, target, detector):
        pass

    def resetState(self, detector, oldState):
        pass
    
    def eventOccurred(self, s, detector, increasing):
        if increasing:
            self.__times.append(s.getDate())
        return Action.CONTINUE
    
    @property
    def 
"""


class AoiHandler(PythonEventHandler):
    """Orbit event handler, handling events when the payload comes into view of an aoi."""

    def __init__(
        self,
        aoi: Aoi,
        sat: Satellite,
        sensor: CameraSensor,
        builder: SafeListBuilder = None,
    ):
        super().__init__()
        self.__aoi = aoi
        self.__sat = sat
        self.__sensor = sensor
        self.__builder = builder if builder else SafeListBuilder()
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


@dataclass(frozen=True)
class PreprocessingResult:
    sensor: ScheduleableSensor
    sat: Satellite
    ephemeris: BoundedPropagator
    aois: tuple[PreprocessedAoi]


class Preprocessor:
    def __init__(
        self,
        interval: DateInterval,
        sat: Satellite,
        aois: Iterable[Aoi],
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
            self.__centralBody = OrekitUtils.referenceEllipsoid(
                "wgs84",
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
        return logging.getLogger(self.__class__.__name__)

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

        propagator = self.sat.propagator

        self.logger.critical(
            "Starting work for %s over timespan %s ", self.sat.id, self.interval
        )
        
        generator = EphemerisGenerator(propagator)

        # set the propagator at the start time before we do anything else
        ephemerisInterval = self.interval.pad(timedelta(minutes=5))
        
        # propagate the initial period
        generator.propagate(DateInterval(ephemerisInterval.start, self.interval.start), self.stepSeconds)

        
        #ephemeris = EphemerisGenerator.generate(propagator, ephemerisInterval, step=self.stepSeconds)

        
        """ move to a graphics component
        print("registring for events")
        # register an event detector to avoid line wrapping on the map
        nadirLine = LineBuilder(
            **(
                {"tooltip": item.sat.name, "color": item.sat.displayColor}
                | item.sat.groundTraceConfig
            )
        )
        nadirTracer = NadirTrace(centralBody, nadirLine)
        propagator.addEventDetector(
            LongitudeCrossingDetector(centralBody, FastMath.PI).withHandler(
                LongitudeWrapHandler(nadirTracer)
            )
        )
        """

        # register aoi detectors per sensor
        handlers = []
        count = 0
        # for sensor in self.sat.sensors:
        #    fov = sensor.createFovInBodyFrame()

        sensor_idx = 0
        sensor = self.sat.sensors[sensor_idx]
        fov = sensor.createFovInBodyFrame()

        # register aoi detectors
        handlers = []
        count = 0
        for aoi in self.aois:
            handler = AoiHandler(
                aoi=aoi,
                sat=self.sat,
                sensor=sensor,
                builder=SafeListBuilder(self.interval.start, self.interval.stop),
            )
            handlers.append(handler)

            try:
                self.logger.debug("Registring for aoi: %s", aoi.id)
                for zone in aoi.createZones():
                    propagator.addEventDetector(
                        FootprintOverlapDetector(
                            fov, self.centralBody, zone, 10000.0
                        ).withHandler(handler)
                    )
            except BaseException as e:
                self.logger.warning(
                    "Caught exception building zones, skipping %s", aoi.id, exc_info=e
                )

            count = count + 1
            if test_mode and count > 10:
                break

        generator.propagate(self.interval, self.stepSeconds)
        #self._propagate(propagator)
        """
        # do the work
        propTime = self.interval.stop.durationFrom(self.interval.start)
        elapsed = 0.0

        self.logger.debug("Propagating over time")
        while elapsed <= propTime:
            t = self.interval.start.shiftedBy(elapsed)
            try:
                state = propagator.propagate(t)
                # nadirTracer.addState(state)

                # if activityBuilder.isInActivity:
                #    activityBuilder.addState(state)

                elapsed += stepSeconds
            except BaseException as e:
                self.logger.exception("Caught exception processing sat=%s at time %s.", self.sat.id, t.toString(), exc_info=e)
                raise e
        """
        """
        nadirLine.finished()
        if not "show" in item.sat.groundTraceConfig or item.sat.groundTraceConfig["show"]:
            for l in nadirLine:
                l.add_to(item.map)

        for a in activityBuilder.activities:
            if not a.footprint is None:
                a.add_to(item.map, color="red")
        """

        propagator.clearEventsDetectors()
        generator.propagate(DateInterval(self.interval.stop, ephemerisInterval.stop), self.stepSeconds)

        self.logger.info("Completed work for %s", self.sat.id)
        self.__last_result = PreprocessingResult(
            ephemeris=generator.build(),
            sat=self.sat,
            aois=tuple(h.result() for h in handlers),
            sensor=None,
        )
        return self.__last_result

    def _init_propagator(self, propagator: Propagator, ivl: DateInterval = None):
        if ivl is None:
            ivl = self.interval
        self.logger.debug("Initially propagating to %s", ivl.start.toString())
        propagator.propagate(ivl.start)

    def _propagate(self, propagator: Propagator, ivl: DateInterval = None):
        if ivl is None:
            ivl = self.interval

        propTime = ivl.duration_secs
        elapsed = 0.0

        self.logger.debug("Propagating over time")
        steps = 0
        while elapsed <= propTime:
            t = ivl.start.shiftedBy(elapsed)
            try:
                propagator.propagate(t)
                elapsed += self.stepSeconds
            except BaseException as e:
                self.logger.exception(
                    "Caught exception processing sat=%s at time %s.",
                    self.sat.id,
                    t.toString(),
                    exc_info=e,
                )
                raise e
            steps = steps + 1

        print(f"propagated {steps} steps by {self.stepSeconds} seconds")
