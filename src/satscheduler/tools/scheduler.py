import folium
import satscheduler.aoi as aoi

from astropy import units
from satscheduler.satellite import Satellite
from satscheduler.utils import OrekitUtils
from org.orekit.data import DataContext
from org.orekit.models.earth import ReferenceEllipsoid
from org.orekit.time import AbsoluteDate, DateTimeComponents
from threading import Thread
from satscheduler.preprocessor import WorkItem, Preprocessor


def saveMap(map: folium.Map, filename="index.html"):
    """
    Save the map to the file

    Args:
        map (folium.Map): The map object to save
        filename (str, optional): Filename where the map will be saved. Defaults to 'index.html'.
    """
    map.save(filename)


def loadSatellites(config: dict) -> list[Satellite]:
    """
    Load the satellites from the provided configuration

    Args:
        config (dict): The configuration dictionary loaded from the yaml file.

    Returns:
        list[Satellite]: List of satellite configuration objects
    """
    sats = []

    if "satellites" in config and not config["satellites"] == None:
        for key, value in config["satellites"].items():
            if "filter" in value and value["filter"]:
                print(f"filtering satellite {key}")
            else:
                sats.append(Satellite(key, value))

    return sats


def timespan(
    config: dict, context: DataContext = None
) -> tuple[AbsoluteDate, AbsoluteDate]:
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

    t0 = config["run"]["start"]
    t1 = config["run"]["stop"]

    return (
        AbsoluteDate(
            DateTimeComponents.parseDateTime(t0), context.getTimeScales().getUTC()
        ),
        AbsoluteDate(
            DateTimeComponents.parseDateTime(t1), context.getTimeScales().getUTC()
        ),
    )


def doWork(
    vm,
    workItem: WorkItem,
    earth: ReferenceEllipsoid = None,
    context: DataContext = None,
    **kwargs,
):
    """
    Thread target. Attaches the thread to the orekit VM before executing the actual propagation work

    Args:
        workItem (WorkItem): The item of work
    """
    vm.attachCurrentThread()  # do this before any orekit in a background thread
    schedule(item=workItem, centralBody=earth, context=context, **kwargs)


def scheduler(args=None, config=None, vm=None):
    """Schedule payload operations over a set of AOIs.

    Args:
        args (argparse.Namespace, optional): The command line arguments. Defaults to None.
        config (dict, optional): A dictionary loaded with the application configuration file's contents. Defaults to None.
        vm (_type_, optional): A reference to the orekit virtual machine. Defaults to None.
    """
    context = DataContext.getDefault()

    aois = aoi.loadAois(
        sourceUrl=config["aois"]["url"]
        if config is not None and "aois" in config
        else None,
        bbox=config["aois"]["bbox"]
        if config is not None and "aois" in config
        else None,
    )

    (start, stop) = timespan(config, DataContext.getDefault())

    map = folium.Map()

    # add the aois to the map
    for a in aois:
        folium.GeoJson(a.to_gdf().to_json()).add_to(map)

    # load the reference ellipsoid
    if "earth" in config:
        earth = OrekitUtils.referenceEllipsoid(context=context, **(config["earth"]))
    else:
        earth = OrekitUtils.referenceEllipsoid(model="wgs-84", context=context)

    sats = loadSatellites(config)
    workers = []
    for s in sats:
        work = WorkItem(start=start, stop=stop, sat=s, map=map, aoi=aois)
        thread = Thread(
            target=doWork,
            kwargs={
                "vm": vm,
                "workItem": work,
                "context": context,
                "earth": earth,
                **(config["control"]),
            },
        )
        thread.start()
        workers.append(thread)

    for t in workers:
        t.join()

    saveMap(map, filename=args.output)
