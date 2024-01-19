# SPACELY MASTER CONFIGURATION #
import importlib

#Global software settings
VERBOSE = True
PROGRESS = True

#The following variables may be redefined by target config files:
USE_ARDUINO = False
USE_NI = False

TARGET = "SPROCKET2"

TARGET_ROUTINES_MOD = f"asic_config.{TARGET}.{TARGET}_Routines"
TARGET_ROUTINES_PY = f"asic_config\\{TARGET}\\{TARGET}_Routines.py"
TARGET_CONFIG_MOD = f"asic_config.{TARGET}.{TARGET}_Config"
TARGET_CONFIG_PY = f"asic_config\\{TARGET}\\{TARGET}_Config.py"

print(" * * * TARGETING \""+TARGET+"\" ASIC * * *")


# Deep Python Magic which is basically equivalent to doing "from {module_name} import *"
# where {module_name} is dynamically determined at runtime. We do this twice, once for 
# ASIC_Config.py and once for ASIC_Routines.py.
for module_name in [TARGET_CONFIG_MOD, TARGET_ROUTINES_MOD]:

    module = __import__(module_name, fromlist=['*'])

    if hasattr(module, '__all__'):
        all_names = module.__all__
    else:
        all_names = [name for name in dir(module) if not name.startswith('_')]
        
    #print("(DBG) Importing the following functions/variables to global scope:"+str(all_names))

    globals().update({name: getattr(module, name) for name in all_names})



try:
    ROUTINES
except NameError:
    ROUTINES = []

try:
    INSTR
except NameError:
    INSTR = {}
    
try:
    INSTR_HANDLE
except NameError:
    INSTR_HANDLE = {}

try:
    INSTR_INIT_SEQUENCE
except NameError:
    INSTR_INIT_SEQUENCE = []