# Spacely Globals #
#
# Dynamic global variables and data structures that can be accessed from
# any part of Spacely. 
import pickle
import os

#Arduino port. Making this a global variable allows for
#commands that would affect the NI System or analog to send
#emulation commands to the Arduino instead.
port = None
INSTR = {}
ROUTINES = []

#Global pattern runner and glue converter instances.
pr = None
gc = None


ARDUINO_CONNECTED = False
NI_CONNECTED = False
AWG_CONNECTED = False
log = None


#Config-defined variables:
VERBOSE = None
PROGRESS = None
USE_ARDUINO = None
USE_NI = None
USE_COCOTB = None
SIMULATOR = None
HDL_TOP_MODULE = None
FW_TOP_MODULE = None
TWIN_MODE = None
COCOTB_BUILD_ARGS = None
TARGET = None

#Files to import
TARGET_CONFIG_PY = None
TARGET_ROUTINES_PY = None
TARGET_SUBROUTINES_PY = []
TARGET_CONFIG_MOD = None
TARGET_ROUTINES_MOD = None
TARGET_SUBROUTINES_MOD = []


## sg Pickle Logic ##
#
# The sg Pickle Logic allows you to save and load the global (sg) state in a pickle file.
# If state is saved in a file, it will automatically be reloaded the next time Spacely_Globals.py is
# imported. The idea of including this code in Spacely_Globals.py itself instead of Spacely_Utils.py is
# that any module which imports sg should have the same consistent global state.

#In general, we pickle only simple text variables. Pickling generic classes is unlikely to work because
#of the various references and file handles they hold.
GLOBALS_TO_PICKLE = [ "ARDUINO_CONNECTED", "NI_CONNECTED", "AWG_CONNECTED", "VERBOSE", "PROGRESS", "USE_ARDUINO", "USE_NI", "USE_COCOTB", "SIMULATOR", "HDL_TOP_MODULE", "FW_TOP_MODULE", "TWIN_MODE", "COCOTB_BUILD_ARGS", "TARGET", "TARGET_CONFIG_PY", "TARGET_ROUTINES_PY", "TARGET_SUBROUTINES_PY", "TARGET_CONFIG_MOD", "TARGET_ROUTINES_MOD", "TARGET_SUBROUTINES_MOD"]

PICKLE_FILE = "Spacely_Globals.pkl"

def save_pickle():
    sg_dict = {key: globals()[key] for key in GLOBALS_TO_PICKLE}
    print(sg_dict)
    with open(PICKLE_FILE,"wb") as write_file:
        pickle.dump(sg_dict, write_file)

def load_pickle():
    with open(PICKLE_FILE,"rb") as read_file:
        globals().update(pickle.load(read_file))

def clear_pickle():
    os.remove(PICKLE_FILE)
