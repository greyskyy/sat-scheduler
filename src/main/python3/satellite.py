if '__main__' == __name__:
    import orekit
    orekit.initVM()

from asyncio import CancelledError
from dataclasses import dataclass
from requests import get

from orekithelpers import toVector, toRotation, FixedTransformProvider

from propagator import buildOrbit, buildTle, buildPropagator

from org.orekit.data import DataContext
from org.orekit.frames import Frame, Transform, TransformProvider, TransformProviderUtils
from org.orekit.propagation import Propagator
from org.orekit.time import AbsoluteDate

@dataclass(frozen=True)
class FrameData:
    translation:list[float]=(0., 0., 0.)
    x:list[float]=None
    y:list[float]=None
    z:list[float]=None

@dataclass(frozen=True)
class CameraSensorData:
    id:str
    type:str
    focalLength:str
    pitch:str
    imgPeriod:str
    cols:int
    rows:int
    frame:dict

class CameraSensor:
    
    def __init__(self, data:CameraSensorData):
        self.__data = data
        self.__bodyToSensor = None
        
        if not data.frame is None:
            fdata = FrameData(**(data.frame))
            tx = toVector(fdata.translation)
            r = toRotation(x=toVector(fdata.x), y=toVector(fdata.y), z=toVector(fdata.z))

            self.__bodyToSensor = FixedTransformProvider(tx=tx, r=r)
        else:
            self.__bodyToSensor = FixedTransformProvider()
    
    @property
    def bodyToSensorTxProv(self) -> TransformProvider:
        return self.__bodyToSensor
            

class Satellite:
    """
    Data object representing a single satellite
    """
    def __init__(self, id:str, config:dict):
        self.__config = config
        self.__id = id
        self.__name = config['name']
        self.__propagator = None
        self.__inertialFrame = None
        self.__sensors=[]
        
        if 'sensors' in config:
            for s in config['sensors']:
                self.__sensors.append(CameraSensor(CameraSensorData(**s)))
            
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
        return self.__name == self.id if self.__name == None or len(self.__name) == 0 else self.__name
    
    @property
    def mass(self) -> float:
        """The satellite's mass, in kg
        
        Returns:
            float: the satellite's mass, in kg (defaults to 100kg if not set)
        """
        return float(self.__config['mass']) if 'mass' in self.__config else 100.
    
    @property
    def showGroundTrace(self) -> bool:
        return self.__config['groundTrace'] if 'groundTrace' in self.__config else True
        
    @property
    def displayColor(self) -> str:
        """The satellite's display color

        Returns:
            str: The satellite's display color
        """
        return self.__config['color'] if 'color' in self.__config else 'green'
    
    @property
    def groundTraceConfig(self) -> dict:
        return self.__config['groundTrace'] if 'groundTrace' in self.__config else {}
    
    @property
    def missionConfig(self) -> dict:
        return self.__config['mission'] if 'mission' in self.__config else {}
    
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
    
    @property
    def sensorCount(self) -> int:
        return len(self.__sensors)
    
    def getSensor(self, idx:int=0) -> CameraSensor:
        return self.__sensors[idx]
    
    def init(self, context:DataContext=None):
        if context is None:
            context = DataContext.getDefault()
        
        # Build the propagator
        if 'catnr' in self.__config:
            catnr = int(self.__config['catnr'])
            r = get(f"https://celestrak.com/NORAD/elements/gp.php?CATNR={catnr}&FORMAT=TLE", headers={
                "accept":"*/*",
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_3) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/99.0.4844.84 Safari/537.36'
            })
            if not r.status_code == 200:
                raise RuntimeError(f"failed to load TLE for catalog number {catnr}")
            
            data = r.content.splitlines()
            tle = buildTle(line1=data[1], line2=data[2], context=context)
            self.__propagator = buildPropagator(tle, mass=self.mass, context=context)
        elif 'tle' in self.__config:
            tle = buildTle(**(self.__config['tle']), context=context)
            self.__propagator = buildPropagator(tle, mass=self.mass, context=context)
        elif 'keplerian' in self.__config:
            orbit = buildOrbit(**(self.__config['keplerian']), context=context)
            print(orbit)
            self.__propagator = buildPropagator(orbit, mass=self.mass, context=context, **(self.__config))
        else:
            raise ValueError(f"cannot build propagator for satellite {self.id}")
        
        # inertial frame from the propagator
        self.__inertialFrame = self.__propagator.getFrame()

if '__main__' == __name__:
    import yaml
    import json
    
    from org.hipparchus.geometry.euclidean.threed import Vector3D
    with open('config.yaml', 'r') as file:
        config = yaml.safe_load(file)
    
    if 'satellites' in config and not config['satellites'] == None:
        for key, value in config['satellites'].items():
            s = Satellite(key, value)
            
            if s.sensorCount > 0:
                print(s.id)
                print(s.getSensor().bodyToSensorTxProv.getTransform(AbsoluteDate.ARBITRARY_EPOCH).getInverse().transformVector(Vector3D.PLUS_J))
            