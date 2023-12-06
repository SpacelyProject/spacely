# SPACELY MASTER CONFIGURATION #

#Global software settings
VERBOSE = True
PROGRESS = True
LITE = True

#The following variables may be redefined by target config files:
USE_ARDUINO = False
USE_NI = False
USE_AWG = False
USE_SCOPE = False

#ROUTINES = []
#INSTR = {}
#INSTR_INIT_SEQUENCE = []

TARGET = "ExampleASIC"

print(" * * * TARGETING \""+TARGET+"\" ASIC * * *")



if TARGET == "SPROCKET1":
    from SPROCKET1_Config import *
elif TARGET == "XROCKET1":
    from asic_config.XROCKET1.XROCKET1_Config import *
    from asic_config.XROCKET1.XROCKET1_Routines import *
elif TARGET == "XROCKET2":
    from asic_config.XROCKET2.XROCKET2_Config import *
    from asic_config.XROCKET2.XROCKET2_Routines import *
elif TARGET == "SPROCKET2":
    from asic_config.SPROCKET2.SPROCKET2_Config import *
    from asic_config.SPROCKET2.SPROCKET2_Routines import *
elif TARGET == "SQUIDDAC":
    from asic_config.SQUIDDAC.SQUIDDAC_Config import *
    from asic_config.SQUIDDAC.SQUIDDAC_Routines import *
elif TARGET == "ExampleASIC":
    from asic_config.ExampleASIC.ExampleASIC_Config import *
    from asic_config.ExampleASIC.ExampleASIC_Routines import *
        


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
