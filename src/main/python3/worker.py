from dataclasses import dataclass
from folium import Map, PolyLine
from matplotlib import fontconfig_pattern
from linebuilder import LineBuilder
from orekithelpers import referenceEllipsoid
from nadirtrace import NadirTrace
from aoi import AoiCollection
from payload_activity import PayloadActivityBuilder, PayloadActivity

from org.hipparchus.ode.events import Action
from org.hipparchus.util import FastMath
from org.orekit.bodies import OneAxisEllipsoid, GeodeticPoint
from org.orekit.data import DataContext
from org.orekit.frames import Transform, StaticTransform
from org.orekit.models.earth import ReferenceEllipsoid
from org.orekit.time import AbsoluteDate
from satellite import Satellite
from org.orekit.propagation import SpacecraftState
from org.orekit.geometry.fov import FieldOfView

from org.orekit.propagation.events import LongitudeCrossingDetector, FootprintOverlapDetector
from org.orekit.propagation.events.handlers import PythonEventHandler

from org.hipparchus.geometry.euclidean.threed import Rotation, Vector3D

import isodate
import numpy as np

import java

@dataclass
class WorkItem:
    """
    Work packet of w
    """
    start:AbsoluteDate
    stop:AbsoluteDate
    sat:Satellite
    aoi:AoiCollection
    map:Map

class LongitudeWrapHandler(PythonEventHandler):
    def __init__(self, tracer:NadirTrace):
        #PythonEventHandler.__init__(self)
        super().__init__()
        self.__tracer = tracer
        
    def init(self, initialstate, target, detector):
        pass

    def resetState(self, detector, oldState):
        pass
    
    def eventOccurred(self, s, detector, increasing):
        self.__tracer.addStateAndNewline(s)
        return Action.CONTINUE



class AoiHandler(PythonEventHandler):
    def __init__(self, id:str, builder:PayloadActivityBuilder):
        super().__init__()
        self.__id = id
        self.__builder = builder
    
    def init(self, initialstate, target, detector):
        pass

    def resetState(self, detector, oldState):
        pass
    
    def eventOccurred(self, s, detector, increasing):
        if increasing:
            print(f"exiting {self.__id} at: {s.getDate()}")
            self.__builder.stopActivity(s)
        else:
            print(f"entering {self.__id} at {s.getDate()}")
            self.__builder.startActivity(s)
        return Action.CONTINUE

def execute(item:WorkItem, centralBody:ReferenceEllipsoid=None, context:DataContext=None, step:str="PT10M"):
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
    propagator.propagate(item.start)
    
    # register an event detector to avoid line wrapping on the map
    nadirLine = LineBuilder(**({'tooltip':item.sat.name, 'color': item.sat.displayColor} | item.sat.groundTraceConfig))
    nadirTracer = NadirTrace(centralBody, nadirLine)
    propagator.addEventDetector(LongitudeCrossingDetector(centralBody, FastMath.PI).withHandler(LongitudeWrapHandler(nadirTracer)))
    
    sensor = item.sat.getSensor()
    fov = sensor.createFovInBodyFrame()
    
    # build the payload activities
    activityBuilder = PayloadActivityBuilder(fov, centralBody)
    
    # register aoi detectors
    idx = 0
    for zone in item.aoi.zones:
        propagator.addEventDetector(FootprintOverlapDetector(fov, centralBody, zone, 10000.).withHandler(AoiHandler(f"zone{idx}", activityBuilder)))
        idx = idx + 1
        
    # do the work
    propTime = item.stop.durationFrom(item.start)
    elapsed = 0.
    
    points = []
    while elapsed <= propTime:
        t = item.start.shiftedBy(elapsed)
        try: 
            state = propagator.propagate(t)
            
            nadirTracer.addState(state)
            
            if activityBuilder.isInActivity:
                activityBuilder.addState(state)
            
            #from state frame to earth frame
            #stateToEarth = state.getFrame().getTransformTo(centralBody.getBodyFrame(), t)
            #from spacecraft body to state frame
            #bodyToState = state.toTransform().getInverse()
            #from fov frame to spacecraft body frame
            #fovToBody = fovToBodyTxProv.getTransform(t)
            #fov to earth
            #fovToEarth = Transform(t, fovToBody, Transform(t, bodyToState, stateToEarth))
            
            #footprint = fov.getFootprint(fovToEarth, centralBody, FastMath.toRadians(1.))
            #for ring in list(footprint):
            #    for l in java.util.List.cast_(ring):
            #        loc = GeodeticPoint.cast_(l)
            #        points.append((FastMath.toDegrees(loc.getLongitude()), FastMath.toDegrees(loc.getLatitude())))
            
            elapsed += stepSeconds
        except:
            print(f"Caught exception processing sat {item.sat.id} at time {t}")
            raise
    
    nadirLine.finished()
    if not 'show' in item.sat.groundTraceConfig or item.sat.groundTraceConfig['show']:
        for l in nadirLine:
            l.add_to(item.map)
    
    for a in activityBuilder.activities:
        if not a.footprint is None:
            a.add_to(item.map, color='red')
    
    print(f"completed work for {item.sat.id}")