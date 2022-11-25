"""Transform providers."""
from org.hipparchus.geometry.euclidean.threed import Rotation, Vector3D
from org.orekit.frames import Transform, PythonTransformProvider
from org.orekit.time import AbsoluteDate


class FixedTransformProvider(PythonTransformProvider):
    """Transform provider for a fixed transformation, regardless of time called.

    Args:
        tx (Vector3D, Optional): translation from the parent to this frame. Defaults
        to `[0, 0, 0]`
        r (Rotation, Optional): rotation from the parent to this frame. Defaults to
        identity rotation.
    """

    def __init__(self, tx: Vector3D = None, r: Rotation = None):
        """Class constructor.

        Args:
            tx (Vector3D, optional): Translation vector. Defaults to None.
            r (Rotation, optional): Frame rotation. Defaults to None.
        """
        super().__init__()
        self.__tx = tx
        self.__r = r

    def getTransform(self, date: AbsoluteDate) -> Transform:
        """Get the transfor at the absolute date.

        Args:
            date (AbsoluteDate): The date at which the transform is computed.

        Returns:
            Transform: The transform
        """
        # translation is unspecified
        if self.__tx is None:
            # if both are none, identity transform
            if self.__r is None:
                return Transform.IDENTITY
            # if only rotation
            else:
                return Transform(date, self.__r)
        # translation is specified
        else:
            # both translation and rotation are specified
            if self.__r is not None:
                tx = Transform(date, self.__tx)  # TODO: Do i need to negate this??
                r = Transform(date, self.__r)
                return Transform(date, tx, r)
            # only translation
            else:
                # return Transform.cast_(StaticTransform.of(date, self.__tx))
                return Transform(date, self.__tx)

    def getTransform_F(self, date):
        """Get the transfor at the absolute date.

        Args:
            date (AbsoluteDate): The date at which the transform is computed.

        Returns:
            Transform: The transform
        """
        pass
