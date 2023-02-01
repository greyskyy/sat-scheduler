"""Test appliction.
Running this script simulates a build + install + run of the module.
"""
import os.path
import pyrebar
import sys

from satscheduler.runner import run

if __name__ == "__main__":
    path = os.path.dirname(__file__)
    pyrebar.bootstrap_from_pyproject(os.path.join(path, "..", "pyproject.toml"))
    rc = run()
    sys.exit(rc)