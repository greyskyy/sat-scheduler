
from folium import PolyLine
from math import copysign

class LineBuilder:
    """Builder managing the construction of lines on a map, handling any wrapping around 180 degrees longitude
    """
    def __init__(self, **kwargs):
        self.__currentPoints = []
        self.__lines = []
        self.__displayArgs = kwargs
    
    def addPoint(self, lat:float, lon:float):
        self.__currentPoints.append((lat, lon))
    
    def addPointAndSplit(self, lat:float, lon:float):
        """add a point to the builder, splitting the line into a new one

        Args:
            lat (float): latitude, in degrees
            lon (float): longitude, in degrees
        """
        
        if len(self.__currentPoints) == 0:
            self.addPoint(lat, lon)
            return
        
        (currentLat, currentLon) = self.__currentPoints[-1]
        
        if lon < 0:
            lon = -lon
        
        # if the line currently is in west and the point is in the west
        if currentLon < 0:
            if abs(currentLon + lon) < 1e-9:
                self.split()
                self.addPoint(lat, lon)
            else:
                self.addPoint(lat, -lon)
                self.split()
                self.addPoint(lat, lon)
        else:
            if abs(currentLon - lon) < 1e-9:
                self.split()
                self.addPoint(lat, -lon)
            else:
                self.addPoint(lat, lon)
                self.split()
                self.addPoint(lat, -lon)
                
    def split(self):
        """Indicate to split the line and create a new one. Call this as the line crosses 180-degrees longitude
        """
        
        if len(self.__currentPoints) > 2:
            self.__lines.append(PolyLine(self.__currentPoints, **(self.__displayArgs)))
        self.__currentPoints = []
            
    def clear(self):
        """Clear the builder
        """
        self.__currentPoints = []
        self.__lines = []
        
    def finished(self):
        """Indicate no more points will be added
        """
        self.split()
        pass
    
    @property
    def size(self):
        return len(self.__lines)
    
    @property
    def currentSize(self):
        return len(self.__currentPoints)
    
    def __iter__(self):
        return iter(self.__lines)