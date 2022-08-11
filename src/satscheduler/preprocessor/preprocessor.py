from dataclasses import dataclass
from pickle import FALSE
from folium import Map

from functools import cached_property
from satscheduler.utils import DateIntervalList, SafeListBuilder
from .linebuilder import LineBuilder
from .nadirtrace import NadirTrace
from satscheduler.aoi import Aoi

from satscheduler.utils import OrekitUtils

from org.hipparchus.ode.events import Action
from org.hipparchus.util import FastMath
from org.orekit.data import DataContext
from org.orekit.models.earth import ReferenceEllipsoid
from org.orekit.propagation import BoundedPropagator
from org.orekit.time import AbsoluteDate
from satscheduler.satellite import CameraSensor, Satellite

from org.orekit.propagation.events import (
    LongitudeCrossingDetector,
    FootprintOverlapDetector,
    GeographicZoneDetector,
)
from org.orekit.propagation.events.handlers import PythonEventHandler

from org.hipparchus.geometry.euclidean.threed import Rotation, Vector3D

import isodate
import numpy as np

# import logging


@dataclass
class WorkItem:
    """
    Work packet describing the satellite to schedule.
    """

    start: AbsoluteDate
    stop: AbsoluteDate
    sat: Satellite
    aoi: list[Aoi]
    map: Map
    schedule = None


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
            # print(f"caught exception in longitude handler: {e}")
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

    def init(self, initialstate, target, detector):
        pass

    def resetState(self, detector, oldState):
        pass

    def eventOccurred(self, s, detector, increasing):
        try:
            if increasing:
                # print(f"exiting {self.__id} at: {s.getDate()}")
                self.__builder.add_stop(s)
            else:
                # print(f"entering {self.__id} at {s.getDate()}")
                self.__builder.add_start(s)
            return Action.CONTINUE
        except BaseException as e:
            # print(f"Caught exception {e}")
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
    sat: Satellite
    ephemeris: BoundedPropagator
    aois: tuple[PreprocessedAoi]


class Preprocessor:
    def __init__(
        self,
        item: WorkItem,
        centralBody: ReferenceEllipsoid = None,
        context: DataContext = None,
        step: str = "PT10M",
    ):
        self.__item = item
        self.__centralBody = centralBody
        self.__context = context
        self.__step = step

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

    @property
    def workItem(self) -> WorkItem:
        return self.__item

    @cached_property
    def stepSeconds(self) -> str:
        return isodate.parse_duration(self.__step).total_seconds()

    def __call__(self) -> PreprocessingResult:
        """Execute a schedule work item."""
        # initialize the satellite
        self.workItem.sat.init(context=self.context, earth=self.centralBody)

        propagator = self.workItem.sat.propagator

        stepSeconds = self.stepSeconds

        print(
            f"starting work for {self.workItem.sat.id} over timespan {self.workItem.start} to {self.workItem.stop}"
        )

        # set the propagator at the start time before we do anything else
        print("initially propagating")
        propagator.propagate(self.workItem.start)

        generator = propagator.getEphemerisGenerator()

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

        sensor_idx = 0
        sensor = self.workItem.sat.getSensor(sensor_idx)
        fov = sensor.createFovInBodyFrame()

        # register aoi detectors
        handlers = []
        for aoi in self.workItem.aoi.aois:
            handler = AoiHandler(
                aoi=aoi,
                sat=self.workItem.sat,
                sensor=sensor,
                builder=SafeListBuilder(self.workItem.start, self.workItem.stop),
            )
            handlers.append(handler)

            print(f"registring for aoi: {aoi.id}")
            if aoi.size < 500:
                propagator.addEventDetector(
                    FootprintOverlapDetector(
                        fov, self.centralBody, aoi.zone, 10000.0
                    ).withHandler(handler)
                )
            else:
                print(f"simplifying complex aoi {aoi.id} (boundarySize={aoi.size})")
                simplified = aoi.simplify()
                print(
                    f"simplifed aoi {aoi.id} (origBoundarySize={aoi.size}, simplifiedSize={simplified.size}"
                )

                propagator.addEventDetector(
                    FootprintOverlapDetector(
                        fov, self.centralBody, simplified.zone, 10000.0
                    ).withHandler(handler)
                )

        print("computing prop time")
        # do the work
        propTime = self.workItem.stop.durationFrom(self.workItem.start)
        elapsed = 0.0

        print("propagating over time")
        while elapsed <= propTime:
            t = self.workItem.start.shiftedBy(elapsed)
            try:
                state = propagator.propagate(t)
                # nadirTracer.addState(state)

                # if activityBuilder.isInActivity:
                #    activityBuilder.addState(state)

                elapsed += stepSeconds
            except BaseException as e:
                print(
                    f"Caught exception processing sat {self.workItem.sat.id} at time {t}: {e}"
                )
                raise e

        """
        nadirLine.finished()
        if not "show" in item.sat.groundTraceConfig or item.sat.groundTraceConfig["show"]:
            for l in nadirLine:
                l.add_to(item.map)

        for a in activityBuilder.activities:
            if not a.footprint is None:
                a.add_to(item.map, color="red")
        """

        print(f"completed work for {self.workItem.sat.id}")
        return PreprocessingResult(
            ephemeris=generator.getGeneratedEphemeris(),
            sat=self.workItem.sat,
            aois=tuple(h.result() for h in handlers),
        )
