from dataclasses import dataclass
from folium import Map, PolyLine
from linebuilder import LineBuilder
from orekithelpers import referenceEllipsoid
from nadirtrace import NadirTrace

from org.hipparchus.ode.events import Action
from org.hipparchus.util import FastMath
from org.orekit.data import DataContext
from org.orekit.models.earth import ReferenceEllipsoid
from org.orekit.time import AbsoluteDate
from satellite import Satellite

from org.orekit.propagation.events import LongitudeCrossingDetector
from org.orekit.propagation.events.handlers import PythonEventHandler

import isodate

@dataclass
class WorkItem:
    """
    Work packet of w
    """
    start:AbsoluteDate
    stop:AbsoluteDate
    sat:Satellite
    map:Map

class LongitudeWrapHandler(PythonEventHandler):
    def __init__(self, tracer:NadirTrace):
        PythonEventHandler.__init__(self)
        self.__tracer = tracer
        
    def init(self, initialstate, target, detector):
        pass

    def resetState(self, detector, oldState):
        pass
    
    def eventOccurred(self, s, detector, increasing):
        self.__tracer.addStateAndNewline(s)
        return Action.CONTINUE


def execute(item:WorkItem, centralBody:ReferenceEllipsoid=None, context:DataContext=None, step:str="PT10M"):
    if context is None:
        context = DataContext.getDefault()
        
    if centralBody is None:
        centralBody = referenceEllipsoid("wgs84", frameName="itrf", simpleEop=False, iersConventions="iers2010")
    
    propagator = item.sat.buildPropagator(context=context)
    
    stepSeconds = isodate.parse_duration(step).total_seconds()
    
    print(f"starting work for {item.sat.id} over timespan {item.start} to {item.stop}")
    
    #set the propagator at the start time before we do anything else
    propagator.propagate(item.start)
    
    # register an event detector to avoid line wrapping on the map
    nadirLine = LineBuilder(**({'tooltip':item.sat.name, 'color': item.sat.displayColor} | item.sat.groundTraceConfig))
    nadirTracer = NadirTrace(centralBody, nadirLine)
    propagator.addEventDetector(LongitudeCrossingDetector(centralBody, FastMath.PI).withHandler(LongitudeWrapHandler(nadirTracer)))
    
    # do the work
    propTime = item.stop.durationFrom(item.start)
    elapsed = 0.
    while elapsed <= propTime:
        t = item.start.shiftedBy(elapsed)
        try: 
            state = propagator.propagate(t)
            
            nadirTracer.addState(state)

            elapsed += stepSeconds
        except:
            print(f"Caught exception processing sat {item.sat.id} at time {t}")
            raise
    
    nadirLine.finished()
    if not 'show' in item.sat.groundTraceConfig or item.sat.groundTraceConfig['show']:
        for l in nadirLine:
            l.add_to(item.map)
    
    print(f"completed work for {item.sat.id}")