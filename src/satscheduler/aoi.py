"""
Container to load and manage AOIs within the 
"""
from typing import Iterable
from astropy import units
from numpy import isin
from pyproj import CRS
from orekitfactory.utils import Dataloader
from orekitfactory.utils import validate_quantity

import shapely
import shapely.geometry
import shapely.validation
from shapely.ops import clip_by_rect, polygonize
from shapely.geometry.polygon import Polygon
from shapely.geometry.multipolygon import MultiPolygon
from shapely.geometry.multilinestring import MultiLineString
import geopandas
from geopandas import GeoDataFrame, GeoSeries

from collections.abc import Generator
from org.hipparchus.geometry.spherical.twod import SphericalPolygonsSet
from org.hipparchus.util import FastMath
from org.orekit.models.earth.tessellation import EllipsoidTessellator
from org.orekit.bodies import GeodeticPoint

from stactools.core.utils import antimeridian

import warnings
import logging
from shapely.errors import ShapelyDeprecationWarning


warnings.filterwarnings("ignore", category=ShapelyDeprecationWarning)
warnings.filterwarnings("ignore", category=FutureWarning)


class Aoi:
    """An Area of Interest to be collected by the scheduler.

    This object holds the region, as well as any necessary metadata regarding the region.
    """

    def __init__(
        self,
        id: str,
        polygon: Polygon,
        crs=None,
        continent: str = None,
        country: str = None,
        alpha2: str = None,
        alpha3: str = None,
        area: float = 0
    ):
        """Class construtor

        Args:
            id (str): The unique id of this area
            polygon (Polygon): Area of this region, as a shapely Polygon
            crs (_type_, optional): The CRS in which the polygon is defined. Defaults to None.
            continent (str, optional): Continent on which this aoi is defined. Defaults to None.
            country (str, optional): Country in which this aoi is defined. Defaults to None.
            alpha2 (str, optional): The 2-digit country code for this AOI. Defaults to None.
            alpha3 (str, optional): The 3-digit country code for this AOI. Defaults to None.
        """
        self.__id = id
        self.__polygon = polygon
        self.__alpha2 = alpha2
        self.__alpha3 = alpha3
        self.__country = country
        self.__continent = continent
        self.__crs = crs
        self.__area = area

    @property
    def id(self) -> str:
        """The AOI id

        Returns:
            str: The AOI id
        """
        return self.__id

    @property
    def polygon(self) -> Polygon:
        """The region of this AOI.

        Returns:
            Polygon: The shapely Polygon describing this aoi
        """
        return self.__polygon

    @property
    def size(self) -> int:
        """The number of points in the AOI."""
        return len(self.__polygon.boundary.coords)

    @property
    def alpha2(self) -> str:
        """ISO 3166 two letter country code for this AOI's country, may be None if unset.

        Returns:
            str: 3166 alpha-2 country code, None if unset.
        """
        return self.__alpha2

    @property
    def alpha3(self) -> str:
        """ISO 3166 three letter country code of this AOI's country, may be None if unset.

        Returns:
            str: 3166 alpha-3 country code, None if unset.
        """
        return self.__alpha3

    @property
    def country(self) -> str:
        """The AOI's country, may be None if unset.

        Returns:
            str: The AOI country, None if unset.
        """
        return self.__country

    @property
    def continent(self) -> str:
        """The continent for this aoi, may be None if unset.

        Returns:
            str: The AOI's continent, None if unset.
        """
        return self.__continent

    @property
    def crs(self):
        """The CRS in which the polygon is defined.

        This may be None, if unspecified in the constructor.

        Returns:
            CRS|Any: The crs of the aoi's polygon, if specified
        """
        return self.__crs
    
    @property
    def area(self) -> float:
        """The area of this aoi, in square meters.
        
        Returns:
            float: The area of this aoi, in square meters.
        """
        return self.__area

    def to_gdf(self) -> GeoDataFrame:
        """Create a GeoDataFrame from this AOI

        Returns:
            GeoDataFrame: A data frame for this AOI
        """

        return GeoDataFrame(
            data={
                "aoi_id": [self.id],
                "ISO_A2": [self.alpha2],
                "ISO_A3": [self.alpha3],
                "continent": [self.continent],
                "ADMIN": [self.country],
                "geometry": [self.polygon],
            },
            crs=self.crs,
        )

    @units.quantity_input
    def createZone(
        self, tolerance: units.Quantity[units.m] = 1000 * units.m
    ) -> SphericalPolygonsSet:
        """Create the spherical polygons set, suitable for payload operations for this aoi.

        Returns:
            list[SphericalPolygonsSet]: The spherical polygon set for this AOI, or None if an error was generated.
        """
        try:
            return _toZone(self.polygon)
        except:
            logging.getLogger(__name__).error(
                "Error building aoi zone for aoi id=%s.",
                self.id,
                exc_info=1,
                stack_info=1,
            )
            return None


def loadIntoGdf(
    sourceUrl: str = "https://www.naturalearthdata.com/http//www.naturalearthdata.com/download/110m/cultural/ne_110m_admin_0_countries.zip",  #'https://datahub.io/core/geo-countries/r/countries.geojson',
    bbox: Polygon = None,
) -> geopandas.GeoDataFrame:
    """Load the source file into a GeoDataFrame.

    Args:
        sourceUrl (str, optional): The file to load. Defaults to 'https://www.naturalearthdata.com/http//www.naturalearthdata.com/download/110m/cultural/ne_110m_admin_0_countries.zip'.
        bbox (Polygon, optional): A bounding box, specified as [lon1,lat1,lon2,lat2] in degrees. Defaults to None.

    Returns:
        geopandas.GeoDataFrame: The data frame
    """
    # download the source file
    filepath = Dataloader.download(url=sourceUrl)

    # read the fille
    gdf = geopandas.read_file(filepath, bbox=bbox)

    # project to equal-area
    equal_area = gdf.to_crs("EPSG:3857")
    center = equal_area.geometry.centroid
    center = center.to_crs("+proj=longlat +datum=WGS84 +no_defs")

    gdf["center"] = center

    return gdf


def _toZone(polygon: Polygon) -> SphericalPolygonsSet:
    """Convert the polygon into an orekit SphericalPolygonsSet, suitable for use in the astrodynamics computation.

    Args:
        polygon (Polygon): The aoi's polygon, in a lon/lat (degrees), WGS-84 format.

    Returns:
        SphericalPolygonsSet: The resulting spherical polygons set
    """
    points = []
    prev = None
    for p in polygon.boundary.coords:
        if prev:
            d_lat = abs(p[1] - prev[1])
            d_lon = abs(p[0] - prev[1])
            if (d_lat < 0.000001 or d_lat > 89.999999) and (
                d_lon < 0.000001 or d_lon > 359.999999
            ):
                continue

        if p[1] > -90 and p[1] < 90:
            points.append(
                GeodeticPoint(FastMath.toRadians(p[1]), FastMath.toRadians(p[0]), 0.0)
            )  # put lon,lat into lat,lon order

        prev = p

    return EllipsoidTessellator.buildSimpleZone(float(1.0e-6), points)


def _buildAoi(
    geometry,
    id: str,
    alpha3: str = None,
    alpha2: str = None,
    continent: str = None,
    country: str = None,
    crs: CRS = None,
    area: float = 0
) -> Aoi:
    """Build an AOI from the provided geometry

    Args:
        geometry (GeoSeries|Polygon|MultiPolygon): The aoi polygon.
        id (str): The unique id of the aoi.
        alpha3 (str, optional): The ISO_A3 country code for this aoi. Defaults to None.
        alpha2 (str, optional): The ISO_A2 country code for this aoi. Defaults to None.
        continent (str, optional): The continent of this aoi. Defaults to None.
        country (str, optional): The country name for this aoi. Defaults to None.

    Raises:
        ValueError: When an invalid geometry type is provided.

    Yields:
        Generator[Aoi]: A generator enumerating all the AOIs built from this geometry
    """
    ccw = shapely.geometry.polygon.orient(Polygon(shell=geometry.exterior))

    return Aoi(
        id.replace(" ", "_"),
        polygon=ccw,
        alpha2=alpha2,
        alpha3=alpha3,
        country=country,
        continent=continent,
        crs=crs,
        area=area
    )


def loadAois(
    sourceUrl: str = "https://www.naturalearthdata.com/http//www.naturalearthdata.com/download/110m/cultural/ne_110m_admin_0_countries.zip",
    bbox: tuple[float, float, float, float] = None,
    buffer: units.Quantity[units.m] | float | str = 20000 * units.m,
    tolerance: units.Quantity[units.m] | float | str = 1000 * units.m,
    **kwargs
) -> list[Aoi]:
    """Load the AOIs from the source as a list of Aoi objects.

    If the `buffer` parameter is greater than 0, all AOIs will have their boundary expanded, as defined by the geopandsas.GeoSeries.buffer method.
    If the `tolerance` parameter is greater than 0, the aois will have their boundaries simplified.

    Args:
        sourceUrl (str, optional): The url from which to load the AOI Must be consumable by geopandas.GeoDataFrame.load_file. Defaults to "https://www.naturalearthdata.com/http//www.naturalearthdata.com/download/110m/cultural/ne_110m_admin_0_countries.zip".
        bbox (tuple[float, float, float, float], optional): Bounding box limiting the regions to read. A 4-tuple of [min_lon, min_lat, max_lon, max_lat]. Defaults to None.
        buffer (units.Quantity[units.m], optional): Amount to buffer each aoi. Defaults to 20km.
        tolerance (units.Quantity[units.m], optional): Minimum spacing of points, used to reduce the fidelidy of polygons. Defaults to 1km.

    Returns:
        list[Aoi]: The list of loaded Aoi objects.
    """

    logger = logging.getLogger(__name__)
    logger.debug("loading aois from %s", sourceUrl)

    buffer = validate_quantity(buffer, units.m)
    tolerance = validate_quantity(tolerance, units.m)

    # build a bounding box, if one is loaded
    box = None
    if bbox is not None:
        box = shapely.geometry.box(
            minx=min(bbox[0], bbox[2]),
            maxx=max(bbox[0], bbox[2]),
            miny=min(bbox[1], bbox[3]),
            maxy=max(bbox[1], bbox[3]),
        )

    # read the fille
    gdf = loadIntoGdf(sourceUrl=sourceUrl, bbox=box)
    crs = gdf.crs

    if crs is None:
        crs = CRS.from_string("+proj=longlat +datum=WGS84 +no_defs")
        gdf.set_crs(crs)

    # buffer
    if buffer > 0 * units.m:
        gdf.to_crs("EPSG:3857", inplace=True)
        gds = gdf.buffer(buffer.to_value(units.m))
        gdf.geometry = gds
        gdf.to_crs(crs, inplace=True)
        
        # explode the multi-geometries
        gdf = gdf.explode(ignore_index=True)

        lonspan = gdf.bounds["maxx"] - gdf.bounds["minx"]
        mask = lonspan > 150

        gdf.loc[mask, "geometry"] = gdf.loc[mask, "geometry"].apply(antimeridian.split)
    gdf = gdf.explode(ignore_index=True)
    
    # compute the area
    gdf.to_crs("EPSG:3857", inplace=True)
    area = gdf.geometry.area
    gdf["area"] = area
    gdf.to_crs(crs, inplace=True)
    
    aois = []
    for index, row in gdf.iterrows():
        continent = row["CONTINENT"]
        country = row["ADMIN"]
        alpha2 = row["ISO_A2"]
        alpha3 = row["ISO_A3"]
        geometry = gdf.geometry[index]
        a = row["area"]

        aois.append(
            _buildAoi(
                geometry,
                continent.replace(" ", "_") + str(index),
                country=country,
                alpha2=alpha2,
                alpha3=alpha3,
                continent=continent,
                crs=crs,
                area=a
            )
        )

    return aois
