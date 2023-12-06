#ExampleASIC Routines File
#
# This file contains any custom code that you want to write for your ASIC,
# for example routines to read or write to registers, or to run tests.

import time

#Import Spacely functions
from Master_Config import *
import Spacely_Globals as sg
from Spacely_Utils import *
from pattern_runner import *

def ROUTINE_FPGATest():
    """Basic Test of our ability to write bits using the FPGA"""

    #Define the routine's purpose in a docstring like above, this will appear
    #when you call the routine in Spacely.
    
    #Create a basic pattern
    test_pattern = sg.pr.genpattern_from_waves_dict({"mclk":[0,1]*20, "data_in":[0,0,0,0,0,0,1,1,1,1,1,1,1]}, time_scale_factor=3)
    
    #Run that pattern
    sg.pr.run_pattern( test_pattern,time_scale_factor = 1, outfile_tag ="testpattern")

    




# IMPORTANT! If you want to be able to run a routine easily from
# spacely, put its name in the "ROUTINES" list:
ROUTINES = [ROUTINE_FPGATest]
