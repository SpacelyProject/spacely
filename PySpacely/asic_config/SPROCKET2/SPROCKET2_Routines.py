# SQUIDDAC Routines


import numpy as np
import time

#Import utilities from py-libs-common
from hal_serial import * #todo: this shouldn't import all symbols but just the ArudinoHAL class
from pattern_runner import *
from fnal_libawg import AgilentAWG
from fnal_ni_toolbox import * #todo: this should import specific class(es)
import fnal_log_wizard as liblog
from fnal_libvisa import *

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


def ROUTINE2_ADC_Capture_ScanChain():
    """Operate the ADC to digitize a range of values from TestEn (DEPRECATED, DO NOT USE...)"""
    
    pr = PatternRunner(sg.log, DEFAULT_IOSPEC, DEFAULT_FPGA_BITFILE_MAP)
    gc = GlueConverter(DEFAULT_IOSPEC)
    config_AWG_as_DC(0)
    time.sleep(3)
    
    #Pre-generate patterns to run the ADC and to read from the scan chain.
    adc_op_glue = genpattern_ADC_Capture(1)
    sc_read_glue = genpattern_SC_write([0]*19,1000)
    
    
    #Set Scan Chain Configuration:  TestEn = 1  
    SC_PATTERN = SC_CFG(override=0,TestEn=1,Range2=0)
    pr.run_pattern( genpattern_SC_write(SC_PATTERN),outfile_tag="sc_cfg")
    
    #(2) Sweep ADC from 0mV to 1000mV and record the  results.
    with open("ADC_Sweep_Results.csv","w") as write_file:
        write_file.write("Vin(mV),Output Code\n")
    
        for vin in range(0,1000,100):
            #Set the input voltage:
            set_Vin_mV(vin)
            
            #Run the ADC to capture a reading.
            pr.run_pattern(adc_op_glue,outfile_tag="adc_op_result")
            adc_op_result = "adc_op_result_PXI1Slot16_NI6583_se_io.glue"
            adc_bits = gc.get_clocked_bitstream(gc.read_glue(adc_op_result), "DACclr", "CompOut")
            print("CompOut value at the end of each bit period: ",adc_bits)
            x = vec_to_int(adc_bits)
            print("ADC value inferred directly from CompOut: ",x)
            
            #Scan out the result
            pr.run_pattern(sc_read_glue,outfile_tag="sc_result")
            sc_result = "sc_result_PXI1Slot16_NI6583_se_io.glue"
            scanout_bits = gc.get_clocked_bitstream(gc.read_glue(sc_result), "S_CLK", "S_DOUT")
            print("These are the bits read back from the scan chain: ", scanout_bits)
            #These bits represent the ADC result.
            x = vec_to_int(scanout_bits[0:10])
            print("ADC Reading from the Scan Chain: ",x)
            write_file.write(str(vin)+","+str(x)+"\n")
            
def ROUTINE2_ADC_Capture_Scope():
    """Operate the ADC to digitize a range of values from TestEn (OSCILLOSCOPE ASSISTED)"""


    ASK_FOR_INPUT_CONNECTIONS = False

    if ASK_FOR_INPUT_CONNECTIONS:
        input("""REQUIREMENTS:
 > Oscilloscope Ch1 connected to CAPLO
 > Oscilloscope Ch2 connected to DACCLR
Press enter to continue...""")
    
    pr = PatternRunner(sg.log, DEFAULT_IOSPEC, DEFAULT_FPGA_BITFILE_MAP)
    gc = GlueConverter(DEFAULT_IOSPEC)
    config_AWG_as_DC(0)
    time.sleep(3)
    
    #Pre-generate patterns to run the ADC and to read from the scan chain.
    adc_op_glue = genpattern_ADC_Capture(10)
    sc_read_glue = genpattern_SC_write([0]*19,1000)
    
    #Set Scan Chain Configuration:  TestEn = 1  
    SC_PATTERN = SC_CFG(override=0,TestEn=1,Range2=0)
    pr.run_pattern( genpattern_SC_write(SC_PATTERN),outfile_tag="sc_cfg")
    
    #(2) Sweep ADC from 0mV to 1000mV and record the  results.
    with open("ADC_Sweep_Results.csv","w") as write_file:
        write_file.write("Vin(mV),Output Code\n")
    
        for vin in range(0,1000,10):
            
            #Set the input voltage:
            set_Vin_mV(vin)

            #Set up a 600 mV trigger on channel 1:
            sg.scope.write("HORIZONTAL:POSITION 5")  #Sets the trigger close to the left-hand side.
            sg.scope.write("HORIZONTAL:MODE MANUAL") #Manual mode: specify record length + sample rate.
            sg.scope.write("HORIZONTAL:MODE:RECORDLENGTH 10000") #RL = 10,000 ( = total pattern length of 20ns * 10k = 200 us)
            sg.scope.write("HORIZONTAL:MODE:SAMPLERATE 50E6") # = 20 ns/sample
            #sg.scope.write("HORIZONTAL:MODE:SCALE 20E-6") #Sets the horizontal resolution to 2us/div.
            #                                             #As a result we should have 20ns/sample
            sg.scope.setup_trigger(2,0.6) #600mV trigger on DACclr.
            
            #Run the ADC to capture a reading.
            pr.run_pattern(adc_op_glue,outfile_tag="adc_op_result")
            adc_op_result = "adc_op_result_PXI1Slot16_NI6583_se_io.glue"
            
            caplo_wave = sg.scope.get_wave(1)
            dacclr_wave = sg.scope.get_wave(2)

            result = interpret_CDAC_pattern_edges(caplo_wave, dacclr_wave)

            adc_bits = gc.get_clocked_bitstream(gc.read_glue(adc_op_result), "DACclr", "CompOut")
            adc_bits.reverse()
            print("CompOut value at the end of each bit period: ",adc_bits[1:])
            x = vec_to_int(adc_bits[1:])
            print("ADC value inferred directly from CompOut: ",x)

            #sg.scope.onscreen()
            write_file.write(str(vin)+","+str(result)+","+str(x)+"\n")




def ROUTINE3_Comparator_Offset_Tuning():
    """Determine comparator offset for DACclr state."""


    
    pr = PatternRunner(sg.log, DEFAULT_IOSPEC, DEFAULT_FPGA_BITFILE_MAP)
    gc = GlueConverter(DEFAULT_IOSPEC)
    config_AWG_as_DC(0)
    time.sleep(3)
    
    #Pre-generate patterns to run the ADC and to read from the scan chain.
    adc_op_glue = genpattern_from_waves_dict({"DACclr":[1]*1000, "Qequal":[0]*1000})
    
    #Set Scan Chain Configuration:  TestEn = 1  
    SC_PATTERN = SC_CFG(override=0,TestEn=1,Range2=0)
    pr.run_pattern( genpattern_SC_write(SC_PATTERN),outfile_tag="sc_cfg")
    
    #(2) Sweep ADC from 0mV to 1000mV and record the  results.
    with open("Comparator_Sweep.csv","w") as write_file:
        write_file.write("Vin(mV),CompOut\n")
    
        for vin in range(0,200,10):
            
            #Set the input voltage:
            set_Vin_mV(vin)

            #Setup a trigger for easy viewing:
            sg.scope.setup_trigger(2,0.6) #600mV trigger on DACclr.
            
            #Run the ADC
            pr.run_pattern(adc_op_glue,outfile_tag="adc_op_result")
            adc_op_result = "adc_op_result_PXI1Slot16_NI6583_se_io.glue"

            compout = gc.get_bitstream(gc.read_glue(adc_op_result),"CompOut")

            if any([i > 0 for i in compout]):
                result = 1
            else:
                result = 0
            
            write_file.write(str(vin)+","+str(result)+"\n")


def ROUTINE4_Front_End_Demo():
    """Demo Front End w/ Analog Pileup"""


    #NOTES:
    # - Trigger must be supplied from NI, pre-level-shifters. 

    pr = PatternRunner(sg.log, DEFAULT_IOSPEC, DEFAULT_FPGA_BITFILE_MAP)
    gc = GlueConverter(DEFAULT_IOSPEC)
    config_AWG_as_Pulse(500)
    time.sleep(3)


    fe_glue = genpattern_Front_End_demo(1)

    pr.run_pattern(fe_glue,outfile_tag="fe_result")


### HELPER FUNCTIONS ###



def genpattern_Front_End_demo(time_scale_factor):

    waves = {}

    waves["mclk"] =       [0]*10
    waves["read_ext"] =   [0]*10
    waves["Rst_ext"] =    [0]*10
    waves["bufsel_ext"] = [0]*10

    for i in range(10):
        #w/ time_scale_factor = 1, the period of mclk is 20 ticks or 2 MHz
        waves["mclk"] = waves["mclk"] + [1]*10*time_scale_factor + [0]*10*time_scale_factor


    return genpattern_from_waves_dict(waves)

#Get the implied value from a string of DACclr and capLo pulses only by counting posedges.
#This method makes no assumption about the bit period, and thus can be accurate w/ lower scope resolution.
def interpret_CDAC_pattern_edges(caplo_wave, dacclr_wave):

    gc = GlueConverter(DEFAULT_IOSPEC)

    
    THRESH = 0.6

    caplo_edges = []

    for idx in range(1,len(caplo_wave)):

        #If there is a dacclr edge, start a new bit approximation. 
        if (dacclr_wave[idx-1] < THRESH and dacclr_wave[idx] >= THRESH):
            caplo_edges.append(0)
            #print(f"(DBG) dacclr edge at {idx}")

        #Within each bit approximation, count the number of capLo edges.
        if (caplo_wave[idx-1] < THRESH and caplo_wave[idx] >= THRESH):
            caplo_edges[-1] = caplo_edges[-1] + 1
            #print(f"(DBG) caplo edge at {idx}")

    print(f"(DBG) caplo_edges: {caplo_edges}")

    if len(caplo_edges) != 11 or caplo_edges[0] != 0:
        print(f"ERROR: Malformed caplo_edges {caplo_edges}")
        gc.plot_waves([caplo_wave,dacclr_wave],["caplo","dacclr"],1)
        return -99

    binary_approximation = []
    
    for bit in range(1, 10):

        if caplo_edges[bit] - caplo_edges[bit-1] == 0:
            binary_approximation.append(1)

        elif caplo_edges[bit] - caplo_edges[bit-1] == 1:
            binary_approximation.append(0)
        
        else:
            print(f"ERROR: Malformed caplo_edges {caplo_edges}")
            gc.plot_waves([caplo_wave,dacclr_wave],["caplo","dacclr"],1)
            return -99

    print(f"(DBG) bin_approx: {binary_approximation}")

    #Notes:
    # - Reverse the binary approximation because it is naturally big-endian (MSB is decided first) whereas
    #   vec_to_int expects little-endian.
    # - Multiply by 2 b/c it is a 9-bit approximation.
    binary_approximation.reverse()
    
    return vec_to_int(binary_approximation)*2


def interpret_CDAC_pattern(caplo_wave, dacclr_wave):

    #print(dacclr_waveform)

    #Assume horizontal scale of 20ns per point, and that bits are 100 ns long (75 ns + 25 ns gap)
    # (2*100 ns)/(20ns) = 10
    BIT_PERIOD = 10 #20

    #Initial offset
    idx = 3

    THRESH = 0.6
    
    binary_approximations = []
    decimal_approximations = []

    for approximation in range(1,10):

        #Find the rising edge of DACclr.
        while idx < len(caplo_wave) and not (dacclr_wave[idx-1] < THRESH and dacclr_wave[idx] > THRESH):
            idx = idx + 1


        if idx >= len(caplo_wave):
            print("ERROR (interpret_CDAC_pattern): Reached the end of the waveform w/o seeing all 10 bits. Is the Oscope resolution set properly?")
            return -99
        
        print(f"(DBG) DACclr rising edge found at: {idx}")

        #Add 2 to get off the rising edge.
        idx = idx + 3
        
        binary_approximations.append([])
                                             
        for bit in range(approximation):
            #Note the inverted polarity here b/c capLo being high means the CDAC value is decreasing.
            if caplo_wave[idx] > THRESH:
                binary_approximations[-1].append(0)
            else:
                binary_approximations[-1].append(1)
            idx = idx + BIT_PERIOD

        decimal_approximations.append(vec_to_int(binary_approximations[-1])*(2**(10-approximation)))
        print("(DBG)",binary_approximations[-1], "==",decimal_approximations[-1])
        idx = idx - BIT_PERIOD


    return decimal_approximations[-1]
            




    
    
# Generates the pattern necessary to run the ADC.
def genpattern_ADC_Capture(time_scale_factor):
    
    waves = {}
    
    #Start off w/ some zeros to avoid extra pulse bug.
    waves["DACclr"] = [0]*10
    waves["Qequal"] = [0]*10
    waves["capClk"] = [0]*10
    waves["calc"]   = [0]*10
    waves["read_ext"]   = [0]*10
    
    
    for adc_bit in range(1,11):
        
        for clk_cycle in range(adc_bit):

            if clk_cycle == 0:
                #Each bit starts off w/ a DACclr pulse.
                waves["DACclr"] = waves["DACclr"] + [1,1,1]*time_scale_factor
                waves["capClk"] = waves["capClk"] + [1,1,1]*time_scale_factor
                waves["Qequal"] = waves["Qequal"] + [0,0,0]*time_scale_factor

            else:
                #capClk pulse
                waves["DACclr"] = waves["DACclr"] + [0,0,0]*time_scale_factor
                waves["capClk"] = waves["capClk"] + [1,1,1]*time_scale_factor
                waves["Qequal"] = waves["Qequal"] + [0,0,0]*time_scale_factor


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
            
            
            
        #Add a 0 for non-overlapping.    
        #waves["DACclr"] = waves["DACclr"] + [0]
        #waves["capClk"] = waves["capClk"] + [0]
        #waves["Qequal"] = waves["Qequal"] + [0]
        
        
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


def genpattern_from_waves_dict(waves_dict):

    #2) Writing to an ASCII file.
    with open("genpattern.txt",'w') as write_file:
        for w in waves_dict.keys():
            write_file.write(w+":"+"".join([str(x) for x in waves_dict[w]])+"\n")
            
    #3) Convert ASCII file to Glue.
    gc = GlueConverter(DEFAULT_IOSPEC)

    gc.ascii2Glue("genpattern.txt", 1, "genpattern")


    return "genpattern_se_io.glue"


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

    
ROUTINES = [ROUTINE0_Scan_Chain_Loopback,ROUTINE1_Comparator_Smoke_Test,ROUTINE2_ADC_Capture_ScanChain, ROUTINE2_ADC_Capture_Scope,ROUTINE3_Comparator_Offset_Tuning,ROUTINE4_Front_End_Demo]
