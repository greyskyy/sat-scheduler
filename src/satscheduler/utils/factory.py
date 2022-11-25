"""Misc factory methods used throughout the scheduler."""
import orekitfactory.factory
import requests

from org.hipparchus.geometry.euclidean.threed import Rotation, RotationConvention, RotationOrder
from org.orekit.attitudes import AttitudeProvider, LofOffset
from org.orekit.data import DataContext
from org.orekit.frames import Frame, LOFType
from org.orekit.models.earth import ReferenceEllipsoid
from org.orekit.orbits import Orbit, OrbitType
from org.orekit.propagation import Propagator
from org.orekit.propagation.analytical.tle import TLE

from ..configuration import get_config, PropagatorConfiguration, SatelliteData, AttitudeData, LofOffsetAttitudeData

_REFERENCE_ELLIPSOID = None


def get_reference_ellipsoid(context: DataContext = None) -> ReferenceEllipsoid:
    """Build the reference ellipsoid from the loaded configuration.

    The resulting value is cached for subsequent calls.

    Returns:
        ReferenceEllipsoid: The reference ellipsoid described in the configuration.
    """
    global _REFERENCE_ELLIPSOID

    if _REFERENCE_ELLIPSOID is None:
        config = get_config()
        _REFERENCE_ELLIPSOID = orekitfactory.factory.get_reference_ellipsoid(
            model=config.earth.model,
            frameName=config.earth.frameName,
            iersConventions=config.earth.iersConventions,
            simpleEop=config.earth.simpleEop,
            context=context,
        )

    return _REFERENCE_ELLIPSOID


def build_orbit(sat: SatelliteData, context: DataContext = None) -> TLE | Orbit:
    """Build the satellite orbit from the provided satellite data.

    Args:
        sat (SatelliteData): The satellite data.
        context (DataContext, optional): The context to use. If not provided, the default will be
        used. Defaults to None.

    Raises:
        RuntimeError: When the orbit is defined by a catnr and it cannot be retrieved from the internet.
        ValueError: When the orbit cannot be created from the provided satellite data.

    Returns:
        TLE | Orbit: The resulting satellite orbit.
    """
    if sat.catnr:
        catnr = sat.catnr
        r = requests.get(
            f"https://celestrak.com/NORAD/elements/gp.php?CATNR={catnr}&FORMAT=TLE",
            headers={
                "accept": "*/*",
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_3) AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/99.0.4844.84 Safari/537.36",
            },
        )
        if not r.status_code == 200:
            raise RuntimeError(f"failed to load TLE for catalog number {catnr}")

        data = r.content.splitlines()
        return orekitfactory.factory.to_tle(line1=data[1], line2=data[2], context=context)
    elif sat.tle:
        return orekitfactory.factory.to_tle(line1=sat.tle.line1, line2=sat.tle.line2, context=context)
    elif sat.keplerian:
        d = sat.keplerian.as_dict()
        return orekitfactory.factory.to_orbit(
            d.pop("a"), d.pop("e"), d.pop("i"), d.pop("omega"), d.pop("w"), d.pop("epoch"), context=context, **d
        )
    else:
        raise ValueError(f"unknown orbit type for satellite id={sat.id}")


def build_propagator(orbit, config: PropagatorConfiguration, **kwargs) -> Propagator:
    """Build a propagator object.

    Additional keyword arguments are passed directly to `orekitfactory.factory.to_propagator`

    Args:
        orbit (TLE|Orbit): The orbit (or TLE) definition.
        config (PropagatorConfiguration): Configuration

    Returns:
        Propagator: The propagation
    """
    # first merge any arguments
    if config:
        args = config.as_dict() | kwargs
    else:
        args = kwargs

    # now, fix a few arguments
    if args.get("orbitType", None):
        # convert OrbitTypeData to OrbitType
        args["orbitType"] = OrbitType.valueOf(args["orbitType"].name.upper())

    if args.get("bodies", None):
        args["bodies"] = [b.name.lower() for b in args["bodies"]]

    # remove any `None` fields
    to_remove = [k for k in args if args[k] is None]
    for k in to_remove:
        del args[k]

    return orekitfactory.factory.to_propagator(orbit, **args)


def build_attitude_provider(sat: SatelliteData, data: AttitudeData, inertial_frame: Frame) -> AttitudeProvider:
    """Build an attitude model based on the attitude data.

    Args:
        sat (SatelliteData): The satellite data
        data (AttitudeData): The attitude data
        inertial_frame (Frame): The inertial frame used in propagation.

    Raises:
        ValueError: Raised when the attitude provider type cannot be determined from the attitude data.

    Returns:
        AttitudeProvider: The attitude provider.
    """
    if isinstance(data, LofOffsetAttitudeData):
        return build_lof_offset_provider(sat, data, inertial_frame)
    else:
        raise ValueError(f"Unknown attitude specified in config [sat_name={data.name},at_type={data.type}")


def build_lof_offset_provider(
    sat: SatelliteData, data: LofOffsetAttitudeData, inertial_frame: Frame
) -> AttitudeProvider:
    """Build a LofOffset attitude provider.

    Args:
        sat (SatelliteData): The satellite data.
        data (LofOffsetAttitudeData): The attitude model data.
        inertial_frame (Frame): The frame of the inertial frame. This should be the frame used in the propagator.

    Returns:
        AttitudeProvider: The LofOFfset attitude provider.
    """
    if data.tx:
        x = orekitfactory.factory.to_vector(data.tx.x)
        y = orekitfactory.factory.to_vector(data.tx.y)
        z = orekitfactory.factory.to_vector(data.tx.z)
        rot = orekitfactory.factory.to_rotation(x, y, z)
    else:
        rot = Rotation.IDENTITY

    lof_type = LOFType.valueOf(sat.lof.name)

    # rotation from body -> lof; we need angles from lof -> body
    angles = rot.revert().getAngles(RotationOrder.XYZ, RotationConvention.FRAME_TRANSFORM)
    return LofOffset(inertial_frame, lof_type, RotationOrder.XYZ, angles[0], angles[1], angles[2])


def clear_factory():
    """Clear all cached factory objects."""
    global _REFERENCE_ELLIPSOID
    _REFERENCE_ELLIPSOID = None
