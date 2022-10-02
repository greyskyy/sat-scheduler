"""Test appliction.
Running this script simulates a build + install + run of the module.
"""
import pyrebar
import pyrebar.application
import sys


if sys.version_info < (3, 10):
    from importlib_metadata import EntryPoint
else:
    from importlib.metadata import EntryPoint


if __name__ == "__main__":
    pyrebar.Plugins.add_entrypoint(
        EntryPoint(
            name="satsched-init",
            value="satscheduler.initialize:pre_init",
            group=pyrebar.Plugins.PREINIT_GROUP,
        )
    )
    pyrebar.Plugins.add_entrypoint(
        EntryPoint(
            name="satsched-addargs",
            value="satscheduler.configuration:add_args",
            group=pyrebar.Plugins.PREINIT_GROUP,
        )
    )
    pyrebar.Plugins.add_entrypoint(
        EntryPoint(
            name="satsched-loadconfig",
            value="satscheduler.configuration:load_config",
            group=pyrebar.Plugins.POSTINIT_GROUP,
        )
    )
    pyrebar.Plugins.add_entrypoint(
        EntryPoint(
            name="aoi-tool",
            value="satscheduler.tools.aoitool",
            group=pyrebar.Plugins.APP_GROUP,
        )
    )

    pyrebar.Plugins.add_entrypoint(
        EntryPoint(
            name="preprocessor",
            value="satscheduler.tools.preprocess",
            group=pyrebar.Plugins.APP_GROUP,
        )
    )

    rc = pyrebar.application.main()
    sys.exit(rc)
