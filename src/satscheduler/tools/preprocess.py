import satscheduler.aoi as aoi
from satscheduler.preprocessor import Preprocessor
from satscheduler.satellite import Satellites


def preprocess(args=None, config=None, vm=None):
    """Load the AOIs, generating a summary + map plot.

    Args:
        args (argparse.Namespace, optional): The command line arguments. Defaults to None.
        config (dict, optional): A dictionary loaded with the application configuration file's contents. Defaults to None.
        vm (_type_, optional): A reference to the orekit virtual machine. Defaults to None.
    """
    # load the aois
    aois = aoi.loadAois(sourceUrl=config["aois"]["url"])

    # load the satellites
    sats = Satellites.load_from_config(config)

    for s in sats:
        print(s)
