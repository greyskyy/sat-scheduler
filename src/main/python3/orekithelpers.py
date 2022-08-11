
from functools import singledispatch
from org.hipparchus.geometry.euclidean.threed import Rotation, Vector3D
from org.orekit.data import DataContext
from org.orekit.frames import Frame, Transform, PythonTransformProvider
from org.orekit.models.earth import ReferenceEllipsoid
from org.orekit.utils import Constants, IERSConventions
from org.orekit.time import AbsoluteDate, FieldAbsoluteDate

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
def toVector(a=list[float]) -> Vector3D:
    if a is None or len(a) == 0:
        return Vector3D.ZERO
    elif len(a) == 1:
        return Vector3D(float(a[0]), 0., 0.)
    else:
        return Vector3D(float(a[0]), float(a[1]), float(a[2]))

@toVector.register
def _toVectorA(x:float, y:float=0., z:float=0) -> Vector3D:
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
    
    def __init__(self, tx:Vector3D=None, r:Rotation=None):
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
                rot = Transform(date, self.__r)
                
                return Transform(date, tx, rot)
            # only translation
            else:
                return Transform(date, self.__tx)
    
    def getTransform_F(self, date):
        pass