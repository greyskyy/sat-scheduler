"""Configuration data classes."""
import astropy.coordinates
import astropy.units as u
import datetime as dt
import dacite
from dataclasses import dataclass, field, asdict
import enum
import isodate
from typing import Any, Dict, List, Optional

from .units import Frequency, Mass, Area


class LOFTypeData(enum.Enum):
    """Representation of LOFType."""

    TNW = enum.auto()
    QSW = enum.auto()
    LVLH = enum.auto()
    LVLH_CCSDS = enum.auto()
    VVLH = enum.auto()
    VNC = enum.auto()
    EQW = enum.auto()
    NTW = enum.auto()

    @classmethod
    def _missing_(cls, value: Any) -> Any:
        if isinstance(value, str):
            for member in cls:
                if member.name.lower() == value.lower():
                    return member

        return super()._missing_(value)


class OrbitTypeData(enum.Enum):
    """Representation of OrbitType."""

    CARTESIAN = enum.auto()
    CIRCULAR = enum.auto()
    EQUINOCTIAL = enum.auto()
    KEPLERIAN = enum.auto()

    @classmethod
    def _missing_(cls, value: Any) -> Any:
        if isinstance(value, str):
            for member in cls:
                if member.name.lower() == value.lower():
                    return member

        return super()._missing_(value)


class CelestialBodyNames(enum.Enum):
    """Enumeration of known celestial bodies."""

    SOLAR_SYSTEM_BARYCENTER = enum.auto()
    SUN = enum.auto()
    MERCURY = enum.auto()
    VENUS = enum.auto()
    EARTH_MOON = enum.auto()
    EARTH = enum.auto()
    MOON = enum.auto()
    MARS = enum.auto()
    JUPITER = enum.auto()
    SATURN = enum.auto()
    URANUS = enum.auto()
    NEPTUNE = enum.auto()
    PLUTO = enum.auto()

    @classmethod
    def _missing_(cls, value: Any) -> Any:
        if isinstance(value, str):
            for member in cls:
                if member.name.lower() == value.lower():
                    return member

        return super()._missing_(value)


@dataclass(frozen=True, kw_only=True)
class DisplayOptions:
    """Set of display options that can be used when drawing on maps/globes."""

    color: Optional[str] = None
    """Color to use when drawing objects on the globe/map."""
    outlineColor: Optional[int] = None
    """Polygon outline color."""
    fillColor: Optional[int] = None
    """Fill color for polygons."""
    outlineWidth: Optional[int] = None
    """Width, in pixels, of the outline."""
    labels: Optional[bool] = None
    """Flag whether to show the label, if available to display."""
    font: Optional[str] = None
    """Font to use in the label."""
    show: Optional[bool] = True
    """Flag indicating whether to display or not-display the object."""

    def maybe_get(self, attr: str):
        """Attempt to retreive an attribute value.

        Args:
            attr (str): The attribute name

        Returns:
            Any|None: The attribute value, or `None` if the attribute is not found.
        """
        if hasattr(self, attr):
            return getattr(self, attr)
        return None


class Dictable:
    """A class that is convertable to a dictionary."""

    def as_dict(self) -> dict:
        """Convert this class to a dictionary."""
        return asdict(self)


@dataclass(frozen=True, kw_only=True)
class IntervalData:
    """Data class holding a start and stop interval."""

    start: dt.datetime
    """Interval start, as an ISO-8601 time string."""
    stop: dt.datetime
    """Interval stop, as an ISO-8601 time string."""


@dataclass(frozen=True, kw_only=True)
class RunData(IntervalData):
    """Data class for the run."""

    step: dt.timedelta = dt.timedelta(minutes=10)
    """Timestep used during ephemeris propagation."""
    multithread: bool = True
    """Flag indicating whether to multithread processing or not."""


@dataclass(frozen=True, kw_only=True)
class AoiConfiguration(DisplayOptions, Dictable):
    """Data class for AOI loading."""

    url: str = "https://www.naturalearthdata.com/"
    "http//www.naturalearthdata.com/download/110m/cultural/ne_110m_admin_0_countries.zip"
    """URL from where to download the file."""
    buffer: astropy.coordinates.Distance = astropy.coordinates.Distance(0, u.km)
    """Buffer distance to be applied to all AOI borders."""
    color: str = "#FF0000"
    """Color to use when drawing AOIs on the globe or map."""
    filter: Optional[dict] = None
    """Dictionary of filters to apply when loading the AOIs."""
    bbox: Optional[List] = None
    """Bounding box to use when loading AOI data. In [lon_min,lat_min,lon_max, lat_max]."""


@dataclass(frozen=True, kw_only=True)
class TleData:
    """Data class for TLE data."""

    line1: str
    """Line 1."""
    line2: str
    """Line 2."""


@dataclass(frozen=True, kw_only=True)
class KeplerianOrbitData(Dictable):
    """Data class for keplerian orbits."""

    epoch: dt.datetime
    """Orbit epoch."""
    a: astropy.coordinates.Distance
    """Semi-major axis."""
    e: float
    """Orbit eccentricity."""
    i: astropy.coordinates.Angle
    """Orbit inclination."""
    omega: astropy.coordinates.Angle
    """Orbit RAAN."""
    w: astropy.coordinates.Angle
    """Orbit Argument of Perigee."""
    v: Optional[astropy.coordinates.Angle]
    """True anomaly."""
    m: Optional[astropy.coordinates.Angle]
    """Mean anomaly."""
    frame: str = "gcrf"
    """Frame in which the orbit is defined."""


@dataclass(frozen=True, kw_only=True)
class RotationData:
    """Class describing a rotation.

    The rotation is specified with one or two of the resulting frame axis, as defined
    in the parent's frame.
    """

    x: list[float] = None
    """The frame's X-axis, defined in the parent's frame."""
    y: list[float] = None
    """The frame's Y-axis, defined in the parent's frame."""
    z: list[float] = None
    """The frame's Z-axis, defined in the parent's frame."""


@dataclass(frozen=True, kw_only=True)
class FrameData(RotationData):
    """Frame data class."""

    translation: list[float] = (0.0, 0.0, 0.0)
    """The frame's origin, defined in the parent frame."""


@dataclass(frozen=True, kw_only=True)
class SensorData:
    """Sensor data class."""

    id: str
    """Unique sensor id."""
    type: str
    """Sensor type."""
    frame: FrameData
    """Dictionary holding data used to construct the FrameData, defining the sensor frame."""
    useNadirPointing: bool
    """Whether or not to ignore the FoV and use the satellite's nadir point for inviews."""

    @classmethod
    def create(cls, data: dict):
        """Create a SensorData class or appropriate subclass.

        Args:
            data (dict): Dictionary of data parameters

        Returns:
            SensorData: The sensor data class (or subclass) instance.
        """
        cls = SensorData
        if data.get("type", "").lower() == "camera":
            cls = CameraSensorData

        return dacite.from_dict(data_class=cls, data=data, config=DACITE_CONFIG)


@dataclass(frozen=True, kw_only=True)
class CameraSensorData(SensorData):
    """Subclass of SensorData, holding data for a camera."""

    focalLength: astropy.coordinates.Distance
    """Focal length."""
    pitch: astropy.coordinates.Distance
    """Camera detector pitch."""
    imgPeriod: Frequency
    """Imaging period."""
    cols: int
    """Number of columns, must an integer greater than 0."""
    rows: int
    """Number of rows, must be an integer greater than 0."""
    rowsAlongX: bool
    """Flag indicating whether the rows or columns are aligned with +X_sensor."""


@dataclass(frozen=True, kw_only=True)
class PropagatorConfiguration(Dictable):
    """Propagator configuration parameters."""

    minStep: Optional[float]
    """Minimum propagator step, in seconds."""
    maxStep: Optional[float]
    """Largest propagator step, in seconds."""
    positionTolerance: Optional[astropy.coordinates.Distance]
    """Position tolerance."""
    considerGravity: Optional[bool]
    """Flag to enable or disable gravity."""
    gravityFieldDegree: Optional[int]
    """Polynomial degree for the gravity field."""
    gravityFieldOrder: Optional[int]
    """Polynomial order of the gravity field."""
    considerSolarPressure: Optional[bool]
    """Flag to enable solar pressure."""
    solarPressureCrossSection: Optional[Area]
    """Cross section for solar pressure."""
    solarCa: Optional[float]
    """Solar absorption coefficient."""
    solarCs: Optional[float]
    """Solar reflection coefficient."""
    considerAtmosphere: Optional[bool]
    """Flag indicating whether to consider atmospheric drag."""
    atmosphereCrossSection: Optional[Area]
    """Cross section for atmospheric drag."""
    atmosphereDragCoeff: Optional[float]
    """Coefficient for atmospheric drag."""
    bodies: Optional[list[CelestialBodyNames]]
    """List of celestial bodies to consider 3rd body effects."""
    orbitType: Optional[OrbitTypeData]
    """Orbit type override, defines the type of propagation."""

    @classmethod
    def union(cls, a: Dictable, b: Dictable):
        """Combine the propagator configurations.

        Duplicate keys from B will overwrite those from A.

        This is effectively similiar to a.as_dict() | b._as_dict()

        Args:
            a (PropagatorConfiguration): The first instance
            b (PropagatorConfiguration): The second instance

        Returns:
            PropagatorConfiguration: A new instance that combines A and B.
        """
        if a is None:
            return b
        elif b is None:
            return a
        else:
            return cls(**(a.as_dict() | b.as_dict()))


@dataclass(frozen=True, kw_only=True)
class AttitudeData:
    """Attitude data class."""

    name: str
    """Attitude mode name."""
    type: str
    """Mode type."""

    default: bool = False
    """Flag indicating whether this should be considered the default attitude."""

    @classmethod
    def create(cls, data: dict):
        """Create a AttitudeData class or appropriate subclass.

        Args:
            data (dict): Dictionary of data parameters

        Returns:
            SensorData: The attitude data class (or subclass) instance.
        """
        cls = AttitudeData
        if data.get("type", "").lower() == "lofoffset":
            cls = LofOffsetAttitudeData

        return dacite.from_dict(data_class=cls, data=data, config=DACITE_CONFIG)


@dataclass(frozen=True, kw_only=True)
class LofOffsetAttitudeData(AttitudeData):
    """An attitude described by a rotation from the Local-Orbit-Frame."""

    tx: RotationData
    """The rotation from LOF to the body frame."""


@dataclass(frozen=True, kw_only=True)
class SatelliteData(DisplayOptions):
    """Satellite data."""

    name: str
    """Satellite name."""
    catnr: Optional[int]
    """The catalog number, to use when downloading the TLE."""
    tle: Optional[TleData]
    """The orbit defined as a TLE."""
    keplerian: Optional[KeplerianOrbitData]
    """The orbit defined as a set of keplerian elements."""
    attitudes: List[AttitudeData] = field(default_factory=list)
    """List of attitude definitions."""
    sensors: List[SensorData] = field(default_factory=list)
    """List of sensor definitions."""
    lof: LOFTypeData = LOFTypeData.QSW
    """Local orbit frame definition."""
    filter: Optional[bool] = False
    """Filter flag, when True the satellite is ignored."""
    mass: Optional[Mass]
    """Spacecraft mass."""
    propagator: Optional[PropagatorConfiguration]
    """Propagator configuration."""


@dataclass(frozen=True, kw_only=True)
class EarthData(Dictable):
    """Definition of the earth model."""

    model: str = "wgs84"
    """Earth model name."""
    frameName: str = "itrf"
    """Fixed body frame of the model."""
    iersConventions: str = "2010"
    """Type of IERS conventions."""
    simpleEop: bool = False
    """Boolean flag indicating whether to ignore tidal effects."""


@dataclass(frozen=True, kw_only=True)
class Configuration:
    """Application configuration."""

    run: RunData
    """The run data."""
    satellites: Dict[str, SatelliteData]
    """Dictionary of the satellites by their unique id."""
    aois: AoiConfiguration = AoiConfiguration()
    """AOI configuration."""
    earth: EarthData = EarthData()
    """Earth model."""
    propagator: Optional[PropagatorConfiguration]
    """Defaults for satellite propagator construction."""
    extensions: Optional[Dict]
    """Details for any extensions."""

    @classmethod
    def from_dict(cls, data: dict):
        """Construct a Configuration instance from the provided data dictionary.

        Args:
            data (dict): data dictionary

        Returns:
            Configuration: The configuration instance.
        """
        return dacite.from_dict(
            data_class=cls,
            data=data,
            config=DACITE_CONFIG,
        )


def _to_distance(value) -> astropy.coordinates.Distance:
    if isinstance(value, (int, float)):
        return astropy.coordinates.Distance(value=value, unit=u.m)
    else:
        return astropy.coordinates.Distance(value=value)


def _to_angle(value) -> astropy.coordinates.Angle:
    if isinstance(value, (int, float)):
        return astropy.coordinates.Angle(value=value, unit=u.deg)
    else:
        return astropy.coordinates.Angle(value)


DACITE_CONFIG = dacite.Config(
    type_hooks={
        SensorData: SensorData.create,
        AttitudeData: AttitudeData.create,
        dt.datetime: isodate.parse_datetime,
        dt.timedelta: isodate.parse_duration,
        astropy.coordinates.Distance: _to_distance,
        astropy.coordinates.Angle: _to_angle,
    },
    cast=[LOFTypeData, Mass, Frequency, OrbitTypeData],
    strict=True,
)