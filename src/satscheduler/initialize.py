"""Initialization functions."""
import os.path
from orekitfactory.utils import Dataloader


def pre_init(*args, **kwargs):
    """Set up the data directory."""
    Dataloader.data_dir = os.path.abspath(".data")
