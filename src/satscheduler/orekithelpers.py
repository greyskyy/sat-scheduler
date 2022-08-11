"""Series of utility methods supporting creation of orekit classes."""
from functools import singledispatch
from org.hipparchus.geometry.euclidean.threed import Rotation, Vector3D
from org.orekit.data import DataContext
from org.orekit.frames import Frame, StaticTransform, Transform, PythonTransformProvider
from org.orekit.models.earth import ReferenceEllipsoid
from org.orekit.utils import IERSConventions
from org.orekit.time import AbsoluteDate

def loadIersConventions(s:str, default:str=None) -> IERSConventions:
    """Convert a string to an iers convetions

    Args:
        s (str): The string to convert
        default (str, optional): The default to use if s is None. Defaults to None.

    Raises:
        ValueError: Triggered when the string cannot be converted

    Returns:
        IERSConventions: The convention
    """
    if s is None and default is None:
        return None
    
    safe = default if s is None else default
    lsafe = safe.lower()
    
    if lsafe == "iers_2010" or lsafe == "2010":
        return IERSConventions.IERS_2010
    elif lsafe == "iers_2003" or lsafe == "2003":
        return IERSConventions.IERS_2003
    elif lsafe == "iers_1996" or lsafe == "1996":
        return IERSConventions.IERS_1996
    else:
        raise ValueError(f"Invalid iers convention string {s}")

def frame(s:str, context:DataContext=None, 
          iersConventions:str=None,
          simpleEop:bool=False,
          **kwargs) -> Frame:
    """Construct an orekit Frame from the provided string.

    Args:
        s (str): Frame name
        context (DataContext, optional): Data context from which frames will be loaded. Defaults to None.
        iersConventions (str, optional): IERSConventions to use when loading an ITRF. Defaults to None.
        simpleEop (bool, optional): When True, tidal effects will be ignored when converting to an ITRF. Defaults to False.

    Raises:
        ValueError: When the string is None or describes an unknown frame

    Returns:
        Frame: The orekit frame instance
    """
    if s is None:
        raise ValueError("frame name must be specified")
    
    if context is None:
        context = DataContext.getDefault()
    
    if s.lower() == 'j2000' or s.lower() == 'eme2000':
        return context.getFrames().getEME2000()
    elif s.lower() == 'gcrf' or s.lower() == 'eci':
        return context.getFrames().getGCRF()
    elif s.lower() == 'itrf' or s.lower() == 'ecef' or s.lower() == 'ecf':
        iers = loadIersConventions(iersConventions, "iers_2010")
        return context.getFrames().getITRF(iers, simpleEop)
    else:
        raise ValueError(f"unknown frame type: {frame}")

def referenceEllipsoid(model:str="wgs84", frameName:str="itrf", **kwargs) -> ReferenceEllipsoid:
    """Create a reference ellipsoid from the string description.

    Args:
        model (str, optional): The model to use. Must be one of [wgs84, iers2010, iers2003, iers1996]. Defaults to "wgs84".
        frameName (str, optional): Name of the ellipsoid's body frame. Defaults to "itrf".

    Raises:
        ValueError: When an unknown reference ellipsoid model is provided

    Returns:
        ReferenceEllipsoid: The reference ellipsoid instance
    """
    if model is None:
        raise ValueError("reference ellipsoid name cannot be None")
    
    f = frame(frameName, **kwargs)
    lModel = model.lower()
    if lModel == "wgs84" or lModel == "wgs-84":
        return ReferenceEllipsoid.getWgs84(f)
    elif lModel == "iers2010" or lModel == "iers-2010" or lModel == "2010":
        return ReferenceEllipsoid.getIers2010(f)
    elif lModel == "iers2003" or lModel == "iers-2003" or lModel == "2003":
        return ReferenceEllipsoid.getIers2003(f)
    elif lModel == "iers1996" or lModel == "iers-1996" or lModel == "1996" or lModel.lower() == "iers96" or lModel.lower() == "iers-96" or lModel == "96":
        return ReferenceEllipsoid.getIers96(f)
    else:
        raise ValueError(f"Cannot convert unknown reference ellipsoid value {s}")

@singledispatch
def toVector(a:list[float]) -> Vector3D:
    """Create a vector from the provided list of numbers.
    
    The provided values are considered to be [x, y, z]. Any missing values will be assumed to be zero.

    Args:
        a (list[float], optional): List of numbers to convert.

    Returns:
        Vector3D: A vector instance
    """
    if a is None or len(a) == 0:
        return Vector3D.ZERO
    elif len(a) == 1:
        return Vector3D(float(a[0]), 0., 0.)
    elif len(a) == 2:
        return Vector3D(float(a[0]), float(a[1]), 0.)
    else:
        return Vector3D(float(a[0]), float(a[1]), float(a[2]))

@toVector.register
def _toVectorA(x:float, y:float=0., z:float=0) -> Vector3D:
    """Create a vector from the provide values.

    Args:
        x (float): The x value
        y (float, optional): The y value. Defaults to 0..
        z (float, optional): The z value. Defaults to 0.

    Returns:
        Vector3D: A new vector instance
    """
    return Vector3D(x, y, z)

def toRotation(x:Vector3D=None, y:Vector3D=None, z:Vector3D=None) -> Rotation:
    if Vector3D.ZERO.equals(x):
        x = None
    if Vector3D.ZERO.equals(y):
        y = None
    if Vector3D.ZERO.equals(z):
        z = None
        
    # if x is specified
    if not x is None:
        #x and y are specifed
        if not y is None:
            return Rotation(x, y, Vector3D.PLUS_I, Vector3D.PLUS_J)
        # if x and z are specfied
        elif not z is None:
            return Rotation(x, z, Vector3D.PLUS_I, Vector3D.PLUS_K)
        # if only x is specified
        else:
            return Rotation(x, Vector3D.PLUS_I)
    # x is not specified, by y is
    elif not y is None:
        # if y and z are specifed
        if not z is None:
            return Rotation(y, z, Vector3D.PLUS_J, Vector3D.PLUS_K)
        # only y is specified
        else:
            return Rotation(y, Vector3D.PLUS_J)
    # if only z is specified
    elif not z is None:
        return Rotation(z, Vector3D.PLUS_K)
    # none are specified
    else:
        return Rotation.IDENTITY

class FixedTransformProvider(PythonTransformProvider):
    """Transform provider for a fixed transformation, regardless of time called.

    Args:
        tx (Vector3D, Optional): translation from the parent to this frame. Defaults to `[0, 0, 0]`
        r (Rotation, Optional): rotation from the parent to this frame. Defaults to identity rotation.
    """
    def __init__(self, tx:Vector3D=None, r:Rotation=None):
        """Class constructor.

        Args:
            tx (Vector3D, optional): Translation vector. Defaults to None.
            r (Rotation, optional): Frame rotation. Defaults to None.
        """
        super().__init__()
        self.__tx = tx
        self.__r = r
    
    def getTransform(self, date:AbsoluteDate) -> Transform:
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
            if not self.__r is None:
                tx = Transform(date, self.__tx)
                r = Transform(date, self.__r)
                return Transform(date, tx, r)
            # only translation
            else:
                #return Transform.cast_(StaticTransform.of(date, self.__tx))
                return Transform(date, self.__tx)
    
    def getTransform_F(self, date):
        pass