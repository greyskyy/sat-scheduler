
from linebuilder import LineBuilder

from org.hipparchus.util import FastMath

from org.orekit.bodies import GeodeticPoint
from org.orekit.frames import Frame
from org.orekit.models.earth import ReferenceEllipsoid
from org.orekit.propagation import SpacecraftState
from org.orekit.time import AbsoluteDate
from org.orekit.utils import PVCoordinates

class NadirTrace:
    def __init__(self, earth:ReferenceEllipsoid, lineBuilder:LineBuilder=None):
        self.__earth = earth
        self.__line = lineBuilder
    
    def addState(self, state:SpacecraftState):
        pv = state.getPVCoordinates(self.__earth.getBodyFrame())
        
        return self.addPv(pv, self.__earth.getBodyFrame(), state.getDate())
    
    def addPv(self, pv:PVCoordinates, frame:Frame, date:AbsoluteDate):
        # project to ground
        nadir = self.__earth.projectToGround(pv.getPosition(), date, self.__earth.getFrame())
        point = self.__earth.transform(nadir, self.__earth.getFrame(), date)

        # add current points to the list
        (lat, lon) = self._asTuple(point)
        self.__line.addPoint(lat, lon)
        
        return self
    
    def addStateAndNewline(self, state:SpacecraftState):
        try:
            pv = state.getPVCoordinates(self.__earth.getBodyFrame())
            
            return self.addPvAndNewline(pv, self.__earth.getBodyFrame(), state.getDate())
        except Exception as e:
            print(e)
            raise e
    
    def addPvAndNewline(self, pv:PVCoordinates, frame:Frame, date:AbsoluteDate):
        # project to ground
        nadir = self.__earth.projectToGround(pv.getPosition(), date, self.__earth.getFrame())
        point = self.__earth.transform(nadir, self.__earth.getFrame(), date)
        
        (lat, lon) = self._asTuple(point)
        self.__line.addPointAndSplit(lat, lon)
    
    def _asTuple(self, point:GeodeticPoint) -> tuple[float,float]:
        return tuple([FastMath.toDegrees(point.getLatitude()), FastMath.toDegrees(point.getLongitude())])
    