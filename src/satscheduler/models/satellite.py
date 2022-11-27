"""Satellite models."""
import astropy.units as u
import typing

from org.orekit.attitudes import AttitudeProvider
from org.orekit.data import DataContext
from org.orekit.frames import Frame
from org.orekit.models.earth import ReferenceEllipsoid
from org.orekit.orbits import Orbit
from org.orekit.propagation import Propagator
from org.orekit.propagation.analytical.tle import TLE

from ..configuration import get_config, SatelliteData, PropagatorConfiguration, Configuration
from ..configuration.units import Mass
from .sensor import SensorModel, construct_sensor_model
from ..utils import get_reference_ellipsoid, build_propagator, build_orbit, build_attitude_provider


class SatelliteModel:
    """A single satellite model."""

    def __init__(
        self,
        id: str,
        data: SatelliteData,
        orbit: Orbit | TLE,
        orbit_frame: Frame,
        propagator: Propagator,
        sensors: typing.Sequence[SensorModel],
        attitudes: typing.Dict[str, AttitudeProvider],
        default_attitude_law: str,
        mass: Mass = None,
    ):
        """Class constructor.

        Args:
            id (str): Satellite id.
            data (SatelliteData): Satellite data.
            orbit (Orbit | TLE): Orbit definition.
            orbit_frame (Frame): Local orbit frame.
            propagator (Propagator): Satellite propagator
            sensors (typing.Sequence[SensorModel]): Satellite sensor models.
            attitudes (typing.Dict[str, AttitudeProvider]): Sattelite attitude providers, indexed by mode name.
            default_attitude_law (str): Name of the default attitude law.
            mass (Mass, optional): Satellite mass. If None, the mass will be used from the data. Defaults to None.
        """
        self.__id = id
        self.__data = data
        self.__orbit = orbit
        self.__orbit_frame = orbit_frame
        self.__propagator = propagator
        self.__sensors = tuple(sensors)
        self.__attitudes = attitudes
        self.__defaultAtLaw = default_attitude_law
        self.__mass = mass or data.mass

    @property
    def id(self) -> str:
        """The satellite's id."""
        return self.__id

    @property
    def data(self) -> SatelliteData:
        """The satellite data."""
        return self.__data

    @property
    def name(self) -> str:
        """The long name of the satellite."""
        return self.data.name if self.data.name else self.__id

    @property
    def mass(self) -> u.Quantity:
        """The satellite's mass."""
        return self.__mass

    @property
    def inertial_frame(self) -> Frame:
        """The inertial frame of this satellite, used in propagation."""
        return self.propagator.getFrame()

    @property
    def propagator(self) -> Propagator:
        """The satellite propagator."""
        if self.__propagator is None:
            self.init()
        return self.__propagator

    @property
    def sensors(self) -> tuple[SensorModel]:
        """The list of sensors on this satellite platform."""
        return self.__sensors

    @property
    def orbit(self) -> TLE | Orbit:
        """The satellite's orbit definition."""
        return self.__orbit

    @property
    def orbit_frame(self) -> Frame:
        """The local orbit frame."""
        self.__orbit_frame

    def sensor(self, id: str) -> SensorModel:
        """Locate the sensor with the defined id.

        Args:
            id (str): The sensor id.

        Returns:
            SensorModel: the sensor, or None if no sensor matches the id.
        """
        for s in self.__sensors:
            if s.id == id:
                return s

        return None

    def getAttitudeProvider(self, name: str = None) -> AttitudeProvider:
        """Get the attitude provider for the specifed mode.

        Args:
            name (str, optional): The attitude mode name. Defaults to None.

        Returns:
            AttitudeProvider: The provider for the specified attitude mode
        """
        if name is None:
            return self.__attitudes[self.__defaultAtLaw]

        return self.__attitudes[name]

    def __str__(self) -> str:
        """Represent this model as a string.

        Returns:
            str: The string summary for this object.
        """
        return f"Satellite[id={self.id},sensors=[" + ",".join([s.id for s in self.__sensors]) + "]]"


def construct_satellite_model(
    id: str, data: SatelliteData, context: DataContext = None, earth: ReferenceEllipsoid = None
) -> SatelliteModel:
    """Construct a SatelliteModel instance.

    This method builds the necessary data objects and provides them to the `SatelliteModel` constructor.

    Args:
        id (str): The unique satellite id.
        data (SatelliteData): The backing data for this model.
        context (DataContext, optional): The data context to use while building the model. If None, the default
        context will be used. Defaults to None.
        earth (ReferenceEllipsoid, optional): The reference ellipsoid to use when building the propagator. The
        WGS-84 ellipsoid will be used if None. Defaults to None.

    Returns:
        SatelliteModel: The contructed satellite model.
    """
    # set the context
    if context is None:
        context = DataContext.getDefault()

    # built earth reference
    if earth is None:
        earth = get_reference_ellipsoid(context=context)

    # build propagator configuration
    config = get_config()
    propagator_config: PropagatorConfiguration = PropagatorConfiguration.union(config.propagator, data.propagator)

    # build the orbit and the orbit frame
    orbit = build_orbit(data, context)
    orbit_frame: Frame = orbit.getFrame() if isinstance(orbit, Orbit) else context.getFrames().getTEME()

    # initialize the attitudes, get the mission attitude provider
    attitudes = {}
    defaultAtLaw = None
    atProv = None
    if data.attitudes:
        for item in data.attitudes:
            attitudes[item.name] = build_attitude_provider(data, item, orbit_frame)
            if item.default:
                defaultAtLaw = item.name

        if defaultAtLaw is None and attitudes:
            defaultAtLaw = list(attitudes.keys())[0]

        atProv = attitudes["mission"]

    # build the propagator
    mass = data.mass or Mass("100 kg")
    propagator = build_propagator(
        orbit,
        config=propagator_config,
        mass=mass,
        context=context,
        attitudeProvider=atProv,
        centralBody=earth,
    )

    # build the sensor models
    sensors = (construct_sensor_model(d) for d in data.sensors)

    return SatelliteModel(
        id=id,
        data=data,
        orbit=orbit,
        orbit_frame=orbit_frame,
        sensors=sensors,
        attitudes=attitudes,
        propagator=propagator,
        default_attitude_law=defaultAtLaw,
        mass=mass,
    )


def load_satellite_models(
    config: Configuration = None, context: DataContext = None, earth: ReferenceEllipsoid = None
) -> tuple[SatelliteModel]:
    """Load satellite models from the application configuration.

    Args:
        config (Configuration, optional): The application cofiguration. The global config will be retrieved
        if None. Defaults to None.
        context (DataContext, optional): The data context to use during construction. If None, the default
        context will be used. Defaults to None.
        earth (ReferenceEllipsoid, optional): The earth ellipsoid to use. If None, WGS-84 will be used. Defaults
        to None.

    Returns:
        tuple[SatelliteModel]: List of satellite models loaded from the configuration.
    """
    if config is None:
        config = get_config()

    return tuple(
        construct_satellite_model(id, data, context=context, earth=earth)
        for id, data in config.satellites.items()
        if not data.filter
    )
