"""Manage the location and loading of applications."""
import collections
import importlib
import inspect
import pkgutil

ToolInfo = collections.namedtuple("ToolInfo", ["func", "docstring"], defaults=[None])
"""Information class regarding the tools in this application.
    Attributes:
        func (Callable): The application function
        docstring (str, optional): The process description to display in help text. Defaults to None.
"""


def load_tools() -> list[ToolInfo]:
    module = importlib.import_module("satscheduler.tools")

    results = []
    for info in pkgutil.iter_modules(module.__path__, prefix="satscheduler.tools."):
        submod = importlib.import_module(info.name)

        func = None
        docstring = None
        for n, value in inspect.getmembers(submod):
            if n == "execute" and inspect.isfunction(value):
                func = value
            elif n == "__doc__":
                docstring = value

        if func:
            results.append(ToolInfo(func=func, docstring=docstring))

    return results
