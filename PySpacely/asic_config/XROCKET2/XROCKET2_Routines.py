# XROCKET2-Specific Routines

import sys
import platform
import os
import numpy as np
import serial.tools.list_ports
import atexit
import argparse
from datetime import datetime
from prettytable.colortable import PrettyTable
from si_prefix import si_format
from statistics import mean, NormalDist
import csv


#Import utilities from py-libs-common
from hal_serial import * #todo: this shouldn't import all symbols but just the ArudinoHAL class
from pattern_runner import *
from fnal_libawg import AgilentAWG
from fnal_ni_toolbox import * #todo: this should import specific class(es)
import fnal_log_wizard as liblog

from Master_Config import *
#from .XROCKET2_Config import *
import Spacely_Globals as sg

def XROCKET2_Config_Chain():

    tp1_in_file = "C:\\Users\\aquinn\\Downloads\\Glue code from Chengjing\\Tests\\Tests\\configchain\\configchain_testoutput_se_io.glue"
    tp1_out_file = "C:\\Users\\aquinn\Desktop\\SPROCKET Test\\spacely\\PySpacely\\xrocket2_config_output_PXI1Slot5_NI6583_se_io.glue"
    tp1_golden = "C:\\Users\\aquinn\\Downloads\\Glue code from Chengjing\\Tests\\Tests\\configchain\\configchain_golden_se_io.glue"
    
    tp = PatternRunner(sg.log, DEFAULT_IOSPEC)
    
    time.sleep(3)

    print("Checking XROCKET2 Config Chain!")
    
    tp.run_pattern(tp1_in_file, outfile_tag="xrocket2_config_output")
    gc = GlueConverter(DEFAULT_IOSPEC)
    gc.compare(gc.read_glue(tp1_golden), gc.read_glue(tp1_out_file))



ROUTINES = [XROCKET2_Config_Chain]
