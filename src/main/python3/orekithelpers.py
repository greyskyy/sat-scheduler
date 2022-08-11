from org.orekit.data import DataContext
from org.orekit.frames import Frame
from org.orekit.models.earth import ReferenceEllipsoid
from org.orekit.utils import Constants, IERSConventions

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