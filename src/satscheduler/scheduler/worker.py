from dataclasses import dataclass
from folium import Map
from .linebuilder import LineBuilder
from orekithelpers import referenceEllipsoid
from .nadirtrace import NadirTrace
from aoi import AoiCollection

from schedule.payload_activity import PayloadActivityBuilder, PayloadActivity

from org.hipparchus.ode.events import Action
from org.hipparchus.util import FastMath
from org.orekit.data import DataContext
from org.orekit.models.earth import ReferenceEllipsoid
from org.orekit.time import AbsoluteDate
from satellite import Satellite

from org.orekit.propagation.events import LongitudeCrossingDetector, FootprintOverlapDetector, GeographicZoneDetector
from org.orekit.propagation.events.handlers import PythonEventHandler

from org.hipparchus.geometry.euclidean.threed import Rotation, Vector3D

import isodate
import numpy as np

#import logging

@dataclass
class WorkItem:
    """
    Work packet describing the satellite to schedule.
    """
    start:AbsoluteDate
    stop:AbsoluteDate
    sat:Satellite
    aoi:AoiCollection
    map:Map
    schedule=None

class LongitudeWrapHandler(PythonEventHandler):
    """Orbit event handler, detecting a wrap around at 180 degrees longitude.
    
    This handler is used to split the nadir trace, so that it draws properly
    on the folium map.
    """
    def __init__(self, tracer:NadirTrace):
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
            print(f"caught exception in longitude handler: {e}")
            raise e

'''
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
'''
class AoiHandler(PythonEventHandler):
    """Orbit event handler, handling events when the payload comes into view of an aoi."""
    def __init__(self, id:str, builder:PayloadActivityBuilder):
        super().__init__()
        self.__id = id
        self.__builder = builder
    
    def init(self, initialstate, target, detector):
        pass

    def resetState(self, detector, oldState):
        pass
    
    def eventOccurred(self, s, detector, increasing):
        try:
            if increasing:
                print(f"exiting {self.__id} at: {s.getDate()}")
                self.__builder.stopActivity(s)
            else:
                print(f"entering {self.__id} at {s.getDate()}")
                self.__builder.startActivity(s)
            return Action.CONTINUE
        except BaseException as e:
            print(f"Caught exception {e}")
            raise e

def schedule(item:WorkItem, centralBody:ReferenceEllipsoid=None, context:DataContext=None, step:str="PT10M"):
    """Execute a schedule work item.

    Args:
        item (WorkItem): _description_
        centralBody (ReferenceEllipsoid, optional): _description_. Defaults to None.
        context (DataContext, optional): _description_. Defaults to None.
        step (str, optional): _description_. Defaults to "PT10M".
    """
    if context is None:
        context = DataContext.getDefault()
        
    if centralBody is None:
        centralBody = referenceEllipsoid("wgs84", frameName="itrf", simpleEop=False, iersConventions="iers2010")
    
    # initialize the satellite
    item.sat.init(context=context)
    
    propagator = item.sat.propagator
    
    stepSeconds = isodate.parse_duration(step).total_seconds()
    
    print(f"starting work for {item.sat.id} over timespan {item.start} to {item.stop}")
    
    #set the propagator at the start time before we do anything else
    print("initially propagating")
    propagator.propagate(item.start)
    
    print("registring for events")
    # register an event detector to avoid line wrapping on the map
    nadirLine = LineBuilder(**({'tooltip':item.sat.name, 'color': item.sat.displayColor} | item.sat.groundTraceConfig))
    nadirTracer = NadirTrace(centralBody, nadirLine)
    propagator.addEventDetector(LongitudeCrossingDetector(centralBody, FastMath.PI).withHandler(LongitudeWrapHandler(nadirTracer)))
    
    sensor = item.sat.getSensor()
    fov = sensor.createFovInBodyFrame()
    
    # build the payload activities
    activityBuilder = PayloadActivityBuilder(fov, centralBody)
    
    # register aoi detectors
    for aoi in item.aoi.aois:
        print(f"registring for aoi: {aoi.id}")
        if aoi.size < 500:
            propagator.addEventDetector(FootprintOverlapDetector(fov, centralBody, aoi.zone, 10000.).withHandler(AoiHandler(aoi.id, activityBuilder)))
        else:
            print(f"simplifying complex aoi {aoi.id} (boundarySize={aoi.size})")
            simplified = aoi.simplify()
            print(f"simplifed aoi {aoi.id} (origBoundarySize={aoi.size}, simplifiedSize={simplified.size}")
            
            propagator.addEventDetector(FootprintOverlapDetector(fov, centralBody, simplified.zone, 10000.).withHandler(AoiHandler(aoi.id, activityBuilder)))
        
    print("computing prop time")
    # do the work
    propTime = item.stop.durationFrom(item.start)
    elapsed = 0.
    
    print("propagating over time")
    while elapsed <= propTime:
        t = item.start.shiftedBy(elapsed)
        try:
            state = propagator.propagate(t)
            nadirTracer.addState(state)
            
            if activityBuilder.isInActivity:
                activityBuilder.addState(state)
            
            elapsed += stepSeconds
        except BaseException as e:
            print(f"Caught exception processing sat {item.sat.id} at time {t}: {e}")
            raise e
    
    nadirLine.finished()
    if not 'show' in item.sat.groundTraceConfig or item.sat.groundTraceConfig['show']:
        for l in nadirLine:
            l.add_to(item.map)
    
    for a in activityBuilder.activities:
        if not a.footprint is None:
            a.add_to(item.map, color='red')
    
    print(f"completed work for {item.sat.id}")