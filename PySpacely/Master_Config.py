# SPACELY MASTER CONFIGURATION #
import importlib
import os

#Global software settings
VERBOSE = True
PROGRESS = True

#The following variables may be redefined by target config files:
USE_ARDUINO = False
USE_NI = False
USE_COCOTB = False
SIMULATOR = None
HDL_TOP_LEVEL = None
HDL_SOURCES = None

TARGET = "ExampleASIC"

TARGET_ROUTINES_MOD = f"spacely-asic-config.{TARGET}.{TARGET}_Routines"
TARGET_ROUTINES_PY = os.path.join("spacely-asic-config",TARGET,f"{TARGET}_Routines.py")  

TARGET_SUBROUTINES_MOD = f"spacely-asic-config.{TARGET}.{TARGET}_Subroutines"
TARGET_SUBROUTINES_PY = os.path.join("spacely-asic-config",TARGET,f"{TARGET}_Subroutines.py")

TARGET_CONFIG_MOD = f"spacely-asic-config.{TARGET}.{TARGET}_Config"
TARGET_CONFIG_PY = os.path.join("spacely-asic-config",TARGET,f"{TARGET}_Routines.py")  


print(" * * * TARGETING \""+TARGET+"\" ASIC * * *")

try:
    # Deep Python Magic which is basically equivalent to doing "from {module_name} import *"
    # where {module_name} is dynamically determined at runtime. We do this twice, once for 
    # ASIC_Config.py and once for ASIC_Routines.py.
    modules_to_try = [TARGET_CONFIG_MOD, TARGET_ROUTINES_MOD]

    #If we are running with the Cocotb flow, we may start out in /sim_build/, necessitating the ".."
    if os.path.exists(TARGET_SUBROUTINES_PY) or os.path.exists(os.path.join("..",TARGET_SUBROUTINES_PY)):
        print(f"{TARGET} has a subroutines file, loading...")
        #Be sure load subroutines before routines.
        modules_to_try = [TARGET_CONFIG_MOD, TARGET_SUBROUTINES_MOD, TARGET_ROUTINES_MOD]
        

    for module_name in modules_to_try:

        module = __import__(module_name, fromlist=['*'])

        if hasattr(module, '__all__'):
            all_names = module.__all__
        else:
            all_names = [name for name in dir(module) if not name.startswith('_')]
        
        #print("(DBG) Importing the following functions/variables to global scope:"+str(all_names))

        globals().update({name: getattr(module, name) for name in all_names})


except ModuleNotFoundError as e:
    if module_name.endswith("Routines"):
        print(f"ERROR: {module_name} COULD NOT BE FOUND! NO ROUTINES LOADED.")
    else:
        print(f"ERROR: {module_name} COULD NOT BE FOUND! NO CONFIG OR ROUTINES LOADED.") 
    print(f"(Detail: {e})")



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
