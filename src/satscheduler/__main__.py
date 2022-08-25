"""Initialize and run the satellite scheduler application."""
from application import runApp
import sys

if __name__ == "__main__":
    rc = runApp()
    sys.exit(rc)
