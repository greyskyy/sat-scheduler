"""Sensor models."""
import astropy.units as u
import functools
import orekitfactory.factory

from org.hipparchus.geometry.euclidean.threed import Vector3D
from org.orekit.frames import StaticTransform, TransformProvider, TransformProviderUtils
from org.orekit.geometry.fov import DoubleDihedraFieldOfView, FieldOfView
from org.orekit.time import AbsoluteDate

from ..configuration import SensorData, CameraSensorData
from ..utils import FixedTransformProvider


class SensorModel:
    """Sensor model class."""

    def __init__(self, data: SensorData):
        """Class constructor.

        Args:
            data (SensorData): Sensor data class used to construct this object.
        """
        self.__data = data

        if data.frame is not None:
            tx = orekitfactory.factory.to_vector(data.frame.translation)
            r = orekitfactory.factory.to_rotation(
                x=orekitfactory.factory.to_vector(data.frame.x),
                y=orekitfactory.factory.to_vector(data.frame.y),
                z=orekitfactory.factory.to_vector(data.frame.z),
            )

            self.__bodyToSensor = FixedTransformProvider(tx=tx, r=r)
        else:
            self.__bodyToSensor = FixedTransformProvider()

    @property
    def id(self) -> str:
        """Unique sensor id."""
        return self.data.id

    @property
    def data(self) -> SensorData:
        """The SensorData backing this model."""
        return self.__data

    @property
    def bodyToSensorTxProv(self) -> TransformProvider:
        """Provider for the transformation from satellite body frame to sensor frame."""
        return self.__bodyToSensor

    @functools.cached_property
    def sensorToBodyTxProv(self) -> TransformProvider:
        """Provider for the transformation from sensor frame to satellite body frame."""
        return TransformProviderUtils.getReversedProvider(self.bodyToSensorTxProv)

    @property
    def has_fov(self) -> bool:
        """Flag indicating this sensor has a specific field of view."""
        return False

    @u.quantity_input
    def createFovInBodyFrame(self, angularMargin: u.Quantity[u.rad] = 1.0e-6 * u.rad) -> FieldOfView:
        """Create the FieldOfView in the satellite's body frame.

        Args:
            angularMargin (Quantity[u.rad], optional): Angular margin of the computation. Defaults to 1.0e-6*u.rad.

        Returns:
            FieldOfView: The sensor field of view.
        """
        tx = self.sensorToBodyTxProv.getStaticTransform(AbsoluteDate.ARBITRARY_EPOCH)
        return self.createFovInFrame(tx, angularMargin=angularMargin)

    def createFovInFrame(self, tx: StaticTransform, angularMargin: u.Quantity[u.rad] = 1.0e-6 * u.rad) -> FieldOfView:
        """Create the FieldOfView using the provided transform.

        This class is intended to be impletented by sub-classes. No default implementation is provided.

        Args:
            tx (StaticTransform): The transform from the sensor to the destination frame.
            angularMargin (Quantity[u.rad], optional): The angular margin. Defaults to 1.0e-6*u.rad.
        """
        raise NotImplementedError()


class CameraSensorModel(SensorModel):
    """Sensor model specification for camera sensors."""

    def __init__(self, data: CameraSensorData):
        """Class constructor.

        Args:
            data (CameraSensorData): The sensor data used to construct this object.
        """
        super().__init__(data)
        self.__hfov: u.Quantity[u.rad] = data.rows * data.pitch.si / data.focalLength.si * u.rad
        self.__vfov: u.Quantity[u.rad] = data.cols * data.pitch.si / data.focalLength.si * u.rad

    @property
    def hFov(self) -> u.Quantity[u.rad]:
        """The horizontal field of view angle."""
        return self.__hfov

    @property
    def vFov(self) -> u.Quantity[u.rad]:
        """The vertical field of view angle."""
        return self.__vfov

    @property
    def has_fov(self) -> bool:
        """Flag indicating this sensor has a specific field of view."""
        return True

    def createFovInFrame(self, tx: StaticTransform, angularMargin: u.Quantity[u.rad] = 1.0e-6 * u.rad) -> FieldOfView:
        """Create the FieldOfView using the provided transform.

        Args:
            tx (StaticTransform): The transform from the sensor to the destination frame.
            angularMargin (Quantity[u.rad], optional): The angular margin. Defaults to 1.0e-6*u.rad.

        Returns:
            FieldOfView: The sensor FieldOfView
        """
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
                float(self.hFov.to_value(u.rad) / 2.0),
                axis2,
                float(self.vFov.to_value(u.rad) / 2.0),
                float(angularMargin.to_value(u.rad)),
            )
        )


def construct_sensor_model(data: SensorData) -> SensorModel:
    """Create a sensor model.

    Args:
        data (SensorData): The data

    Returns:
        SensorModel: The sensor model
    """
    cls = SensorModel
    if isinstance(data, CameraSensorData):
        cls = CameraSensorModel

    return cls(data)
