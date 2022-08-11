'''
Container to load and manage AOIs within the 
'''
if __name__ == '__main__':
    import orekit
    orekit.initVM()
    
from argparse import ArgumentError
from dataclasses import dataclass
from dataloader import download

import shapely.geometry
from shapely.geometry import Polygon
import geopandas

from org.hipparchus.geometry.spherical.twod import SphericalPolygonsSet
from org.hipparchus.util import FastMath
from org.orekit.models.earth.tessellation import EllipsoidTessellator
from org.orekit.bodies import GeodeticPoint

def _toZone(polygon:Polygon) -> SphericalPolygonsSet:
    points = []
    for p in polygon.boundary.coords:
        points.append(GeodeticPoint(FastMath.toRadians(p[1]), FastMath.toRadians(p[0]), 0.)) # put lon,lat into lat,lon order
    
    return EllipsoidTessellator.buildSimpleZone(float(1.0e-10), points)

class Aoi:
    
    def __init__(self,
            id:str,
            polygon:Polygon,
            zone: SphericalPolygonsSet,
            simplifed:bool = False):
        self.__id = id
        self.__polygon = polygon
        self.__zone = zone
        self.__simplifed = simplifed
    
    @property
    def id(self) -> str:
        return self.__id
    
    @property
    def polygon(self) -> Polygon:
        return self.__polygon
    
    @property
    def zone(self) -> SphericalPolygonsSet:
        return self.__zone
    
    @property
    def size(self) -> int:
        """The number of points in the AOI."""
        return len(self.__polygon.boundary.coords)
    
    def simplify(self, maxSize:int=500):
        """Simplify the aoi into one with fewer verticies

        Returns:
            _type_: _description_
        """
        
        # convert the polygon to a distance-preserving shape
        gs = geopandas.GeoSeries(data = self.__polygon, crs="+proj=longlat +datum=WGS84 +no_defs")
        gs = gs.to_crs("+proj=eck4 +lon_0=0 +x_0=0 +y_0=0 +datum=WGS84 +units=m +no_defs")
        
        gs = gs.simplify(10000)
        gs = gs.to_crs("+proj=longlat +datum=WGS84 +no_defs")
        poly = shapely.geometry.polygon.orient(gs.item())
        
        if len(poly.boundary.coords) > maxSize:
            print("simplifed shape was too big, simplifying using convex hull")
            poly = shapely.geometry.polygon.orient(Polygon(shell = self.__polygon.boundary.convex_hull))
            
        zone = _toZone(poly)
        
        return Aoi(self.id, poly, zone, True)
        

class AoiCollection:
    """
    Collection of relevant AOIs to use in this run.
    
    Data is loaded as GeoJSON and can be filtered after loading.
    """
    
    def __init__(self, sourceUrl='https://datahub.io/core/geo-countries/r/countries.geojson', bbox:tuple[float, float, float, float]=None):
        """
        Class constructor

        Args:
            sourceUrl (str, optional): Url from which to load the data. Defaults to 'https://datahub.io/core/geo-countries/r/countries.geojson'.
            bbox (tuple, optional): 4-tuple of the geographic bounding box. Must be specified as `[lon1, lat1, lon2, lat2]`. Defaults to None.
        """
        
        self.sourceUrl = sourceUrl
        self.__geojson = None
        self.__gdf = None
        self.__polygons = None
        self.__bbox = bbox
        self.__aois = None
    
    @property
    def sourceUrl(self) -> str:
        """
        The URL from which source data is loaded.

        Returns:
            str: The source URL
        """
        return self.__sourceUrl
    
    @sourceUrl.setter
    def sourceUrl(self, value):
        self.__sourceUrl = value
    
    @property
    def isLoaded(self) -> bool:
        """
        Indicate whether or not data is loaded

        Returns:
            bool: True when data is load, False otherwise
        """
        return self.__geojson != None
    
    @property
    def bbox(self) -> tuple[float, float, float, float]:
        """
        bounding box filter, in the form (lon1, lat1, lon2, lat2)
        
        Returns:
            tuple[float, float, float, float]: bounding box filter for this AoiCollection
        """
        return self.__bbox
    @bbox.setter
    def bbox(self, value):
        if not value == None and not len(value) == 4:
            raise ArgumentError(argument='bbox', message='bbox must have 4 elements')
        self.__bbox = value
    
    @property
    def geoJson(self):
        """
        GeoJSON for this AoiCollection

        Returns:
            str: This AoiCollection, as a GeoJSON string
        """
        return self.__geojson
    
    @property
    def gdf(self) -> geopandas.GeoDataFrame:
        """The data frame for this AoiCollection

        Returns:
            geopandas.GeoDataFrame: The data frame for this aoi collection
        """
        return self.__gdf
    
    @property
    def zones(self) -> list[SphericalPolygonsSet]:
        """The set of AOI borders, as sphericalpolygonsset instances

        Returns:
            list[SphericalPolygonsSet]: the list of aoi boundaries
        """
        return self.__zones
    
    @property
    def aois(self) -> list[Aoi]:
        return self.__aois
    
    def load(self):
        """
        Load the data from the `sourceUrl` property.
        """
        if self.isLoaded:
            return
        
        filepath = download(self.sourceUrl)
        
        box = None
        if not self.bbox is None:
            box = shapely.geometry.box(minx=min(self.bbox[0], self.bbox[2]),
                                        maxx=max(self.bbox[0], self.bbox[2]),
                                        miny=min(self.bbox[1], self.bbox[3]),
                                        maxy=max(self.bbox[1], self.bbox[3]))
        
        gdf = geopandas.read_file(filepath, bbox=box)
                
        # project to equal-area
        gdf = gdf.to_crs("+proj=eck4 +lon_0=0 +x_0=0 +y_0=0 +datum=WGS84 +units=m +no_defs")
                
        # apply the buffer
        gdf['geometry'] = gdf.geometry.buffer(20000)
        
        # combine overlapping data
        gdf = gdf.dissolve(aggfunc = 'sum')
              
        # put back to wgs-84
        gdf = gdf.to_crs("+proj=longlat +datum=WGS84 +no_defs")
        
        # filter the data
        if not box is None:
            gdf = gdf.intersection(box)
        
        # extract only the polygon shells, ignore any holes
        aois = []
        idx=0
        polys=[]
        for g in gdf.geometry:
            for p in g.geoms:
                ccw = shapely.geometry.polygon.orient(Polygon(shell=p.exterior))
                polys.append(ccw)
                
                zone = _toZone(ccw)
                idx = idx + 1
                
                id = f"target{idx}"
                
                aois.append(Aoi(id=id, polygon=ccw, zone=zone))

        gdf = geopandas.GeoDataFrame(geometry=polys)
    
        # save the data frame and geojson
        self.__gdf = gdf
        self.__geojson = gdf.to_json()
        self.__aois = aois
    
    def unload(self):
        """
        Unload the data.
        """
        self.__geojson = None
        self.__gdf = None

if __name__ == '__main__':
    import folium
    
    countries = AoiCollection(bbox=(-85, -60, -33, 13))
    countries.load()
    
    #map = folium.Map()
    #folium.GeoJson(data=countries.geoJson).add_to(map)
    
    #map.save('test.html')
    