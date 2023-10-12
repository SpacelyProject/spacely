# SQUIDDAC Routines


import numpy as np
import time

#Import utilities from py-libs-common
from hal_serial import * #todo: this shouldn't import all symbols but just the ArudinoHAL class
from pattern_runner import *
from fnal_libawg import AgilentAWG
from fnal_ni_toolbox import * #todo: this should import specific class(es)
import fnal_log_wizard as liblog

#Import Spacely functions
from Master_Config import *
import Spacely_Globals as sg
from Spacely_Utils import *


def SC_CFG(override,TestEn,Range2):
    return [0]*17 + [override] + [TestEn] + [Range2]


def ROUTINE0_Scan_Chain_Loopback():
    """Scan Chain Loopback"""

    pr = PatternRunner(sg.log, DEFAULT_IOSPEC, DEFAULT_FPGA_BITFILE_MAP)
    time.sleep(3)

    # 1) Generate some random data
    sc_data = list(np.random.binomial(1,0.5,size=19))
    print("Random Scan Chain Data: ",str(sc_data))

    # 2) Create a Glue waveform that writes the data to the scan chain.
    glue_wave = genpattern_SC_write(sc_data,1000)

    # 3) Run the Glue waveform
    pr.run_pattern(glue_wave,outfile_tag="sc_1")
    pr.run_pattern(glue_wave,outfile_tag="sc_2")

    # 4) Check that the data we read back is correct.
    out_1 = "sc_1_PXI1Slot16_NI6583_se_io.glue"
    out_2 = "sc_2_PXI1Slot16_NI6583_se_io.glue"
    gc = GlueConverter(DEFAULT_IOSPEC)

    scanout_bits = gc.get_clocked_bitstream(gc.read_glue(out_2), "S_CLK", "S_DOUT")
    print("Received:",str(scanout_bits))
    #gc.compare(gc.read_glue(out_1), gc.read_glue(out_2))


def ROUTINE1_Comparator_Smoke_Test():
    """Comparator Smoke Test uwu"""

    pr = PatternRunner(sg.log, DEFAULT_IOSPEC, DEFAULT_FPGA_BITFILE_MAP)
    gc = GlueConverter(DEFAULT_IOSPEC)
    config_AWG_as_DC(0)
    time.sleep(3)

    smoke_test_ascii = ".\\asic_config\\SPROCKET2\\comparator_smoke_test_pattern.txt"
    if gc.ascii2Glue(smoke_test_ascii, 1, "smoke_test_pattern") == -1:
        return
    smoke_test_pattern = "smoke_test_pattern_se_io.glue"

    #Config: TestEn = 1  
    SC_PATTERN = SC_CFG(override=0,TestEn=1,Range2=0)
    print(SC_PATTERN)
    pr.run_pattern( genpattern_SC_write(SC_PATTERN),outfile_tag="sc_cfg")

    #Smoke 1: Expected output -- CompOut = 0
    pr.run_pattern(smoke_test_pattern,outfile_tag="smoke_1")

    #Smoke 2: Expected output -- CompOut = 1
    set_Vin_mV(1000)
    pr.run_pattern(smoke_test_pattern,outfile_tag="smoke_2")
    
    smoke_1 = "smoke_1_PXI1Slot16_NI6583_se_io.glue"
    smoke_2 = "smoke_2_PXI1Slot16_NI6583_se_io.glue"

    print("Smoke Test 1/2 (expected result: all 0's)")
    print(gc.get_bitstream(gc.read_glue(smoke_1),"CompOut"))
    print("Smoke Test 2/2 (expected result: all 1's)")
    print(gc.get_bitstream(gc.read_glue(smoke_2),"CompOut"))


def ROUTINE2_ADC_Capture():
    """Operate the ADC to digitize a range of values from TestEn"""
    
    pr = PatternRunner(sg.log, DEFAULT_IOSPEC, DEFAULT_FPGA_BITFILE_MAP)
    gc = GlueConverter(DEFAULT_IOSPEC)
    config_AWG_as_DC(0)
    time.sleep(3)
    
    adc_op_glue = genpattern_ADC_Capture(1)
    sc_read_glue = genpattern_SC_write([0]*19,1000)
    
    
    #Config: TestEn = 1  
    SC_PATTERN = SC_CFG(override=0,TestEn=1,Range2=0)
    pr.run_pattern( genpattern_SC_write(SC_PATTERN),outfile_tag="sc_cfg")
    
    #(2) Sweep ADC from 0mV to 1000mV and record the  results.
    with open("ADC_Sweep_Results.csv","w") as write_file:
        write_file.write("Vin(mV),Output Code\n")
    
        for vin in range(0,1000,100):
            #Set Vin_mV and run the ADC
            set_Vin_mV(vin)
            pr.run_pattern(adc_op_glue,outfile_tag="adc_op")
            
            #Scan out the result
            pr.run_pattern(sc_read_glue,outfile_tag="sc_result")
            sc_result = "sc_result_PXI1Slot16_NI6583_se_io.glue"
            scanout_bits = gc.get_clocked_bitstream(gc.read_glue(sc_result), "S_CLK", "S_DOUT")
            print(scanout_bits)
            #These bits represent the ADC result.
            x = vec_to_int(scanout_bits[0:10])
            print(x)
            write_file.write(str(vin)+","+str(x)+"\n")
            
    
    
# Generates the pattern necessary to run the ADC.
def genpattern_ADC_Capture(time_scale_factor):
    
    waves = {}
    
    #Start off w/ some zeros to avoid extra pulse bug.
    waves["DACclr"] = [0]*10
    waves["Qequal"] = [0]*10
    waves["capClk"] = [0]*10
    waves["calc"]   = [0]*10
    waves["read_ext"]   = [0]*10
    
    
    for adc_bit in range(10):
        
        #Each bit starts off w/ a DACclr pulse.
        waves["DACclr"] = waves["DACclr"] + [1,1,1]*time_scale_factor
        waves["capClk"] = waves["capClk"] + [1,1,1]*time_scale_factor
        waves["Qequal"] = waves["Qequal"] + [0,0,0]*time_scale_factor
        
        for clk_cycle in range(adc_bit):
            #Add a 0 for non-overlapping.    
            waves["DACclr"] = waves["DACclr"] + [0]
            waves["capClk"] = waves["capClk"] + [0]
            waves["Qequal"] = waves["Qequal"] + [0]
            
            #Qequal pulse
            waves["DACclr"] = waves["DACclr"] + [0,0,0]*time_scale_factor
            waves["capClk"] = waves["capClk"] + [0,0,0]*time_scale_factor
            waves["Qequal"] = waves["Qequal"] + [1,1,1]*time_scale_factor
            
            
            #Add a 0 for non-overlapping.    
            waves["DACclr"] = waves["DACclr"] + [0]
            waves["capClk"] = waves["capClk"] + [0]
            waves["Qequal"] = waves["Qequal"] + [0]
            
            if clk_cycle < adc_bit - 1:
                #capClk pulse
                waves["DACclr"] = waves["DACclr"] + [0,0,0]*time_scale_factor
                waves["capClk"] = waves["capClk"] + [1,1,1]*time_scale_factor
                waves["Qequal"] = waves["Qequal"] + [0,0,0]*time_scale_factor
        
            
            
        #Add a 0 for non-overlapping.    
        waves["DACclr"] = waves["DACclr"] + [0]
        waves["capClk"] = waves["capClk"] + [0]
        waves["Qequal"] = waves["Qequal"] + [0]
        
        
    #Final DACclr pulse.
    waves["DACclr"] = waves["DACclr"] + [1,1,1]*time_scale_factor
    waves["capClk"] = waves["capClk"] + [1,1,1]*time_scale_factor
    waves["Qequal"] = waves["Qequal"] + [0,0,0]*time_scale_factor
        
    waves["calc"] = waves["calc"] + [1]*(len(waves["DACclr"])-len(waves["calc"]))
    waves["read_ext"] = waves["calc"]
    
    #2) Writing to an ASCII file.
    with open("genpattern_adc_op.txt",'w') as write_file:
        for w in waves.keys():
            write_file.write(w+":"+"".join([str(x) for x in waves[w]])+"\n")
            
    #3) Convert ASCII file to Glue.
    gc = GlueConverter(DEFAULT_IOSPEC)

    gc.ascii2Glue("genpattern_adc_op.txt", 1, "genpattern_adc_op")


    return "genpattern_adc_op_se_io.glue"

### HELPER FUNCTIONS ###

# Given a string of bits to write to the scan chain, generates a glue waveform that will write those bits.
def genpattern_SC_write(sc_bits, time_scale_factor=1):

    #1) Generating the waves based on sc_bits
    waves = {}

    waves["S_CLK"] = []
    waves["S_DIN"] = []
    waves["S_PASS"] = []

    for bit in sc_bits:
        waves["S_CLK"] = waves["S_CLK"] + [0]*time_scale_factor+[1]*time_scale_factor
        waves["S_PASS"] = waves["S_PASS"] + [0]*2*time_scale_factor
        if bit == 1:
            waves["S_DIN"] = waves["S_DIN"] + [1]*2*time_scale_factor
        else:
            waves["S_DIN"] = waves["S_DIN"] + [0]*2*time_scale_factor



    #Finally assert S_PASS and clock in the data.
    waves["S_CLK"] = waves["S_CLK"] + [0]*time_scale_factor+[1]*time_scale_factor
    waves["S_PASS"] = waves["S_PASS"] + [1]*2*time_scale_factor
    waves["S_DIN"] = waves["S_DIN"] + [0]*2*time_scale_factor

    #2) Writing to an ASCII file.
    with open("genpattern_SC_write.txt",'w') as write_file:
        for w in waves.keys():
            write_file.write(w+":"+"".join([str(x) for x in waves[w]])+"\n")
            
    #3) Convert ASCII file to Glue.
    gc = GlueConverter(DEFAULT_IOSPEC)

    gc.ascii2Glue("genpattern_SC_write.txt", 1, "genpattern_SC_write")


    return "genpattern_SC_write_se_io.glue"


####################################################

    
ROUTINES = [ROUTINE0_Scan_Chain_Loopback,ROUTINE1_Comparator_Smoke_Test,ROUTINE2_ADC_Capture]
