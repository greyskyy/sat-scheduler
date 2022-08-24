"""
Container to load and manage AOIs within the 
"""
from astropy import units
from numpy import isin
from pyproj import CRS
from satscheduler.dataloader import download

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
    def createZones(
        self, tolerance: units.Quantity[units.m] = 1000 * units.m
    ) -> SphericalPolygonsSet:
        """Create the spherical polygons set, suitable for payload operations for this aoi.

        Returns:
            list[SphericalPolygonsSet]: The list of polygon sets
        """
        gdf = self.to_gdf()

        # project to equal-area
        gdf = gdf.to_crs(
            "+proj=eck4 +lon_0=0 +x_0=0 +y_0=0 +datum=WGS84 +units=m +no_defs"
        )
        # gs = gdf.buffer(buffer)
        gs = gdf.geometry
        if tolerance.value > 0:
            gs = gs.simplify(tolerance.to_value(units.m))
        gs = gs.to_crs(self.crs)

        zones = []
        for p in _polygons(gs):
            ccw = shapely.geometry.polygon.orient(
                Polygon(shell=p.exterior)
            )  # not sure this should go here

            try:
                zones.append(_toZone(ccw))
            except BaseException as e:
                print(f"Caught exception building zone for {self.id} error: {e}")

        return zones


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
    filepath = download(sourceUrl)

    # read the fille
    gdf = geopandas.read_file(filepath, bbox=bbox)

    # project to equal-area
    center = gdf.to_crs(
        "+proj=eck4 +lon_0=0 +x_0=0 +y_0=0 +datum=WGS84 +units=m +no_defs"
    ).geometry.centroid
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

        if p[1] >= -90 and p[1] <= 90:
            points.append(
                GeodeticPoint(FastMath.toRadians(p[1]), FastMath.toRadians(p[0]), 0.0)
            )  # put lon,lat into lat,lon order

        prev = p

    return EllipsoidTessellator.buildSimpleZone(float(1.0e-10), points)


def _polygons(geometry) -> Generator[Polygon]:
    """Split a geometry into a series of valid polygons.

    Args:
        geometry (Polygon|MultiPolygon|GeoSeries): The polygon(s) to enumerate.
        make_valid (bool, optional): If a polygon is not valid, try to make it valid. Defaults to True.

    Yields:
        Generator[Polygon]: The enumeration of valid polygons.
    """
    if isinstance(geometry, Polygon):
        yield geometry
    elif isinstance(geometry, MultiPolygon):
        for g in geometry.geoms:
            yield from _polygons(g)
    elif isinstance(geometry, GeoSeries):
        for g in geometry:
            yield from _polygons(g)
    else:
        raise ValueError(
            f"cannot generate polygon from unsupported type: {type(geometry)}"
        )


def _buildAoi(
    geometry,
    id: str,
    alpha3: str = None,
    alpha2: str = None,
    continent: str = None,
    country: str = None,
    crs: CRS = None,
) -> Generator[Aoi]:
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
    if isinstance(geometry, GeoSeries):
        if geometry.size == 1:
            yield from _buildAoi(
                geometry.iloc[0],
                id,
                alpha2=alpha2,
                alpha3=alpha3,
                country=country,
                continent=continent,
                crs=crs,
            )
        else:
            idx = 0
            for g in geometry.geoms:
                yield from _buildAoi(
                    g,
                    f"{id}_{idx}",
                    alpha2=alpha2,
                    alpha3=alpha3,
                    country=country,
                    continent=continent,
                    crs=crs,
                )
                idx = idx + 1
    elif isinstance(geometry, Polygon):
        fixed = antimeridian.split(geometry)
        if fixed:
            yield from _buildAoi(
                fixed,
                id,
                alpha2=alpha2,
                alpha3=alpha3,
                country=country,
                continent=continent,
                crs=crs,
            )
        else:
            ccw = shapely.geometry.polygon.orient(Polygon(shell=geometry.exterior))
            if crs is None:
                crs = CRS.from_string("+proj=longlat +datum=WGS84 +no_defs")

            frame = GeoDataFrame(
                data={
                    "ISO_A2": [alpha2],
                    "ISO_A3": [alpha3],
                    "country": [country],
                    "continent": [continent],
                    "geometry": [ccw],
                },
                crs=crs,
            )

            yield Aoi(
                id.replace(" ", "_"),
                polygon=ccw,
                alpha2=alpha2,
                alpha3=alpha3,
                country=country,
                continent=continent,
                crs=crs,
            )
    elif isinstance(geometry, MultiPolygon):
        fixed = antimeridian.split_multipolygon(geometry)
        if fixed:
            geometry = fixed

        idx = 0
        for g in _polygons(geometry):
            yield from _buildAoi(
                g,
                f"{id}_{idx}".replace(" ", "_"),
                alpha2=alpha2,
                alpha3=alpha3,
                country=country,
                continent=continent,
                crs=crs,
            )
            idx = idx + 1
    else:
        raise ValueError(
            f"cannot create aoi from invalid geometry type: {type(geometry)}"
        )


@units.quantity_input()
def loadAois(
    sourceUrl: str = "https://www.naturalearthdata.com/http//www.naturalearthdata.com/download/110m/cultural/ne_110m_admin_0_countries.zip",
    bbox: tuple[float, float, float, float] = None,
    buffer: units.Quantity[units.m] = 20000 * units.m,
    tolerance: units.Quantity[units.m] = 1000 * units.m,
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

    aois = []
    count = 0
    for index, row in gdf.iterrows():
        continent = row["CONTINENT"]
        country = row["ADMIN"]
        alpha2 = row["ISO_A2"]
        alpha3 = row["ISO_A3"]
        geometry = gdf.geometry[index]

        # buffer the area
        frame = GeoDataFrame(
            data={
                "ADMIN": [country],
                "ISO_A2": [alpha2],
                "ISO_A3": [alpha3],
                "CONTINENT": [continent],
                "geometry": [geometry],
            },
            crs="+proj=longlat +datum=WGS84 +no_defs",
        )

        frame = frame.to_crs(
            "+proj=eck4 +lon_0=0 +x_0=0 +y_0=0 +datum=WGS84 +units=m +no_defs"
        )
        frame = frame.buffer(buffer.to_value(units.m))
        frame = frame.to_crs(crs)

        if frame.geometry.is_valid.bool():
            geometry = frame.geometry
        else:
            logger.warn(
                "Invalid buffered geometry, using unbuffered geometry for continent=%s country=%s",
                continent,
                country,
            )

        # splits = frame.apply(antimeridian.fix_item)
        # frame.loc[splits.dropna().index, "geometry"] = splits

        count = count + 1

        aois.extend(
            _buildAoi(
                geometry,
                country.replace(" ", "_"),
                country=country,
                alpha2=alpha2,
                alpha3=alpha3,
                continent=continent,
                crs=crs,
            )
        )

    return aois
