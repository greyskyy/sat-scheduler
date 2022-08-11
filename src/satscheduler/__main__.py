"""Initialize and run the satellite scheduler application"""

import orekit
from application import runApp

vm = orekit.initVM()

runApp(vm)