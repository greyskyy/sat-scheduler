from org.hipparchus.util import FastMath

from org.orekit.bodies import GeodeticPoint, OneAxisEllipsoid
from org.orekit.frames import Transform
from org.orekit.geometry.fov import FieldOfView
from org.orekit.propagation import SpacecraftState
from org.orekit.time import AbsoluteDate
from pyproj import Geod

from java.util import List as JavaList

from shapely.geometry import MultiPoint
from shapely.geometry.polygon import Polygon

from folium import Map, Polygon as MapPolygon

import alphashape
import numpy as np

ANGULAR_STEP_DEGREES = 5.

class PayloadActivity:
    def __init__(self, start:AbsoluteDate, stop:AbsoluteDate, footprint:Polygon=None):
        self.__start = start
        self.__stop = stop
        self.__footprint = footprint
    
    @property
    def start(self) -> AbsoluteDate:
        return self.__start
    
    @property
    def stop(self) -> AbsoluteDate:
        return self.__stop

    @property
    def footprint(self) -> Polygon:
        return self.__footprint
    
    def add_to(self, map, **kwargs):
        mapArgs = []
        for p in self.__footprint.exterior.coords:
            mapArgs.append((p[1], p[0])) #shapely polygon is lon,lat but map polygon is lat,lon
        
        MapPolygon(mapArgs, **kwargs).add_to(map)        

class PayloadActivityBuilder:
    
    def __init__(self, fov:FieldOfView, earth:OneAxisEllipsoid):
        self.__fov = fov
        self.__earth = earth
        self.__activities = []
        self.__currentStart = None
        self.__currentPoints = []
    
    def startActivity(self, state:SpacecraftState):
        if self.__currentStart is None:
            self.__currentStart = state.getDate()
            
        self.addState(state)
    
    def addState(self, state:SpacecraftState):
        if self.__currentStart is None:
            raise RuntimeError("Cannot add a state without starting an activity")
        
        try:
            fovToState = state.toTransform().getInverse()
            stateToEarth = state.getFrame().getTransformTo(self.__earth.getBodyFrame(), state.getDate())
            fovToEarth = Transform(state.getDate(), fovToState, stateToEarth)
            footprint = self.__fov.getFootprint(fovToEarth, self.__earth, FastMath.toRadians(ANGULAR_STEP_DEGREES))
            
            if not footprint is None:
                outerRing = list(footprint)[0]
                for p in JavaList.cast_(outerRing):
                    gp = GeodeticPoint.cast_(p)
                    self.__currentPoints.append([
                        FastMath.toDegrees(gp.getLongitude()),
                        FastMath.toDegrees(gp.getLatitude())])
        except BaseException as e:
            print(f"caught exception adding state: {e}")
            
    def stopActivity(self, state:SpacecraftState):
        self.addState(state)
        
        try:
            array = np.array(self.__currentPoints)
            #alpha = alphashape.optimizealpha(array, silent=True)
            #footprint = alphashape.alphashape(array, alpha)
            
            mp = MultiPoint(array)
            footprint = mp.convex_hull
            
            self.__activities.append(PayloadActivity(self.__currentStart, state.getDate(), footprint=footprint))
            
            self.__currentStart = None
            self.__currentPoints.clear()
        except BaseException as e:
            print(f"caught exception closing activity: {e}")
            raise e
        
    @property
    def activities(self) -> list[PayloadActivity]:
        return self.__activities
    
    @property
    def isInActivity(self) -> bool:
        return not self.__currentStart is None