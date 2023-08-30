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
    """Verify the XROCKET2 Config Chain by passing data in via configIn and reading it from configOut"""

    tp1_in_file = "C:\\Users\\aquinn\\Downloads\\Glue code from Chengjing\\Tests\\Tests\\configchain\\configchain_testoutput_se_io.glue"
    tp1_out_file = "C:\\Users\\aquinn\Desktop\\SPROCKET Test\\spacely\\PySpacely\\xrocket2_config_output_PXI1Slot5_NI6583_se_io.glue"
    tp1_golden = "C:\\Users\\aquinn\\Downloads\\Glue code from Chengjing\\Tests\\Tests\\configchain\\configchain_golden_se_io.glue"
    
    tp = PatternRunner(sg.log, DEFAULT_IOSPEC)
    
    time.sleep(3)

    print("Checking XROCKET2 Config Chain!")
    
    tp.run_pattern(tp1_in_file, outfile_tag="xrocket2_config_output")
    gc = GlueConverter(DEFAULT_IOSPEC)
    gc.compare(gc.read_glue(tp1_golden), gc.read_glue(tp1_out_file))



def XROCKET2_Scan_Chain():
    """Verify the XROCKET2 Scan Chain by passing data in via scanIn and reading it from scanOut"""
    
    tp1_in_file = "C:\\Users\\aquinn\\Downloads\\scanchain4\\scanchain4\\scanchain_with_reset.glue"
    tp1_out_file = "C:\\Users\\aquinn\Desktop\\SPROCKET Test\\spacely\\PySpacely\\xrocket2_config_output_PXI1Slot5_NI6583_se_io.glue"
    tp1_golden = "C:\\Users\\aquinn\\Downloads\\scanchain4\\scanchain4\\scanchain_golden_se_io.glue"
    
    tp = PatternRunner(sg.log, DEFAULT_IOSPEC)
    
    time.sleep(3)

    print("Checking XROCKET2 Scan Chain!")
    
    tp.run_pattern(tp1_in_file, outfile_tag="xrocket2_scan_output")
    gc = GlueConverter(DEFAULT_IOSPEC)
    gc.compare(gc.read_glue(tp1_golden), gc.read_glue(tp1_out_file))


def XROCKET2_Serial_Readout():
    """Verify the XROCKET2 Serial Readout by passing in data via the scan chain and reading it through serialOut"""

    pass


def XROCKET2_Vtest_Readout():
    """Test the complete operation of the array by supplying a Vtest voltage and reading the data out through serialOut"""

    for Vtest_mV in range(0,1000,100):
        #1) set Vtest to the correct voltage using Spacely.

        #2) Run the appropriate Glue waveform to take an ADC acquisition and read out the data.

        #3) Parse the data you read back. 

        pass


def XROCKET2_DNL_Trim():
    """Trim the Captrim values of each pixel to optimize DNL."""
    pass



def XROCKET2_ascii_scan_chain_demo():
    """Test scan chain loopback using an ASCII wave instead of a VCD."""

    a = AsciiWave()

    a.init_signals([("scanClk",0),("scanEn",0),("scanLoad",0),("scanIn",0)])

    a.set_signal("scanEn",1)
    a.set_signal("scanIn",1)

    for i in range(4096):
        for j in range(10):
            a.pulse_signal("scanClk")
        a.pulse_signal("scanLoad")

    a.write("ascii_scan_chain_demo.txt")


    tp = PatternRunner(sg.log, DEFAULT_IOSPEC)
    gc = GlueConverter(DEFAULT_IOSPEC)

    gc.ascii2Glue("ascii_scan_chain_demo.txt",5,"ascii_scan_chain_demo")
    
    time.sleep(3)

    print("Checking XROCKET2 Scan Chain (ASCII)!")
    
    tp.run_pattern("ascii_scan_chain_demo_se_io.glue", outfile_tag="xrocket2_scan_output_ascii_demo")

    gc.plot_glue("xrocket2_scan_output_ascii_demo_PXI1Slot5_NI6583_se_io.glue")
    

    
    


ROUTINES = [XROCKET2_Config_Chain, XROCKET2_Scan_Chain, XROCKET2_ascii_scan_chain_demo]
