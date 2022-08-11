"""
Download (if necessary) the data file and provide a handle to it.
"""
dataDir = ".data"
worldBorders = "https://thematicmapping.org/downloads/TM_WORLD_BORDERS-0.3.zip"

import sys

from os import makedirs
from os.path import basename, exists, join
from requests import get
from shutil import rmtree


def download(url: str, chunk_size=128) -> str:
    """
    Download a file to the temporary data data directory

    Args:
        url (str): url to download
        chunk_size (int, optional): Block size to process at a time. Defaults to 128.

    Returns:
        str: The path to the downloaded file on the file system.
    """
    name = basename(url)
    dest = join(sys.path[0], "../", dataDir, name)

    if exists(dest):
        return dest

    if not exists(dataDir):
        makedirs(dataDir)

    r = get(
        url,
        stream=True,
        headers={
            "accept": "*/*",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_3) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/99.0.4844.84 Safari/537.36",
        },
    )
    print(url + " ... " + str(r.status_code))

    sz = 0
    with open(dest, "wb") as fd:
        for chunk in r.iter_content(chunk_size=chunk_size):
            fd.write(chunk)
            sz += chunk_size

    print(sz)
    return dest


def clearCache():
    """
    Clear any and all cached data.
    """
    rmtree(path=dataDir)
