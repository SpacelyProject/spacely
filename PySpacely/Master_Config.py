# SPACELY MASTER CONFIGURATION #
import importlib
import os
import glob

import Spacely_Globals as sg

MASTER_CONFIG_TXT_DEFAULT_TEXT = """
//This file was created automatically by Spacely!
//Change the values below to the desired values for your application.
VERBOSE = True
PROGRESS = True
USE_ARDUINO = False
USE_NI = False
USE_COCOTB = False
SIMULATOR = None
HDL_TOP_MODULE = None
FW_TOP_MODULE = None
TWIN_MODE=None
COCOTB_BUILD_ARGS = None
TARGET = "???"
"""

# Ensure that Spacely always starts executing from the spacely/PySpacely directory.
os.chdir(os.path.dirname(os.path.abspath(__file__)))

MASTER_CONFIG_PATH = "Master_Config.txt"

## 1) Check if Master_Config.txt exists. If not, create it.
if not os.path.exists(MASTER_CONFIG_PATH):
    print("No Master_Config.txt found. Creating it with default settings!")
    with open(MASTER_CONFIG_PATH,'w') as write_file:
        write_file.write(MASTER_CONFIG_TXT_DEFAULT_TEXT)

## 2) Read lines from Master_Config.txt and parse to a dictionary.
with open(MASTER_CONFIG_PATH) as read_file:
    config_lines = read_file.readlines()

config_dict = {}
for line in config_lines:
    if not line.startswith("//") and "=" in line:
        line_toks = [x.strip() for x in line.split("=")]
        config_dict[line_toks[0]] = eval(line_toks[1])

## 3) Define global variables from this dictionary.
sg.VERBOSE = config_dict["VERBOSE"]
sg.PROGRESS = config_dict["PROGRESS"]
sg.USE_ARDUINO = config_dict["USE_ARDUINO"]
sg.USE_NI = config_dict["USE_NI"]
sg.USE_COCOTB = config_dict["USE_COCOTB"]
sg.SIMULATOR = config_dict["SIMULATOR"]
sg.HDL_TOP_MODULE = config_dict["HDL_TOP_MODULE"]
sg.FW_TOP_MODULE = config_dict["FW_TOP_MODULE"]
sg.TWIN_MODE = config_dict["TWIN_MODE"]
sg.COCOTB_BUILD_ARGS = config_dict["COCOTB_BUILD_ARGS"]
sg.TARGET = config_dict["TARGET"]

if sg.TARGET == "???":
    print("ERROR: You need to specify the name of the ASIC you wish to target in Master_Config.txt")
    quit()

sg.TARGET_ROUTINES_MOD = f"spacely-asic-config.{sg.TARGET}.{sg.TARGET}_Routines"
sg.TARGET_ROUTINES_PY = os.path.join("spacely-asic-config",sg.TARGET,f"{sg.TARGET}_Routines.py")  

sg.TARGET_CONFIG_MOD = f"spacely-asic-config.{sg.TARGET}.{sg.TARGET}_Config"
sg.TARGET_CONFIG_PY = os.path.join("spacely-asic-config",sg.TARGET,f"{sg.TARGET}_Routines.py")  


print(" * * * TARGETING \""+sg.TARGET+"\" ASIC * * *")

try:
    # Deep Python Magic which is basically equivalent to doing "from {module_name} import *"
    # where {module_name} is dynamically determined at runtime. We do this twice, once for 
    # ASIC_Config.py and once for ASIC_Routines.py.

    # Use glob to find all submodules that have a particular name format.
    subroutines = os.path.join("spacely-asic-config",sg.TARGET,f"{sg.TARGET}_Subroutines*.py")
    sg.TARGET_SUBROUTINES_PY = list(sorted(glob.glob(subroutines))) 
    sg.TARGET_SUBROUTINES_MOD = [i.replace("/",".")[:-3] for i in sg.TARGET_SUBROUTINES_PY]
    modules_to_try = [sg.TARGET_CONFIG_MOD] + sg.TARGET_SUBROUTINES_MOD + [sg.TARGET_ROUTINES_MOD]
    print(f"{sg.TARGET} has the following modules: ")
    for module in modules_to_try:
        print(f"  - {module}")

    for module_name in modules_to_try:

        module = __import__(module_name, fromlist=['*'])

        if hasattr(module, '__all__'):
            all_names = module.__all__
        else:
            all_names = [name for name in dir(module) if not name.startswith('_')]
        
        #print("(DBG) Importing the following functions/variables to global scope:"+str(all_names))

        #This line allows any file that imports Master_Config to access functions and variables
        #from the MyASIC_Routines and MyASIC_Config files. 
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
