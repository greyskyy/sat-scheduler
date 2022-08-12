from typing import Iterable
import folium
import satscheduler.aoi as aoi
import satscheduler.preprocessor as pre_processor

from astropy import units
from satscheduler.satellite import Satellite
from satscheduler.utils import OrekitUtils
from org.orekit.data import DataContext
from org.orekit.models.earth import ReferenceEllipsoid
from org.orekit.time import AbsoluteDate, DateTimeComponents
from threading import Thread
from satscheduler.aoi import Aoi
from satscheduler.preprocessor import Preprocessor, PreprocessedAoi
from satscheduler.satellite import Satellites
from satscheduler.utils import DateInterval, string_to_absolutedate, OrekitUtils



import logging


def saveMap(map: folium.Map, filename="index.html"):
    """
    Save the map to the file

    Args:
        map (folium.Map): The map object to save
        filename (str, optional): Filename where the map will be saved. Defaults to 'index.html'.
    """
    map.save(filename)

def doWork(
    vm,
    callable,
    test_mode:bool=False
):
    """
    Thread target. Attaches the thread to the orekit VM before executing the actual propagation work

    Args:
        workItem (WorkItem): The item of work
    """
    vm.attachCurrentThread()  # do this before any orekit in a background thread
    callable(test_mode=test_mode)

class Worker:
    def __init__(self, vm, callable, test_mode):
        self.vm = vm
        self.callable = callable
        self.test_mode = test_mode
    
    def __call__(self):
        self.vm.attachCurrentThread()
        self.callable(self.test_mode)


def run_preprocessing(
        vm,
        preprocessors:Iterable[Preprocessor]=[],
        args=None,
        config=None) -> list[PreprocessedAoi]:
    shouldThread = True
    if args and args.threading is not None:
        shouldThread = args.threading
    elif config and "run" in config and "multithread" in config["run"]:
        shouldThread = config["run"]["multithread"]
    
    if shouldThread:
        threads = []
        for p in preprocessors:
            thread = Thread(target=Worker(vm, p, args.test))
            thread.start()
            threads.append(thread)
        
        for thread in threads:
            thread.join()
    else:
        for p in preprocessors:
            p(args.test)

def scheduler(args=None, config=None, vm=None):
    """Schedule payload operations over a set of AOIs.

    Args:
        args (argparse.Namespace, optional): The command line arguments. Defaults to None.
        config (dict, optional): A dictionary loaded with the application configuration file's contents. Defaults to None.
        vm (_type_, optional): A reference to the orekit virtual machine. Defaults to None.
    """
    logger = logging.getLogger(__name__)

    logger.info("Initializing the scheduler")
    
    context = DataContext.getDefault()
    
    preprocessingResults = pre_processor.execute(args=args, vm=vm, config=config, context=context)
    

    saveMap(map, filename=args.output)
