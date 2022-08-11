import logging
import logging.config


def configure_logging(level: str = "INFO"):
    config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "standard": {
                "format": "%(asctime)s %(name)s %(levelname)s %(message)s",
                "datefmt": "%Y-%m-%dT%H:%M:%S%z",
            }
        },
        "handlers": {
            "standard": {"class": "logging.StreamHandler", "formatter": "standard"}
        },
        "loggers": {
            "": {"propagate": False},
            "satscheduler": {"handlers": ["standard"], "level": level.upper()},
        },
    }
    logging.config.dictConfig(config)
