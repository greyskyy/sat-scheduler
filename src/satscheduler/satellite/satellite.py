from argparse import ArgumentError
from functools import cache, cached_property, lru_cache
from typing import Iterable
import astropy.units as u
from astropy.units import Quantity
from dataclasses import dataclass
from requests import get

from satscheduler.utils import FixedTransformProvider

import logging

from org.orekit.propagation import BoundedPropagator

from org.hipparchus.geometry.euclidean.threed import (
    Rotation,
    Vector3D,
    RotationConvention,
    RotationOrder,
)

from org.orekit.attitudes import (
    AttitudeProvider,
    LofOffset,
    NadirPointing,
    YawCompensation,
)
from org.orekit.bodies import BodyShape
from org.orekit.data import DataContext
from org.orekit.frames import (
    Frame,
    LOFType,
    StaticTransform,
    TransformProvider,
    TransformProviderUtils,
)

from org.orekit.geometry.fov import DoubleDihedraFieldOfView, FieldOfView
from org.orekit.models.earth import ReferenceEllipsoid
from org.orekit.orbits import OrbitType
from org.orekit.propagation import Propagator
from org.orekit.time import AbsoluteDate

import orekitfactory.factory


@dataclass(frozen=True)
class FrameData:
    translation: list[float] = (0.0, 0.0, 0.0)
    x: list[float] = None
    y: list[float] = None
    z: list[float] = None


@dataclass(frozen=True)
class SensorData:
    id: str
    type: str
    frame: dict


@dataclass(frozen=True)
class CameraSensorData(SensorData):
    focalLength: str
    pitch: str
    imgPeriod: str
    cols: int
    rows: int
    rowsAlongX: bool


class Sensor:
    def __init__(self, data: SensorData):
        self.__data = data

        if not data.frame is None:
            fdata = FrameData(**(data.frame))
            tx = orekitfactory.factory.to_vector(fdata.translation)
            r = orekitfactory.factory.to_rotation(
                x=orekitfactory.factory.to_vector(fdata.x),
                y=orekitfactory.factory.to_vector(fdata.y),
                z=orekitfactory.factory.to_vector(fdata.z),
            )

            self.__bodyToSensor = FixedTransformProvider(tx=tx, r=r)
        else:
            self.__bodyToSensor = FixedTransformProvider()

    @property
    def id(self) -> str:
        return self.data.id

    @property
    def data(self) -> SensorData:
        return self.__data

    @property
    def bodyToSensorTxProv(self) -> TransformProvider:
        return self.__bodyToSensor

    @cached_property
    def sensorToBodyTxProv(self) -> TransformProvider:
        return TransformProviderUtils.getReversedProvider(self.bodyToSensorTxProv)

    @u.quantity_input
    def createFov(self, angularMargin: Quantity[u.rad] = 1.0e-6 * u.rad) -> FieldOfView:
        return self._createFovInFrame(
            StaticTransform.getIdentity(), angularMargin=angularMargin
        )

    def createFovInBodyFrame(
        self, angularMargin: Quantity[u.rad] = 1.0e-6 * u.rad
    ) -> FieldOfView:
        tx = self.sensorToBodyTxProv.getStaticTransform(AbsoluteDate.ARBITRARY_EPOCH)
        return self._createFovInFrame(tx, angularMargin=angularMargin)

    def _createFovInFrame(
        self, tx: StaticTransform, angularMargin: Quantity[u.rad] = 1.0e-6 * u.rad
    ):
        raise NotImplementedError()


class CameraSensor(Sensor):
    def __init__(self, data: CameraSensorData):
        super().__init__(data)
        self.__hfov = (
            data.rows * Quantity(data.pitch).si / Quantity(data.focalLength).si * u.rad
        )
        self.__vfov = (
            data.cols * Quantity(data.pitch).si / Quantity(data.focalLength).si * u.rad
        )

    @property
    def hFov(self):
        return self.__hfov

    @property
    def vFov(self):
        return self.__vfov

    def _createFovInFrame(
        self, tx: StaticTransform, angularMargin: Quantity[u.rad] = 1.0e-6 * u.rad
    ):
        center = tx.transformVector(Vector3D.PLUS_K)
        if self.data.rowsAlongX:
            axis1 = tx.transformVector(Vector3D.PLUS_I)
            axis2 = tx.transformVector(Vector3D.PLUS_J)
        else:
            axis1 = tx.transformVector(Vector3D.PLUS_J)
            axis2 = tx.transformVector(Vector3D.PLUS_I)
        return FieldOfView.cast_(
            DoubleDihedraFieldOfView(
                center,
                axis1,
                float(self.hFov.value / 2.0),
                axis2,
                float(self.vFov.value / 2.0),
                float(angularMargin.to_value(u.rad)),
            )
        )


class Satellite:
    """
    Data object representing a single satellite
    """

    def __init__(self, id: str, config: dict):
        self.__config = config
        self.__id = id
        self.__name = config["name"]
        self.__propagator = None
        self.__inertialFrame = None
        self.__sensors = []
        self.__attitudes = {}

        tmp = []
        if "sensors" in config:
            for s in config["sensors"]:
                tmp.append(CameraSensor(CameraSensorData(**s)))
        self.__sensors: tuple[Sensor] = tuple(tmp)

    @property
    def id(self) -> str:
        """
        The satellite's id

        Returns:
            str: Unique id of the sallite
        """
        return self.__id

    @property
    def name(self) -> str:
        """The long name of the satellite

        Returns:
            str: Longer name of the satellite, defaults to the id if not set
        """
        return (
            self.__name == self.id
            if self.__name == None or len(self.__name) == 0
            else self.__name
        )

    @property
    def mass(self) -> float:
        """The satellite's mass, in kg

        Returns:
            float: the satellite's mass, in kg (defaults to 100kg if not set)
        """
        return float(self.__config["mass"]) if "mass" in self.__config else 100.0

    @property
    def showGroundTrace(self) -> bool:
        return self.__config["groundTrace"] if "groundTrace" in self.__config else True

    @property
    def displayColor(self) -> str:
        """The satellite's display color

        Returns:
            str: The satellite's display color
        """
        return self.__config["color"] if "color" in self.__config else "green"

    @property
    def groundTraceConfig(self) -> dict:
        return self.__config["groundTrace"] if "groundTrace" in self.__config else {}

    @property
    def missionConfig(self) -> dict:
        return self.__config["mission"] if "mission" in self.__config else {}

    @property
    def inertialFrame(self) -> Frame:
        if self.__inertialFrame is None:
            self.init()
        return self.__inertialFrame

    @property
    def propagator(self) -> Propagator:
        if self.__propagator is None:
            self.init()
        return self.__propagator

    @cached_property
    def lofType(self) -> LOFType:
        typeStr = self.__config["lof"] if "lof" in self.__config else "lvlh"

        typeStr = typeStr.upper()
        return LOFType.valueOf(typeStr)

    @property
    def sensors(self) -> tuple[Sensor]:
        return self.__sensors

    def getAttitudeProvider(self, name: str = None) -> AttitudeProvider:
        if name is None:
            return self.__attitudes[self.__defaultAtLaw]

        return self.__attitudes[name]

    def init(self, context: DataContext = None, earth: ReferenceEllipsoid = None):
        if context is None:
            context = DataContext.getDefault()

        if earth is None:
            earth = orekitfactory.factory.get_reference_ellipsoid(context=context)

        # Build the propagator
        if "catnr" in self.__config:
            catnr = int(self.__config["catnr"])
            r = get(
                f"https://celestrak.com/NORAD/elements/gp.php?CATNR={catnr}&FORMAT=TLE",
                headers={
                    "accept": "*/*",
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_3) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/99.0.4844.84 Safari/537.36",
                },
            )
            if not r.status_code == 200:
                raise RuntimeError(f"failed to load TLE for catalog number {catnr}")

            data = r.content.splitlines()
            tle = orekitfactory.factory.to_tle(
                line1=data[1], line2=data[2], context=context
            )
            self._initAttitudes(context.getFrames().getTEME(), context, earth)
            atProv = self.getAttitudeProvider("mission")
            self.__propagator = orekitfactory.factory.to_propagator(
                tle, mass=self.mass, context=context, attitudeProvider=atProv
            )
        elif "tle" in self.__config:
            tle = orekitfactory.factory.to_tle(
                **(self.__config["tle"]), context=context
            )
            self._initAttitudes(context.getFrames().getTEME(), context, earth)
            atProv = self.getAttitudeProvider("mission")
            self.__propagator = orekitfactory.factory.to_propagator(
                tle, mass=self.mass, context=context, attitudeProvider=atProv
            )
        elif "keplerian" in self.__config:
            orbit = orekitfactory.factory.to_orbit(
                **(self.__config["keplerian"]), context=context
            )
            self._initAttitudes(orbit.getFrame(), context, earth)
            atProv = self.getAttitudeProvider("mission")
            self.__propagator = orekitfactory.factory.to_propagator(
                orbit,
                mass=self.mass,
                context=context,
                attitudeProvider=atProv,
                orbitType=OrbitType.CARTESIAN,
                **(self.__config),
            )
        else:
            raise ValueError(f"cannot build propagator for satellite {self.id}")

        # inertial frame from the propagator
        self.__inertialFrame = self.__propagator.getFrame()

    def _initAttitudes(
        self,
        frame: Frame = None,
        context: DataContext = None,
        earth: ReferenceEllipsoid = None,
    ):
        if context is None:
            context = DataContext.getDefault()

        if frame is None:
            frame = context.getFrames().getGCRF()

        self.__attitudes = {}
        self.__defaultAtLaw = None
        if "attitudes" in self.__config:
            for item in self.__config["attitudes"]:
                name = item["name"]
                type = item["type"] if "type" in item else "LofOffset"

                if "default" in item and item["default"]:
                    self.__defaultAtLaw = name

                if "LofOffset" == type:
                    self.__attitudes[name] = self._buildLofOffsetProvider(item, frame)
                else:
                    raise ValueError(
                        f"Unknown attitude type [{type}] specified in config"
                    )

        if self.__defaultAtLaw is None and self.__attitudes:
            self.__defaultAtLaw = list(self.__attitudes.keys())[0]

    def _buildLofOffsetProvider(self, data: dict, frame: Frame) -> AttitudeProvider:
        if "lof" in data:
            lofType = LOFType.valueOf(data["lof"].upper())
        else:
            lofType = self.lofType

        if "tx" in data:
            x = (
                orekitfactory.factory.to_vector(data["tx"]["x"])
                if "x" in data["tx"]
                else None
            )
            y = (
                orekitfactory.factory.to_vector(data["tx"]["y"])
                if "y" in data["tx"]
                else None
            )
            z = (
                orekitfactory.factory.to_vector(data["tx"]["z"])
                if "z" in data["tx"]
                else None
            )
            rot = orekitfactory.factory.to_rotation(x, y, z)
        else:
            rot = Rotation.IDENTITY

        angles = rot.getAngles(RotationOrder.XYZ, RotationConvention.FRAME_TRANSFORM)
        return LofOffset(
            frame, lofType, RotationOrder.XYZ, angles[0], angles[1], angles[2]
        )

    def __str__(self) -> str:
        return (
            f"Satellite[id={self.id},sensors=["
            + ",".join([s.id for s in self.__sensors])
            + "]]"
        )


class Satellites:
    @staticmethod
    def load_from_config(config: dict) -> list[Satellite]:
        """Load the satellites from the provided configuration.

        Args:
            config (dict): The configuration dictionary loaded from the yaml file.

        Returns:
            list[Satellite]: List of satellite configuration objects
        """
        sats = []

        if "satellites" in config and not config["satellites"] == None:
            for key, value in config["satellites"].items():
                if "filter" in value and value["filter"]:
                    logging.getLogger(__name__).info("Filtering satellite %s", key)
                else:
                    sats.append(Satellite(key, value))

        return sats


@dataclass(frozen=True)
class ScheduleableSensor:
    id: str
    sat: Satellite
    ephemeris: BoundedPropagator
