from requests import get

from propagator import buildOrbit, buildTle, buildPropagator

from org.orekit.data import DataContext
from org.orekit.propagation import Propagator

class Satellite:
    """
    Data object representing a single satellite
    """
    def __init__(self, id:str, config:dict):
        self.__config = config
        self.__id = id
        self.__name = config['name']
        self.__propagator = None
    
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
    
    def buildPropagator(self, context:DataContext=None) -> Propagator:
        """Construct an orbit propagator for this satellite object
 
        Args:
        context (DataContext, optional): Data context to use when building, the default will be used if not provided. Defaults to None.

        Raises:
            RuntimeError: When an error occurs loading the TLE by catalog number
            ValueError: When a propagator cannot be built

        Returns:
            Propagator: The orbit propagator representing this satellite's orbit
        """
        
        if context is None:
            context = DataContext.getDefault()
        
        if self.__propagator == None:
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
            
        return self.__propagator

    