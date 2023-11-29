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

#Function to generate a SPROCKET2 test pixel scan chain vector (19 bits long)
#based on setting each individual field by name. 
def SC_CFG(override,TestEn,Range2,CapTrim=0):
    captrim_vec = int_to_vec(CapTrim,6)

    #SC is big-endian, but int_to_vec() is little-endian
    captrim_vec.reverse()
    
    return [0]*10 + captrim_vec + [override] + [TestEn] + [Range2]


def ROUTINE_Scan_Chain_Loopback():
    """Scan Chain Loopback"""

    pr = PatternRunner(sg.log, DEFAULT_IOSPEC, DEFAULT_FPGA_BITFILE_MAP)
    time.sleep(3)

    # 1) Generate some random data
    sc_data = list(np.random.binomial(1,0.5,size=19))
    print("Random Scan Chain Data: ",str(sc_data))

    # 2) Create a Glue waveform that writes the data to the scan chain.
    glue_wave = genpattern_SC_write(sc_data,1000)

    # 3) Run the Glue waveform
    out_1 = pr.run_pattern(glue_wave,outfile_tag="sc_1")[0]
    out_2 = pr.run_pattern(glue_wave,outfile_tag="sc_2")[0]

    # 4) Check that the data we read back is correct.
    # "sc_1_PXI1Slot16_NI6583_se_io.glue"
    # "sc_2_PXI1Slot16_NI6583_se_io.glue"
    gc = GlueConverter(DEFAULT_IOSPEC)

    scanout_bits = gc.get_clocked_bitstream(gc.read_glue(out_2), "S_CLK", "S_DOUT")
    print("Received:",str(scanout_bits))


def ROUTINE_Comparator_Smoke_Test():
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
    smoke_1 = pr.run_pattern(smoke_test_pattern,outfile_tag="smoke_1")[0]

    #Smoke 2: Expected output -- CompOut = 1
    set_Vin_mV(1000)
    smoke_2 = pr.run_pattern(smoke_test_pattern,outfile_tag="smoke_2")[0]

    print("Smoke Test 1/2 (expected result: all 0's)")
    print(gc.get_bitstream(gc.read_glue(smoke_1),"CompOut"))
    print("Smoke Test 2/2 (expected result: all 1's)")
    print(gc.get_bitstream(gc.read_glue(smoke_2),"CompOut"))



def ROUTINE_Leakage_Test():
    """Pulse a voltage on the CDAC output to see how fast it leaks away."""

    pr = PatternRunner(sg.log, DEFAULT_IOSPEC, DEFAULT_FPGA_BITFILE_MAP)
    gc = GlueConverter(DEFAULT_IOSPEC)
    config_AWG_as_DC(0)
    time.sleep(3)

    #Set Scan Chain Configuration:  TestEn = 1  
    SC_PATTERN = SC_CFG(override=0,TestEn=1,Range2=0)
    pr.run_pattern( genpattern_SC_write(SC_PATTERN),outfile_tag="sc_cfg")
    
    #Pre-generate patterns to run the ADC and to read from the scan chain.
    #Note that when calc is low, any capClk pulse leads to a capHib pulse.
    #We include Rst = 1 so that capHib is not gated.
    adc_op_glue = genpattern_from_waves_dict({"calc":[0]*1000,"DACclr":[1]*100+[0]*900, "Qequal":[0]*101+[1]*899,"capClk":[1]*1000,"Rst_ext":[1]*1000})

    #Run the ADC
    adc_op_result = pr.run_pattern(adc_op_glue,outfile_tag="adc_op_result")[0]
    #"adc_op_result_PXI1Slot16_NI6583_se_io.glue"



def ROUTINE_Qequal_Charging_Test():
    """Apply a short pulse on Qequal to see how much charge is shared."""

    pr = PatternRunner(sg.log, DEFAULT_IOSPEC, DEFAULT_FPGA_BITFILE_MAP)
    gc = GlueConverter(DEFAULT_IOSPEC)
    config_AWG_as_DC(0)
    time.sleep(3)

    #Set Scan Chain Configuration:  TestEn = 1  
    SC_PATTERN = SC_CFG(override=0,TestEn=1,Range2=0)
    pr.run_pattern( genpattern_SC_write(SC_PATTERN),outfile_tag="sc_cfg")

    qequal_cyc = int(input("How many cycles should Qequal be asserted?"))
    
    #Note that when calc is low, any capClk pulse leads to a capHib pulse.
    #We include Rst = 1 so that capHib is not gated.
    adc_op_glue = genpattern_from_waves_dict({"calc":   [0]*2000,
                                              "capClk": [1]*1000+[0]*1000,
                                              "Rst_ext":[1]*200,
                                              "DACclr": [1]*1000+[0]*1000,
                                              "Qequal": [0]*1001+[1]*(qequal_cyc)+[0]*(999-qequal_cyc)})

    #Run the ADC
    adc_op_result = pr.run_pattern(adc_op_glue,outfile_tag="adc_op_result")[0]
    

def ROUTINE_Comparator_Offset_Tuning():
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
            adc_op_result = pr.run_pattern(adc_op_glue,outfile_tag="adc_op_result")[0]
            #"adc_op_result_PXI1Slot16_NI6583_se_io.glue"

            compout = gc.get_bitstream(gc.read_glue(adc_op_result),"CompOut")

            if any([i > 0 for i in compout]):
                result = 1
            else:
                result = 0
            
            write_file.write(str(vin)+","+str(result)+"\n")


def ROUTINE_Front_End_Demo():
    """Demo Front End w/ Analog Pileup"""

   

    #NOTES:
    # - Trigger must be supplied from NI, pre-level-shifters. 

    pr = PatternRunner(sg.log, DEFAULT_IOSPEC, DEFAULT_FPGA_BITFILE_MAP)
    gc = GlueConverter(DEFAULT_IOSPEC)
    
    pm = int(input("pulse magnitude (mV)?"))
    
    
    config_AWG_as_Pulse(pm, pulse_width_us=0.25, pulse_period_us=0.3)
    time.sleep(3)


    fe_glue = genpattern_Front_End_demo(1)

    pr.run_pattern(fe_glue,outfile_tag="fe_result")
    
    
def ROUTINE_Front_End_Sweep():
    """SWEEP Front End w/ Analog Pileup"""

   
    #NOTES:
    # - Trigger must be supplied from NI, pre-level-shifters. 

    pr = PatternRunner(sg.log, DEFAULT_IOSPEC, DEFAULT_FPGA_BITFILE_MAP)
    gc = GlueConverter(DEFAULT_IOSPEC)
    
    config_AWG_as_Pulse(10, pulse_width_us=0.25, pulse_period_us=0.3)
    time.sleep(3)
    fe_glue = genpattern_Front_End_demo(1)
    
    with open("FE_Sweep.csv","w") as write_file:
        write_file.write("Pulse Mag(mV),CompOut\n")
        for pulse_mag in range(10,300,10):
        
        
            set_pulse_mag(pulse_mag)

            sg.scope.setup_trigger(3,0.6)
            
            pr.run_pattern(fe_glue,outfile_tag="fe_result")
            
            CompInp_wave = sg.scope.get_wave(2)
            Rst_wave = sg.scope.get_wave(3)
        
            result = CompInp_wave[falling_edge_idx(Rst_wave,2)-5]
        
            print(result)
            
            
            write_file.write(str(pulse_mag)+","+str(result)+"\n")
    

def ROUTINE_fpga_offset_debug():
    """Debug FPGA readback offset when reading a pattern multiple times."""

    #Set up pr, gc, and AWG
    pr = PatternRunner(sg.log, DEFAULT_IOSPEC, DEFAULT_FPGA_BITFILE_MAP)
    gc = GlueConverter(DEFAULT_IOSPEC)
    config_AWG_as_DC(0)
    time.sleep(3)

    token_pattern = [1,0,1,0,1,1,0,0,1,1,1,1]

    debug_glue = genpattern_from_waves_dict({"DACclr":[0]*20+token_pattern+[0]*20}) 

    for i in range(10):

        #Run the ADC to capture a reading.
        debug_result = pr.run_pattern(debug_glue,outfile_tag="debug")[0]
        #"debug_PXI1Slot16_NI6583_se_io.glue"

        dacclr_wave = gc.get_bitstream(gc.read_glue(debug_result),"DACclr")


        for j in range(40):
            #print(dacclr_wave[j:j+len(token_pattern)], token_pattern)
            if dacclr_wave[j:j+len(token_pattern)] == token_pattern:
                
                print(f"TOKEN OFFSET: {j}")
    
def ROUTINE_Transfer_Function_vs_CapTrim():
    """Capture the ADC Transfer function vs CapTrim, using Caplo->Spacely method"""

    VIN_STEP_mV = 1

    VIN_RANGE = [i for i in range(0,1000,VIN_STEP_mV)]

    CAPTRIM_RANGE = [i for i in range(0,63,1)]

    #Set up pr, gc, and AWG
    pr = PatternRunner(sg.log, DEFAULT_IOSPEC, DEFAULT_FPGA_BITFILE_MAP)
    gc = GlueConverter(DEFAULT_IOSPEC)
    config_AWG_as_DC(0)
    time.sleep(3)
    
    #Pre-generate patterns to run the ADC and to read from the scan chain.
    adc_op_glue = genpattern_ADC_Capture(10)

    result_values_by_captrim = []

    for captrim in CAPTRIM_RANGE:

        #Start a new list of result values for this captrim.
        result_values_by_captrim.append([])

        #Set CapTrim value and ensure 
        SC_PATTERN = SC_CFG(override=0,TestEn=1,Range2=0, CapTrim=captrim)
        pr.run_pattern( genpattern_SC_write(SC_PATTERN),outfile_tag="sc_cfg")

        for vin in range(0,1000,VIN_STEP_mV):
                
            #Set the input voltage:
            set_Vin_mV(vin)
                
            result = run_pattern_get_caplo_result(pr, gc, adc_op_glue)

            result_values_by_captrim[-1].append(result)


    print(result_values_by_captrim)

    write_parameter_sweep_to_csv(CAPTRIM_RANGE,
                                 VIN_RANGE,
                                 result_values_by_captrim,
                                 f"Transfer_Function_vs_CapTrim_Vin_step_by_{VIN_STEP_mV}_on_"+time.strftime("%Y_%m_%d")+".csv",
                                 row_param_name="Vin")
    

def ROUTINE_Transfer_Function_vs_Vref():
    """Capture the ADC Transfer function for different Vref_adc voltages, using Caplo->Spacely method"""

    VIN_STEP_mV = 10

    VIN_RANGE = [i for i in range(0,1000,VIN_STEP_mV)]

    VREF_RANGE = [0.6, 0.8, 1.0, 1.2]

    #Set up pr, gc, and AWG
    pr = PatternRunner(sg.log, DEFAULT_IOSPEC, DEFAULT_FPGA_BITFILE_MAP)
    gc = GlueConverter(DEFAULT_IOSPEC)
    config_AWG_as_DC(0)

    #Set CapTrim value = 0
    SC_PATTERN = SC_CFG(override=0,TestEn=1,Range2=0, CapTrim=0)
    pr.run_pattern( genpattern_SC_write(SC_PATTERN),outfile_tag="sc_cfg")
    
    time.sleep(3)
    
    #Pre-generate patterns to run the ADC and to read from the scan chain.
    adc_op_glue = genpattern_ADC_Capture(10)

    result_values_by_vref = []

    for vref in VREF_RANGE:

        #Start a new list of result values for this captrim.
        result_values_by_vref.append([])

        V_PORT["Vref_adc"].set_voltage(vref)

        for vin in VIN_RANGE:
                
            #Set the input voltage:
            set_Vin_mV(vin)
                
            result = run_pattern_get_caplo_result(pr, gc, adc_op_glue)

            result_values_by_vref[-1].append(result)


    print(result_values_by_vref)

    write_parameter_sweep_to_csv(VREF_RANGE,
                                 VIN_RANGE,
                                 result_values_by_vref,
                                 f"Transfer_Function_vs_Vref_Vin_step_by_{VIN_STEP_mV}_on_"+time.strftime("%Y_%m_%d")+".csv",
                                 row_param_name="Vin")


def ROUTINE_Transfer_Function_vs_Timescale():
    """Capture the ADC Transfer function for different Time Scale Factors, using Caplo->Spacely method"""

    VIN_STEP_mV = 1

    VIN_RANGE = [i for i in range(0,1000,VIN_STEP_mV)]

    TIMESCALE_RANGE = [1,2,3,5,10] #,1,1,1,1,1,1,1,1,1,3,3,3,3,3,3,3,3,3,3]#[1,2,3,5,10,15,30,100]

    #Set up pr, gc, and AWG
    pr = PatternRunner(sg.log, DEFAULT_IOSPEC, DEFAULT_FPGA_BITFILE_MAP)
    gc = GlueConverter(DEFAULT_IOSPEC)
    config_AWG_as_DC(0)

    #Set CapTrim value = 0
    SC_PATTERN = SC_CFG(override=0,TestEn=1,Range2=0, CapTrim=0)
    pr.run_pattern( genpattern_SC_write(SC_PATTERN),outfile_tag="sc_cfg")
    
    time.sleep(3)
    
    result_values = []

    for timescale in TIMESCALE_RANGE:

        #Pre-generate patterns to run the ADC and to read from the scan chain.
        adc_op_glue = genpattern_ADC_Capture(timescale, apply_pulse_1_fix=False, tsf_qequal = 10)

        #Start a new list of result values for this captrim.
        result_values.append([])

        for vin in VIN_RANGE:
                
            #Set the input voltage:
            set_Vin_mV(vin)
                
            result = run_pattern_get_caplo_result(pr, gc, adc_op_glue)

            result_values[-1].append(result)


    print(result_values)

    write_parameter_sweep_to_csv(TIMESCALE_RANGE,
                                 VIN_RANGE,
                                 result_values,
                                 f"Transfer_Function_vs_Timescale_Vin_step_by_{VIN_STEP_mV}_on_"+time.strftime("%Y_%m_%d")+".csv",
                                 row_param_name="Vin")
                                 
                                 
                                 
def ROUTINE_Transfer_Function_over_Time():
    """Sample the ADC Transfer Function over a period of time, using Caplo->Spacely method"""

    VIN_STEP_mV = 1

    VIN_RANGE = [i for i in range(0,1000,VIN_STEP_mV)]

    SAMPLE_INTERVAL_MINUTES = 10

    initial_date_string = time.strftime("%Y_%m_%d")

    #Set up pr, gc, and AWG
    pr = PatternRunner(sg.log, DEFAULT_IOSPEC, DEFAULT_FPGA_BITFILE_MAP)
    gc = GlueConverter(DEFAULT_IOSPEC)
    config_AWG_as_DC(0)

    #Set CapTrim value = 0
    SC_PATTERN = SC_CFG(override=0,TestEn=1,Range2=0, CapTrim=0)
    pr.run_pattern( genpattern_SC_write(SC_PATTERN),outfile_tag="sc_cfg")
    
    #Pre-generate patterns to run the ADC and to read from the scan chain.
    adc_op_glue = genpattern_ADC_Capture(10)
    
    time.sleep(3)
    
    result_values = []
    time_samples  = []
    
    time_elapsed = 0

    while True:

        

        #Start a new list of result values for this sample.
        result_values.append([])
        time_samples.append(time_elapsed)

        for vin in VIN_RANGE:
                
            #Set the input voltage:
            set_Vin_mV(vin)
                
            result = run_pattern_get_caplo_result(pr, gc, adc_op_glue)

            result_values[-1].append(result)


    

        write_parameter_sweep_to_csv(time_samples,
                                    VIN_RANGE,
                                    result_values,
                                    f"Transfer_Function_sampled_every_{SAMPLE_INTERVAL_MINUTES}_mins_Vin_step_by_{VIN_STEP_mV}_on_"+initial_date_string+".csv",
                                    row_param_name="Vin")
         
         
        print(f"SLEEPING for {SAMPLE_INTERVAL_MINUTES*60} seconds...")
        time.sleep(SAMPLE_INTERVAL_MINUTES*60)
        time_elapsed = time_elapsed + SAMPLE_INTERVAL_MINUTES


def ROUTINE_average_transfer_function():
    """Capture the Average ADC Transfer function using Caplo->Spacely method"""

    VIN_STEP_mV = 1

    NUM_AVERAGES = 100

    #Set up pr, gc, and AWG
    pr = PatternRunner(sg.log, DEFAULT_IOSPEC, DEFAULT_FPGA_BITFILE_MAP)
    gc = GlueConverter(DEFAULT_IOSPEC)
    config_AWG_as_DC(0)
    time.sleep(3)
    
    #Pre-generate patterns to run the ADC and to read from the scan chain.
    adc_op_glue = genpattern_ADC_Capture(10)

    write_file = open(f"Average_Transfer_Function_Vin_step_by_{VIN_STEP_mV}_on_"+time.strftime("%Y_%m_%d")+".csv","w")

    write_file.write("Vin,Avg Result,Std Dev\n")


    #Set CapTrim value and ensure 
    SC_PATTERN = SC_CFG(override=0,TestEn=1,Range2=0, CapTrim=0)
    pr.run_pattern( genpattern_SC_write(SC_PATTERN),outfile_tag="sc_cfg")


    for vin in range(0,1000,VIN_STEP_mV):
                
        #Set the input voltage:
        set_Vin_mV(vin)

        results_this_vin = []

        for i in range(NUM_AVERAGES):
            #Run the ADC to capture a reading.
            adc_op_result = pr.run_pattern(adc_op_glue,outfile_tag="adc_op_result")[0]
            #"adc_op_result_PXI1Slot4_NI6583_se_io.glue"

            #Get DACclr and capLo
            dacclr_wave = gc.get_bitstream(gc.read_glue(adc_op_result),"DACclr")
            caplo_wave = gc.get_bitstream(gc.read_glue(adc_op_result),"capLo_ext")

            result = interpret_CDAC_pattern_edges(caplo_wave, dacclr_wave)

            results_this_vin.append(result)

        write_file.write(f"{vin},{np.mean(results_this_vin)},{np.std(results_this_vin)}\n")


def ROUTINE_Full_Conversion_Demo():
    """Demo of a full conversion, all the way from preamplifier through the ADC."""

    #NOTES:
    # - Trigger must be supplied from NI, pre-level-shifters. 

    pr = PatternRunner(sg.log, DEFAULT_IOSPEC, DEFAULT_FPGA_BITFILE_MAP)
    gc = GlueConverter(DEFAULT_IOSPEC)


    print("NOTE: ENSURE THAT AWG TRIG IS CONNECTED to phi1_ext (silk as 'P1.0') on the NI side.")
    
    pm = int(input("pulse magnitude (mV)?"))
    

    time_scale_factor = 10
    
    config_AWG_as_Pulse(pm, pulse_width_us=0.25*time_scale_factor, pulse_period_us=0.25*time_scale_factor+0.05)
    time.sleep(3)

    #Set CapTrim value and ensure TestEn=0
    SC_PATTERN = SC_CFG(override=0,TestEn=0,Range2=0, CapTrim=0)
    pr.run_pattern( genpattern_SC_write(SC_PATTERN),outfile_tag="sc_cfg")

    fc_glue = genpattern_Full_Conversion(time_scale_factor)

    fc_result = pr.run_pattern(fc_glue,outfile_tag="fc_result")[0]

    #"fc_result_PXI1Slot16_NI6583_se_io.glue"

    #Get DACclr and capLo
    dacclr_wave = gc.get_bitstream(gc.read_glue(fc_result),"DACclr")
    caplo_wave = gc.get_bitstream(gc.read_glue(fc_result),"capLo_ext")

    result = interpret_CDAC_pattern_edges(caplo_wave, dacclr_wave)

    print(f"RESULT: {result}")


def ROUTINE_Full_Conversion_Sweep():
    """FULL SWEEP of full conversion, all the way from preamplifier through the ADC."""

    VIN_STEP_mV = 50
    
    #NOTES:
    # - Trigger must be supplied from NI, pre-level-shifters. 

    pr = PatternRunner(sg.log, DEFAULT_IOSPEC, DEFAULT_FPGA_BITFILE_MAP)
    gc = GlueConverter(DEFAULT_IOSPEC)


    print("NOTE: ENSURE THAT AWG TRIG IS CONNECTED to phi1_ext (silk as 'P1.0') on the NI side.")
    

    config_AWG_as_Pulse(100, pulse_width_us=0.25, pulse_period_us=0.3)
    time.sleep(3)

    #Set CapTrim value and ensure TestEn=0
    SC_PATTERN = SC_CFG(override=0,TestEn=0,Range2=0, CapTrim=0)
    pr.run_pattern( genpattern_SC_write(SC_PATTERN),outfile_tag="sc_cfg")

    fc_glue = genpattern_Full_Conversion(1)


    write_file = open("Full_Conversion_Sweep.csv","w")
    write_file.write("Vin,Result\n")
    
    for pulse_mag in range(10,500,VIN_STEP_mV):
        set_pulse_mag(pulse_mag)

        fc_result = pr.run_pattern(fc_glue,outfile_tag="fc_result")[0]

        #"fc_result_PXI1Slot16_NI6583_se_io.glue"

        #Get DACclr and capLo
        dacclr_wave = gc.get_bitstream(gc.read_glue(fc_result),"DACclr")
        caplo_wave = gc.get_bitstream(gc.read_glue(fc_result),"capLo_ext")

        result = interpret_CDAC_pattern_edges(caplo_wave, dacclr_wave)

        print(f"RESULT: {result}")
        write_file.write(f"{pulse_mag},{result}\n")


    write_file.close()


def ROUTINE_Noise_Histogram():
    """Generate a noise histogram for the ADC"""

    VTEST_mV = 100

    HISTOGRAM_SAMPLES = 1000000

    CENTER_CODE_SAMPLES = 2000

    #Set up pr, gc, and AWG
    pr = PatternRunner(sg.log, DEFAULT_IOSPEC, DEFAULT_FPGA_BITFILE_MAP)
    gc = GlueConverter(DEFAULT_IOSPEC)
    config_AWG_as_DC(0)

    #Set CapTrim value = 0
    SC_PATTERN = SC_CFG(override=0,TestEn=1,Range2=0, CapTrim=0)
    pr.run_pattern( genpattern_SC_write(SC_PATTERN),outfile_tag="sc_cfg")
    
    time.sleep(3)
    
    #Pre-generate patterns to run the ADC and to read from the scan chain.
    pattern_glue = genpattern_ADC_Capture(10)
    
    histo = SP2_Vin_histogram(pr,gc,pattern_glue, SP2_center_code(pr,gc,pattern_glue,VTEST_mV, samples_per_val=CENTER_CODE_SAMPLES), HISTOGRAM_SAMPLES)


    print(histo)
    
    with open("SPROCKET2_Noise_Histogram_100mV.csv","w") as write_file:
        write_file.write("Code,Count\n")

        for code in histo.keys():
            write_file.write(f"{code},{histo[code]}\n")

### HELPER FUNCTIONS ###


def SP2_Vin_histogram(pr, gc, pattern_glue, Vtest_mV: int, points: int) -> dict[int, int]:
    """
    Sets Vin and takes a specified number of points, returning a histogram of the resulting output codes.

    :param Vtest_mV: Voltage to test at in milli-volts
    :param points: Number of samples to take
    :return: See "liststring_histogram()" docblock
    """

    set_Vin_mV(Vtest_mV)

    results = []

    for i in range(points):
        results.append(run_pattern_get_caplo_result(pr, gc, pattern_glue))

    return liststring_histogram(" ".join([str(x) for x in results]))


def SP2_center_code(pr, gc, pattern_glue, Vtest_init_mV: float, samples_per_val: int = 1000):


    Vtest = Vtest_init_mV
    Vtest_last = Vtest_init_mV

    count_outside = 1000

    sg.log.info(f"Running centering code from {Vtest_init_mV}mV...")

    while True:
        histogram = SP2_Vin_histogram(pr, gc, pattern_glue, Vtest, samples_per_val)
        mode = max(histogram, key=histogram.get) # primary bin count/statistical mode of all values in histogram
        #print(histogram)

        count_below = 0
        count_above = 0
        for bin_val, bin_count in histogram.items():
            if bin_val > mode:
                count_above += bin_count
            elif mode < bin_val:
                count_below += bin_count

        sg.log.debug(f"Vtest:{Vtest:.2f}mV, mode:{mode}, count_below_mode:{count_below}, count_above_mode:{count_above}")

        # That shouldn't be the case really... something is probably misconnected
        if mode == 0:
            sg.log.warning(f"Suspicious mode of 0 for Vtest={Vtest:.2f}mV")

        #If we are less centered than the previous guess, take the
        #last one and be done with it.
        #PROOF that this loop is non-infinite: count_outside is strictly decreasing and positive.
        if count_above + count_below >= count_outside:
            sg.log.notice(f"Centered at Vtest: {Vtest_last:.2f}mV")
            return Vtest_last

        #If not, that is if this was an improvement, try again.
        Vtest_last = Vtest
        count_outside = count_above + count_below

        #Tune by increments of 0.1 mV.
        if count_above > count_below:
            Vtest = Vtest - 0.1
        else:
            Vtest = Vtest + 0.1


# Helper function to write a CSV file.
# col_param_range = List containing all values of the column parameter.
# row_param_range = List containing all values of the row parameter.
# results = List of lists. Each sublist corresponds to a column parameter value and each item in the sublist corresponds to a row param value.
def write_parameter_sweep_to_csv(col_param_range, row_param_range, results, filename, col_param_name="Col_Param",row_param_name="Row_Param"):

    assert(len(results) == len(col_param_range))
    assert(len(results[0]) == len(row_param_range))

    write_file = open(filename, "w")

    #First row: write out all the column headers.
    write_file.write(f"{row_param_name}")
    for col_param in col_param_range:
            write_file.write(f",{col_param}")

    write_file.write("\n")

    #For each row after that, start by writing vin...
    row_idx = 0
    for row_param in row_param_range:
        write_file.write(f"{row_param}")

        col_idx = 0

        #Then write down the results ...
        for col_param in col_param_range:
            write_file.write(f",{results[col_idx][row_idx]}")

            col_idx = col_idx + 1

        write_file.write("\n")

        row_idx = row_idx+1


    write_file.close()



def falling_edge_idx(wave, number=1, thresh=0.6):

    falling_edge_count = 0

    for i in range(1,len(wave)):
        if wave[i] < thresh and wave[i-1] > thresh:
            falling_edge_count = falling_edge_count + 1
            
            if falling_edge_count == number:
                return i


#Run an ADC acquisition pattern w/ a given PatternRunner and use a GlueConverter to read/interpret the result.
def run_pattern_get_caplo_result(pr, gc, pattern_glue):
    #Run the ADC to capture a reading.
    adc_op_result = pr.run_pattern(pattern_glue,outfile_tag="adc_op_result")[0]
    #"adc_op_result_PXI1Slot16_NI6583_se_io.glue"

    #Get DACclr and capLo
    dacclr_wave = gc.get_bitstream(gc.read_glue(adc_op_result),"DACclr")
    caplo_wave = gc.get_bitstream(gc.read_glue(adc_op_result),"capLo_ext")

    result = interpret_CDAC_pattern_edges(caplo_wave, dacclr_wave)
    
    return result


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
            #print(f"(DBG) dacclr edge at {idx*25} ns")

        #Within each bit approximation, count the number of capLo edges.
        if (caplo_wave[idx-1] < THRESH and caplo_wave[idx] >= THRESH):
            caplo_edges[-1] = caplo_edges[-1] + 1
            #print(f"(DBG) caplo edge at {idx*25} ns")

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


            

# # # # # # # # # # # # # # # # # # # # # # # # # # 
#            PATTERN GENERATORS                   #
# # # # # # # # # # # # # # # # # # # # # # # # # # 
    
# Generates the pattern necessary to run the ADC.
def genpattern_ADC_Capture(time_scale_factor, apply_pulse_1_fix=False, tsf_qequal=1):
    
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
                
                if apply_pulse_1_fix:
                    #Extend this pulse only to be 10x longer.
                    waves["DACclr"] = waves["DACclr"] + [1,1,1]*10*time_scale_factor
                    waves["capClk"] = waves["capClk"] + [1,1,1]*10*time_scale_factor
                    waves["Qequal"] = waves["Qequal"] + [0,0,0]*10*time_scale_factor

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
            waves["DACclr"] = waves["DACclr"] + [0,0,0]*time_scale_factor*tsf_qequal
            waves["capClk"] = waves["capClk"] + [0,0,0]*time_scale_factor*tsf_qequal
            waves["Qequal"] = waves["Qequal"] + [1,1,1]*time_scale_factor*tsf_qequal
            
            
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


def genpattern_Full_Conversion(time_scale_factor):


    #Initialize wave dictionary
    waves = {}

    #Everything starts out at 0 for 10 cycles. 
    waves["mclk"] =       [0]*10
    #waves["read_ext"] =   [0]*10  --> at the end we will just assign read_ext = calc
    waves["Rst_ext"] =    [0]*10 
    waves["bufsel_ext"] = [0]*10 
    waves["capClk"] = [0]*10    
    waves["Qequal"] = [0]*10
    waves["DACclr"] = [0]*10
    waves["calc"]   = [0]*10
    

    ### RESET PHASE ###

    #mclk=0 and Rst=1. read/calc=0, but we pulse it at the beginning to make sure SAR logic is reset.
    waves["mclk"] =       waves["mclk"]+[0]*40
    #waves["read_ext"] =   waves["read_ext"] + [1]*5 + [0]*35
    waves["calc"] =   waves["calc"] + [1]*5 + [0]*35
    waves["Rst_ext"] =    waves["Rst_ext"] + [1]*40

    #Establish autorange comparison voltage of 0.75V, see user manual.
    waves["bufsel_ext"] = waves["bufsel_ext"] + [0]*20 + [1]*20
    waves["capClk"] = waves["capClk"] + [0,1,1,1,0,0,0,0,0,1,1,1,0] + [0]*27
    waves["Qequal"] = waves["Qequal"] + [0,0,0,0,0,1,1,1,0,0,0,0,0,1,1,1,0] + [0]*23

    #DACclr = 0
    waves["DACclr"] =       waves["DACclr"]+[0]*40

    
    ### SAMPLING PHASE ###

    for i in range(10):
        #w/ time_scale_factor = 1, the period of mclk is 20 ticks or 2 MHz
        waves["mclk"] = waves["mclk"] + [1]*10*time_scale_factor + [0]*10*time_scale_factor

        #In the sampling phase, read=Rst=0, bufse1=1 (Vref_fe), and all the ADC signals are zero.
        #waves["read_ext"] = waves["read_ext"] + [0]*20*time_scale_factor
        waves["calc"] = waves["calc"] + [0]*20*time_scale_factor
        waves["capClk"] = waves["capClk"] + [0]*20*time_scale_factor
        waves["Qequal"] = waves["Qequal"] + [0]*20*time_scale_factor
        waves["DACclr"] = waves["DACclr"] + [0]*20*time_scale_factor
        waves["Rst_ext"] = waves["Rst_ext"] + [0]*20*time_scale_factor
        waves["bufsel_ext"] = waves["bufsel_ext"] + [1]*20*time_scale_factor

    ### CONVERSION PHASE ###

    #bufsel->0 and Rst->1. Two cycles later, read->1
    #waves["read_ext"] = waves["read_ext"] + [0,0,1]
    waves["calc"] = waves["calc"] +         [0,0,1]
    waves["capClk"] = waves["capClk"] +     [0,0,0]
    waves["Qequal"] = waves["Qequal"] +     [0,0,0]
    waves["DACclr"] = waves["DACclr"] +     [0,0,0]
    waves["Rst_ext"] = waves["Rst_ext"] +   [1,1,1]
    waves["bufsel_ext"] = waves["bufsel_ext"] + [0,0,0]
    waves["mclk"] = waves["mclk"] + [0,0,0]

    
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
            
        
        
    #Final DACclr pulse.
    waves["DACclr"] = waves["DACclr"] + [1,1,1]*time_scale_factor
    waves["capClk"] = waves["capClk"] + [1,1,1]*time_scale_factor
    waves["Qequal"] = waves["Qequal"] + [0,0,0]*time_scale_factor

    #Fill in calc+Rst with all 1's, and mclk+bufsel with all 0's
    waves["calc"] = waves["calc"] + [1]*(len(waves["DACclr"])-len(waves["calc"]))
    waves["Rst_ext"] = waves["Rst_ext"] + [1]*(len(waves["DACclr"])-len(waves["Rst_ext"]))
    waves["mclk"] = waves["mclk"] + [0]*(len(waves["DACclr"])-len(waves["mclk"]))
    waves["bufsel_ext"] = waves["bufsel_ext"] + [0]*(len(waves["DACclr"])-len(waves["bufsel_ext"]))


    waves["read_ext"] = waves["calc"]

    waves["phi1_ext"] = [(1-x) for x in waves["mclk"]]
    waves["phi1_ext"][0:50] = [0]*51
    #waves["mclk"][7:]  #phi1_ext will be used to trigger the AWG. It is a copy of mclk, shifted earlier by 175 ns (7 ticks)

    return genpattern_from_waves_dict(waves)
    
def genpattern_Front_End_demo(time_scale_factor):

    waves = {}

    waves["mclk"] =       [0]*10
    waves["read_ext"] =   [0]*10 
    waves["Rst_ext"] =    [0]*10 
    waves["bufsel_ext"] = [0]*10 
    waves["capClk"] = [0]*10    #Note: capClk and Qequal are only needed for setting up the autorange threshold.
    waves["Qequal"] = [0]*10
    

    #Reset phase
    waves["mclk"] =       waves["mclk"]+[0]*40
    waves["read_ext"] =   waves["read_ext"] + [1]*5 + [0]*35
    waves["Rst_ext"] =    waves["Rst_ext"] + [1]*40
    waves["bufsel_ext"] = waves["bufsel_ext"] + [0]*20 + [1]*20
    waves["capClk"] = waves["capClk"] + [0,1,1,1,0,0,0,0,0,1,1,1,0] 
    waves["Qequal"] = waves["Qequal"] + [0,0,0,0,0,1,1,1,0,0,0,0,0,1,1,1,0]
    
    #Sampling Phase
    for i in range(10):
        #w/ time_scale_factor = 1, the period of mclk is 20 ticks or 2 MHz
        waves["mclk"] = waves["mclk"] + [1]*10*time_scale_factor + [0]*10*time_scale_factor

        waves["read_ext"] = waves["read_ext"] + [0]*20*time_scale_factor
        waves["Rst_ext"] = waves["Rst_ext"] + [0]*20*time_scale_factor
        waves["bufsel_ext"] = waves["bufsel_ext"] + [1]*20*time_scale_factor
        

    waves["mclk"] = waves["mclk"] + [0]*42
    waves["read_ext"] = waves["read_ext"] + [0,0] + [1]*40
    waves["bufsel_ext"] = waves["bufsel_ext"] + [0]*42
    waves["Rst_ext"] = waves["Rst_ext"] + [1]*42

    waves["phi1_ext"] = waves["mclk"][7:]  #phi1_ext will be used to trigger the AWG. It is a copy of mclk, shifted earlier by 175 ns (7 ticks)

    return genpattern_from_waves_dict(waves)


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

    
ROUTINES = [ROUTINE_Transfer_Function_over_Time, ROUTINE_Transfer_Function_vs_Vref, ROUTINE_average_transfer_function, ROUTINE_Transfer_Function_vs_Timescale, ROUTINE_Noise_Histogram, ROUTINE_Transfer_Function_vs_CapTrim]
