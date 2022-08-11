'''
Satellite analytics engine
'''

import argparse
from typing import Any
import folium
import orekit
import yaml

from aoi import AoiCollection
from satellite import Satellite

from dataloader import download
from orekit.pyhelpers import setup_orekit_curdir
from orekithelpers import referenceEllipsoid
from org.orekit.data import DataContext
from org.orekit.models.earth import ReferenceEllipsoid
from org.orekit.time import AbsoluteDate, DateTimeComponents
from threading import Thread
from worker import WorkItem, execute

# initialize the orekit java vm
vm = orekit.initVM()

def parseArgs() -> tuple[argparse.Namespace, dict]:
    """Parse commandline arguments

    Returns:
        argparse.Namespace: the parse arguments
    """
    parser = argparse.ArgumentParser()
    parser.add_argument('-o', '--output',
                        help='Output html file.',
                        type=str,
                        default='index.html')
    parser.add_argument('-c', '--config',
                        help='path to the configuration yaml file',
                        type=str,
                        default='config.yaml')
    
    args = parser.parse_args()
    
    with open(args.config, 'r') as file:
        config = yaml.safe_load(file)
    
    return (args, config)

def saveMap(map:folium.Map, filename='index.html'):
    """
    Save the map to the file

    Args:
        map (folium.Map): The map object to save
        filename (str, optional): Filename where the map will be saved. Defaults to 'index.html'.
    """
    map.save(filename)

def initOrekit(config):
    """
    Initialize the orekit data, download if necessary.
    """
    filePath = download(config['data'])
    
    setup_orekit_curdir(filename=filePath)

def loadSatellites(config:dict) -> list[Satellite]:
    """
    Load the satellites from the provided configuration

    Args:
        config (dict): The configuration dictionary loaded from the yaml file.

    Returns:
        list[Satellite]: List of satellite configuration objects
    """
    sats = []
    
    if 'satellites' in config and not config['satellites'] == None:
        for key, value in config['satellites'].items():
            if 'filter' in value and value['filter']:
                print (f"filtering satellite {key}")
            else:
                sats.append(Satellite(key, value))
    
    return sats

def timespan(config:dict, context:DataContext=None) -> tuple[AbsoluteDate,AbsoluteDate]:
    """
    Compute the execution timespan based on the configuration.

    Args:
        config (dict): the configuration dictionary
        context (DataContext, optional): The data context, if None, the default context will be used

    Returns:
        tuple[AbsoluteDate,AbsoluteDate]: _description_
    """
    
    if context is None:
        context = DataContext.getDefault()
        
    t0 = config['run']['start']
    t1 = config['run']['stop']
    
    return (AbsoluteDate(DateTimeComponents.parseDateTime(t0), context.getTimeScales().getUTC()),
            AbsoluteDate(DateTimeComponents.parseDateTime(t1), context.getTimeScales().getUTC()))

def doWork(workItem:WorkItem, earth:ReferenceEllipsoid=None, context:DataContext=None, **kwargs):
    """
    Thread target. Attaches the thread to the orekit VM before executing the actual propagation work

    Args:
        workItem (WorkItem): The item of work
    """
    vm.attachCurrentThread() # do this before any orekit in a background thread
    execute(item=workItem, centralBody=earth, context=context, **kwargs)

# Main function
def main():
    """
    Main function
    """
    (args, config) = parseArgs()
    initOrekit(config['orekit'])
    
    context = DataContext.getDefault()
    
    countries = AoiCollection(bbox=(-85, -60, -33, 13))
    countries.load()
    
    (start, stop) = timespan(config, DataContext.getDefault())
    
    map = folium.Map()
    folium.GeoJson(data=countries.geoJson).add_to(map)
    
    # load the reference ellipsoid
    if 'earth' in config:
        earth = referenceEllipsoid(context=context, **(config['earth']))
    else:
        earth = referenceEllipsoid(model="wgs-84", context=context)
    
    sats = loadSatellites(config)
    workers = []
    for s in sats:
        work = WorkItem(start=start, stop=stop, sat=s, map=map, aoi=countries)
        thread = Thread(target=doWork, kwargs={'workItem':work, 'context':context, 'earth':earth, **(config['control'])})
        thread.start()
        workers.append(thread)
    
    for t in workers:
        t.join()
        
    saveMap(map, filename=args.output)

if __name__ in "__main__":
    main()
