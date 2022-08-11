"""
Series of factory methods used to build orekit propgators and orbit definitions.
"""
from functools import singledispatch
from astropy.units import Quantity
from typing import Any

import orekit
from orekithelpers import frame as loadFrame, referenceEllipsoid

from org.hipparchus.ode.nonstiff import DormandPrince853Integrator
from org.orekit.attitudes import AttitudeProvider, InertialProvider
from org.orekit.bodies import CelestialBody
from org.orekit.data import DataContext
from org.orekit.forces.drag import DragForce, IsotropicDrag
from org.orekit.forces.gravity import HolmesFeatherstoneAttractionModel, ThirdBodyAttraction
from org.orekit.forces.gravity.potential import GravityFieldFactory
from org.orekit.forces.radiation import IsotropicRadiationClassicalConvention, SolarRadiationPressure
from org.orekit.time import AbsoluteDate, DateTimeComponents
from org.orekit.models.earth import ReferenceEllipsoid
from org.orekit.models.earth.atmosphere import HarrisPriester
from org.orekit.orbits import KeplerianOrbit, Orbit, OrbitType, PositionAngle
from org.orekit.propagation import Propagator, SpacecraftState
from org.orekit.propagation.analytical.tle import TLE, TLEPropagator
from org.orekit.propagation.numerical import NumericalPropagator
from org.orekit.utils import Constants, IERSConventions

def buildTle(line1:str, line2:str, context:DataContext=None) -> TLE:
    """
    Build a TLE from the input lines

    Args:
        line1 (str): Line 1 of the TLE
        line2 (str): Line 2 of the TLE
        context (DataContext, optional): Data context to use when building, the default will be used if not provided. Defaults to None.

    Returns:
        TLE: The TLE object
    """
    if context is None:
        context = DataContext.getDefault()
    
    utc = context.getTimeScales().getUTC()
    
    return TLE(line1, line2, utc)

def buildOrbit(a:Any, e:Any, i:Any, omega:Any, w:Any, epoch:str, frame:str=None, v:Any=None, m:Any=None, context:DataContext=None, mu:float=None) -> Orbit:
    """
    Build an orbit from the provided values.
    
    Args:
        a (Any): The semi-major axis of the orbit, as a string parsable by astropy.units.Quantity. If a number, must be in meters.
        e (Any): The orbital eccentricity
        i (Any): The inclination of the orbit, as a string parsable by astropy.units.Quantity. If a number, must be in radians.
        omega (Any): The right ascension of ascending node of the orbit, as a string parsable by astropy.units.Quantity. If a number, must be in radians.
        w (Any): The perigee argument of the orbit, as a string parsable by astropy.units.Quantity. If a number, must be in radians.
        epoch (str): epoch time as an ISO-8601 string
        frame (str, optional): Frame in which the orbit is defined. Valid values are GCRF or EME2000. If None, gcrf will be used. Defaults to None.
        v (Any, optional): Orbital true anomaly as a number in radians, or a string parsable by astropy.units.Quantity. Defaults to None.
        m (Any, optional): Orbital mean anomaly as a number in radians, or a string parsable by astropy.units.Quantity.. Defaults to None.
        context (DataContext, optional): Data context to use when building, the default will be used if not provided. Defaults to None.
        mu (float, optional): Central body attraction coefficient. If unspecified the earth's WGS-84 constant is used. Defaults to None.

    Raises:
        ValueError: when a required parameter is unspecified or specified but cannot be parsed

    Returns:
        Orbit: The orbit.
    """
    # TODO: handle EquinoctialOrbit and CircularOrbit construction
    if context is None:
        context = DataContext.getDefault()
    
    if mu is None:
        mu = Constants.WGS84_EARTH_MU
    
    aValue = Quantity(a).si
    eValue = float(e)
    iValue = Quantity(i).si
    omegaValue = Quantity(omega).si
    wValue = Quantity(w).si
    
    if not v is None:
        type = PositionAngle.TRUE
        anom = Quantity(v).si
    elif not m is None:
        type = PositionAngle.MEAN
        anom = Quantity(m).si
    else:
        raise ValueError("either true or mean anomaly must be specified")
    
    if not frame is None:
        frameValue = loadFrame(frame, context=context)
    else:
        frameValue = context.getFrames().getGCRF()
        
    epochValue = AbsoluteDate(DateTimeComponents.parseDateTime(epoch), context.getTimeScales().getUTC())
    return KeplerianOrbit(float(aValue.value), eValue, float(iValue.value), float(wValue.value), float(omegaValue.value), float(anom.value), type, frameValue, epochValue, mu)

@singledispatch
def buildPropagator(tle:TLE, attitudeProvider:AttitudeProvider=None, mass:float=100., context:DataContext=None, **kwargs) -> Propagator:
    """Generate a propagator from a TLE

    Args:
        tle (TLE): The two line element
        attitudeProvider (AttitudeProvider, optional): The attitude provider to use when propagating. Defaults to None.
        mass (float, optional): mass of the spacecraft in kg. Defaults to 100..
        context (DataContext, optional): Data context to use when building the propagator. If None, the default will be used. Defaults to None.

    Returns:
        Propagator: _description_
    """
    if context is None:
        context = DataContext.getDefault()
    
    teme = context.getFrames().getTEME()
    if attitudeProvider is None:
        attitudeProvider = InertialProvider.of(teme)
    
    return TLEPropagator.selectExtrapolator(tle, attitudeProvider, mass, teme)

@buildPropagator.register
def _(orbit:Orbit, attitudeProvider:AttitudeProvider=None, mass:float=100.,
                    centralBody:ReferenceEllipsoid=None,
                    context:DataContext=None,
                    minStep:float=0.001,
                    maxStep:float=1000.,
                    positionTolerance:float=10.,
                    considerGravity:bool=True,
                    gravityFieldDegree:int=2,
                    gravityFieldOrder:int=2,
                    considerSolarPressure:bool=True,
                    sun:CelestialBody=None,
                    solarPressureCrossSection:float=1.,
                    solarCa:float=0.2,
                    solarCs:float=0.8,
                    considerAtmosphere:bool=True,
                    atmosphereCrossSection:float=1.,
                    atmosphereDragCoeff:float=2.2,
                    bodies:list=['sun','moon','jupiter'],
                    **kwargs) -> Propagator:
    """
    Generate a propagator from an Orbit definition

    Args:
        orbit (Orbit): The orbit for which a numerical propagtor will be built
        attitudeProvider (AttitudeProvider, optional): The attitude provider to use when propagating. Defaults to None.
        mass (float, optional): mass of the spacecraft in kg. Defaults to 100.
        centralBody (ReferenceEllipsoid, optional): Central body, the WGS-84 ellipsoid will be used if unspecified. Defaults to None.
        context (DataContext, optional): Data context to use when building the propagator. If None, the default will be used. Defaults to None.
        minStep (float, optional): Minimum time step to take during propagation, in seconds. Defaults to 0.001.
        maxStep (float, optional): Maxmimum time step to take during propagation, in seconds. Defaults to 1000..
        positionTolerance (float, optional): Positional tolerance during propagation, in meters. Defaults to 10..
        considerGravity (bool, optional): Indication whether to consider a gravity model during propagation. Defaults to True.
        gravityFieldDegree (int, optional): Degree of the gravity field (use 10 for high fidelity, 2 for low). Defaults to 2.
        gravityFieldOrder (int, optional): Order of the gravity field (use 10 for high fidelity and 2 for low). Defaults to 2.
        considerSolarPressure (bool, optional): Indication whether to consider solar pressure during propagation. Defaults to True.
        sun (CelestialBody, optional): Sun location, default will be loaded if not provided. Defaults to None.
        solarPressureCrossSection (float, optional): Cross section facing the solar pressure vector, in square meters. Defaults to 1..
        solarCa (float, optional): solar absorption coefficient. Defaults to 0.2.
        solarCs (float, optional): solar reflection coefficient. Defaults to 0.8.
        considerAtmosphere (bool, optional): Indication whether to include atmospheric drag. Defaults to True.
        atmosphereCrossSection (float, optional): Cross section facing the drag force, in square meters. Defaults to 1..
        atmosphereDragCoeff (float, optional): drag coefficient. Defaults to 4..
        bodies (list, optional): List of celestial bodies whose gravitational effects will be considered. Defaults to ['sun','moon','jupiter'].

    Returns:
        Propagator: the propagator
    """
    if context is None:
        context = DataContext.getDefault()
    
    if centralBody is None:
        centralBody = referenceEllipsoid("wgs84", frameName="itrf", simpleEop=False, iersConventions="iers2010")
    
    tolerances = NumericalPropagator.tolerances(positionTolerance, orbit, orbit.getType())
    integrator = DormandPrince853Integrator(minStep, maxStep, orekit.JArray('double').cast_(tolerances[0]), orekit.JArray('double').cast_(tolerances[1]))
    
    propagator = NumericalPropagator(integrator)
    propagator.setOrbitType(OrbitType.CIRCULAR)# orbit.getType())
    
    if considerGravity:
        gravityProvider = GravityFieldFactory.getNormalizedProvider(gravityFieldDegree, gravityFieldOrder)
        gravityForceModel = HolmesFeatherstoneAttractionModel(centralBody.getBodyFrame(), gravityProvider)
        propagator.addForceModel(gravityForceModel)
    
    if considerSolarPressure:
        if sun is None:
            sun = context.getCelestialBodies().getSun()
            
        convention = IsotropicRadiationClassicalConvention(solarPressureCrossSection, solarCa, solarCs)
        solarPressure = SolarRadiationPressure(sun, centralBody.getEquatorialRadius(), convention)
        propagator.addForceModel(solarPressure)
    
    if considerAtmosphere:
        if sun is None:
            sun = context.getCelestialBodies().getSun()
            
        atmosphere = HarrisPriester(sun, centralBody)
        drag = IsotropicDrag(atmosphereCrossSection, atmosphereDragCoeff)
        dragForce = DragForce(atmosphere, drag)
        propagator.addForceModel(dragForce)
    
    if not bodies is None:
        for bodyName in bodies:
            body = context.getCelestialBodies().getBody(bodyName)
            if not body is None:
                propagator.addForceModel(ThirdBodyAttraction(body))
    
    initialState = SpacecraftState(orbit)
    propagator.setInitialState(initialState)
    
    if attitudeProvider is None:
        attitudeProvider = InertialProvider.of(initialState.getFrame())
    propagator.setAttitudeProvider(attitudeProvider)
    
    return propagator
