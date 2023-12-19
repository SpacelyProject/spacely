# SPACELY MASTER CONFIGURATION #
import importlib

#Global software settings
VERBOSE = True
PROGRESS = True

#The following variables may be redefined by target config files:
USE_ARDUINO = False
USE_NI = False
USE_AWG = False
USE_SCOPE = False

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


# if TARGET == "SPROCKET1":
    # from SPROCKET1_Config import *
# elif TARGET == "XROCKET1":
    # from asic_config.XROCKET1.XROCKET1_Config import *
    # from asic_config.XROCKET1.XROCKET1_Routines import *
# elif TARGET == "XROCKET2":
    # from asic_config.XROCKET2.XROCKET2_Config import *
    # from asic_config.XROCKET2.XROCKET2_Routines import *
# elif TARGET == "SPROCKET2":
    # #import asic_config.SPROCKET2.SPROCKET2_Routines
    # importlib.import_module("asic_config.SPROCKET2.SPROCKET2_Config")
    # importlib.import_module("asic_config.SPROCKET2.SPROCKET2_Config")
    # #from asic_config.SPROCKET2.SPROCKET2_Config import *
    # from asic_config.SPROCKET2.SPROCKET2_Routines import *
    # #print(dir(asic_config.SPROCKET2.SPROCKET2_Routines))
# elif TARGET == "SQUIDDAC":
    # from asic_config.SQUIDDAC.SQUIDDAC_Config import *
    # from asic_config.SQUIDDAC.SQUIDDAC_Routines import *
# elif TARGET == "ExampleASIC":
    # from asic_config.ExampleASIC.ExampleASIC_Config import *
    # from asic_config.ExampleASIC.ExampleASIC_Routines import *
# elif TARGET == "CITC2":
    # from asic_config.CITC2.CITC2_Config import *
    # from asic_config.CITC2.CITC2_Routines import *
        


try:
    ROUTINES
except NameError:
    ROUTINES = []

try:
    INSTR
except NameError:
    INSTR = {}

try:
    INSTR_INIT_SEQUENCE
except NameError:
    INSTR_INIT_SEQUENCE = []