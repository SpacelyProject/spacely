#
# Spacely Common Utilities
#
## INSTRUMENT CONTROL FUNCTIONS ##


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
import tkinter as tk
from tkinter import filedialog
import pyvisa

try:
    import matplotlib.pyplot as plt
except ImportError:
    print("WARNING: matplotlib could not be imported. Analysis plotting functions may not work.")


sys.path.append(os.path.abspath("./src"))


#Import utilities from py-libs-common
from hal_serial import * #todo: this shouldn't import all symbols but just the ArudinoHAL class
from pattern_runner import *
from Spacely_Caribou import *



from fnal_libIO import *
from fnal_libinstrument import *
from fnal_ni_toolbox import * #todo: this should import specific class(es)
import fnal_log_wizard as liblog

from Master_Config import *
import Spacely_Globals as sg



# SPACELY GLOBAL VARIABLES


def get_bit(x, bit_pos):
    if x & (1 << bit_pos) > 0:
        return 1
    else:
        return 0
 

# Converts an int to a little-endian vector
# 4 --> [0,0,1]
def int_to_vec(x, vec_len):
    vec = []
    for i in range(vec_len):
        vec.append(get_bit(x,i))      
    return vec

# Converts a little-endian vector to an int
# [0,0,1] --> 4
def vec_to_int(vec):
    x = 0
    for i in range(len(vec)):
        if vec[i] == 1:
            x = x+2**i
    return x



def abbreviate_list(big_list):
    #It's well known that any number smaller than 210 is not that big.
    if len(big_list) < 106:
        return str(big_list)
    else:
        s1 = ",".join([str(x) for x in big_list[:50]])
        s2 = ",".join([str(x) for x in big_list[-50:]])
        return "["+s1+".........."+s2+"] (total # elems = "+str(len(big_list))+")"


def format_time(value: float, precision: int = 5) -> str:
    if value is None:
        return "N/A"
    return si_format(value, precision, u'{value} {prefix}s')
    
def format_voltage(value: float, precision: int = 5) -> str:
    if value is None:
        return "N/A"
    return si_format(value, precision, u'{value} {prefix}V')

def format_current(value: float, precision: int = 5) -> str:
    if value is None:
        return "N/A"
    return si_format(value, precision, u'{value} {prefix}A')

def clean_terminal() -> None:
    """
    Cleans terminal window
    """
    print("\033[2J\033[1;1H", end='')
    #os.system('cls')
    #print(chr(27) + "[2J")

def report_NI(repeat_delay: float|None = 1, report_non_ni_instr = False):
    v_stats = {}
    i_stats = {}

    def get_row(rail: str, ni: Source_Port) -> list:
        if ni is None:
            empty = ["OFF"] * 11
            empty[0] = rail
            return empty

        stat_key = rail
        v_stats.setdefault(stat_key, [])
        i_stats.setdefault(stat_key, [])

        v_now = ni.get_voltage()
        i_now = ni.get_current()
        v_stats[stat_key].append(v_now)
        i_stats[stat_key].append(i_now)

        if ni.nominal_voltage is not None:
            nominal_val = format_voltage(ni.nominal_voltage, 4)
        else:
            nominal_val = format_current(ni.nominal_current, 4)

        return [
            rail,
            format_voltage(v_now, 4),
            format_current(i_now, 4),
            nominal_val,
            format_current(ni.current_limit, 4),
            format_voltage(min(v_stats[stat_key]), 2),
            format_voltage(mean(v_stats[stat_key]), 2),
            format_voltage(max(v_stats[stat_key]), 2),
            format_current(min(i_stats[stat_key]), 2),
            format_current(mean(i_stats[stat_key]), 2),
            format_current(max(i_stats[stat_key]), 2)
        ]

    def add_rails(pt: PrettyTable, ports: dict) -> None:
        rails_count = len(ports)
        row_counter = 0
        for rail, ni in ports.items():
            if report_non_ni_instr or type(ni.instrument) == NIDCPowerInstrument:
                row_counter += 1
                pt.add_row(get_row(rail, ni), divider=True if row_counter == rails_count else False)

    def tabulate_all_rails() -> PrettyTable:
        pt = PrettyTable()
        pt.field_names = ["Rail", "V now", "I now", "Setpoint", "I limit", "V min", "V avg", "V max", "I min", "I avg", "I max"]
        pt.align = 'r'
        add_rails(pt, V_PORT)
        add_rails(pt, I_PORT)
        return pt


    if repeat_delay is None:
        print(tabulate_all_rails())
        return

    try:
        while True:
            pt = tabulate_all_rails() # this takes a second
            clean_terminal()
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"NI PSU Status at {now}\n")
            print(pt)
            print(f"Redrawing in {repeat_delay}s (Ctrl+C to stop)")
            if not report_non_ni_instr:
                print("NOTE: Non-NI source ports are excluded from the monitor by default. Use 'ni_mon -a' to include")
            time.sleep(repeat_delay)

    except KeyboardInterrupt:
        clean_terminal()
        print(tabulate_all_rails())

#Updates the voltage limit of all Isources.
def update_all_Vlimit(new_voltage_limit):
    for key in I_PORT.keys():
        I_PORT[key].update_voltage_limit(new_voltage_limit)

## HELPER FUNCTIONS ##

# Simple check that all filenames given are valid.
# Args:
#   - list_of_filenames = EWISOTT
#   - requestor = Name of the file where these filenames are used. Used only
#                 for printing out a helpful warning.
def filepath_lint(list_of_filenames, requestor=None):
    for filename in list_of_filenames:
        if not os.path.isfile(filename):
            if requestor is None:
                print("(WARNING)",filename,"does not exist!")
            else:
                print("(WARNING)",filename,"used in",requestor,"does not exist!")

def reserve_dated_file(contents_desc: str, extension: str = 'csv', directory: str | None = 'output', fmode: str = 'w') -> str:
    time = datetime.now().strftime("%Y-%m-%d_%a_%H-%M-%S")
    contents_desc = '_'.join(contents_desc.split())
    file = f"{time}_{contents_desc}.{extension}"

    if directory is not None:
        directory = directory.rstrip('/')
        os.makedirs(directory, exist_ok=True)
        file = f"{directory}/{file}"

    with open(file, 'w') as fhandle:
        os.utime(file)
        fhandle.close()

    return file

def bitstring_avg(bitstring):

    avg = 0
    sg.log.debug(bitstring)
    for i in range(len(bitstring)):
        if bitstring[i]=="1":
            avg = avg + 1.0/len(bitstring)

    sg.log.debug(avg)
    return round(avg,2)

def liststring_avg_stdev(liststring):
    myList = [int(x.strip()) for x in liststring.split()]
    return (np.mean(myList), np.std(myList))


def binned_histogram(result_list, bin_size) -> dict[float, int]:
    minimum = min(result_list)
    minimum_bin = round(minimum / bin_size) * bin_size
    maximum = max(result_list)
    maximum_bin = (round(maximum / bin_size) +1)* bin_size

    nr_bins = int(round(((maximum_bin - minimum_bin) / bin_size)))

    histo = {}

    for n in range(nr_bins):
        this_bin = minimum_bin + n*bin_size
        histo[this_bin] = 0
        for item in result_list:
            if item >= this_bin and item < this_bin + bin_size:
                histo[this_bin] = histo[this_bin] + 1

    return histo


def liststring_histogram(liststring) -> dict[int, int]:
    """
    Groups a given list of numbers into a frequency-sorted list.
    Produces a list of "bins" and "counts". The "bins" is a collection of unique numbers, with "counts" being a list
    of frequencies for numbers with indexes corresponding to "bins". Bins are presented as keys in the dictionary, where
    counts are presented as values.

    Example:
        Input:   1     2     3 1 1 1 2
        Output: {1: 4, 2: 2, 3:1}

    :param liststring: A whitespace-separated string of numbers
    :return: Dictionary where keys are bins, and values are count of a given bin
    """
    myList = [int(x.strip()) for x in liststring.split()]
    result = {}

    for value in myList:
        if value in result.keys():
            result[value] += 1
        else:
            result[value] = 1

    return result

def progress_pct(completed, total):
    return str(round(completed/total*100,1))+"%"

## MAIN EVALUATION FUNCTIONS ##

# find_DNL returns the mid-point DNL of the CDAC transfer function for the presently set CapTrim value.
def find_DNL(Vtest_min_mV = 495, Vtest_max_mV = 505,increment_uV = 100, logfile=None):

     #Generate a range w/ steps of 0.1mV
    cdac_codes = ["0111111111","1000000000","1000000001"]
    avg_response = [[],[],[]]
    Vtest_sweep = [round(x*0.1,1) for x in range(10*Vtest_min_mV,10*Vtest_max_mV,int(increment_uV/100))]
    Vtrip = [0,0,0]

    #config_AWG_as_DC(0)

    for c in range(len(cdac_codes)):

        config_AWG_as_DC(Vtest_sweep[0])

        if logfile is not None:
            logfile.write("Finding trip pt for "+cdac_codes[c]+"\n")
        #log.debug("Finding trip pt for "+cdac_codes[c])
        for v in Vtest_sweep:
            set_Vin_mV(v)

            if logfile is not None:
                logfile.write(str(v)+": ")
            sg.log.debug(v)

            #Run the command to send the CDAC pattern 100 times.
            #x = time.perf_counter_ns()
            r = command_ng(sg.log, sg.port, "cdac100x:"+cdac_codes[c])
            #print(time.perf_counter_ns()-x)
            #Format the response
            r = r.replace("cdac100x:"+cdac_codes[c],"").replace("?","").strip()

            if logfile is not None:
                logfile.write(r+"\n")

            #Find the average value and append it to the appropriate list.
            avg_response[c].append(bitstring_avg(r))


    #Print the output for verification.
    for v in range(len(Vtest_sweep)):
        print(Vtest_sweep[v], end=' ')
        for c in range(len(cdac_codes)):
            print(avg_response[c][v],end=' ')
            if avg_response[c][v]<0.5 and (v+1==len(Vtest_sweep) or avg_response[c][v+1] > 0.5):
                Vtrip[c] = Vtest_sweep[v]
        print("")

    print("Vtrip points are:",Vtrip)
    DNL = (Vtrip[2]-Vtrip[1])-(Vtrip[1]-Vtrip[0])
    print("DNL is ",DNL)

    return DNL



#sweep_Vin - Sweeps Vin across the specified range, taking 100 measurements at each point.
#            The avg and stdev for each Vin value are printed to file.
def Vin_sweep(Vtest_min_mV: int = 0, Vtest_max_mV: int = 10, increment_uV: int = 100 ):

    filename = reserve_dated_file(f"Vin sweep {Vtest_min_mV}mV to {Vtest_max_mV}mV by {increment_uV}", directory="output/sweep")

    print("Writing Vtest Sweep to "+filename)

    Vtest_sweep = [round(x*0.1,1) for x in range(10*Vtest_min_mV,10*Vtest_max_mV,int(increment_uV/100))]


    config_AWG_as_DC(Vtest_sweep[0])

    with open(filename, 'wb') as write_file: #Overwrites the file if it exists.
        write_file.write(b'Vtest,Avg Response[codes],Std Dev[codes]\n')

        if PROGRESS:
            print("[",end="")

        for v in range(len(Vtest_sweep)):
            set_Vin_mV(Vtest_sweep[v])
            #sg.log.debug(Vtest_sweep[v])

            if PROGRESS and v % (len(Vtest_sweep)/20)==0:
                print("|",end="")

            r = command_ng(sg.log, sg.port, "conv100x")

            #Format the response
            r = r.replace("conv100x","").replace("?","").strip()

            x = liststring_avg_stdev(r)

            write_file.write((str(Vtest_sweep[v])+","+str(x[0])+","+str(x[1])+"\n").encode())

    if PROGRESS:
        print("]")


def Vin_sweep_full_chain(Vtest_min_mV: int = 10, Vtest_max_mV: int = 100, increment_uV: int = 10000):


    if Vtest_min_mV <= 2:
        sg.log.error("In full-channel mode, step voltage must be > 2 mV")
        return
        
    filename = reserve_dated_file(f"Vin sweep FULL {Vtest_min_mV}mV to {Vtest_max_mV}mV by {increment_uV}", directory="output/sweep")
    print("Writing full-chain Vtest Sweep to "+filename)
    
    Vtest_sweep = [round(x*0.1,1) for x in range(10*Vtest_min_mV,10*Vtest_max_mV,int(increment_uV/100))]
    config_AWG_as_Pulse(Vtest_sweep[0], 1.27)

    with open(filename, 'wb') as write_file: #Overwrites the file if it exists.
        write_file.write(b'Vtest,Avg Response[codes],Std Dev[codes]\n')
        
        for v in range(len(Vtest_sweep)):
            set_pulse_mag(Vtest_sweep[v])
            r = command_ng(sg.log, sg.port, "samp100x")
            r = r.replace("samp100x","").replace("?","").strip()

            x = liststring_avg_stdev(r)

            write_file.write((str(Vtest_sweep[v])+","+str(x[0])+","+str(x[1])+"\n").encode())



def Vin_histogram(Vtest_mV: int, points: int) -> dict[int, int]:
    """
    Sets Vin and takes a specified number of points, returning a histogram of the resulting output codes.

    :param Vtest_mV: Voltage to test at in milli-volts
    :param points: Number of samples to take
    :return: See "liststring_histogram()" docblcok
    """

    config_AWG_as_DC(Vtest_mV)

    if TARGET == "SPROCKET1":
        #r = command(sg.port, "convNx:"+str(points), printresponse=False, timeout_s=10)
        r = command_ng(sg.log, sg.port, f"convNx:{points}")

        #log.debug(f"convNx returned: {r}") # this will return A LOT of lines!
        sg.log.debug(f"Number of values returned: {len(r.split())}")

        #Format the response
        liststring = r.replace("convNx:"+str(points),"").replace("?","").strip()

        return liststring_histogram(liststring)

        


def center_code(Vtest_init_mV: float, samples_per_val: int = 1000):


    Vtest = Vtest_init_mV
    Vtest_last = Vtest_init_mV

    count_outside = 1000

    sg.log.info(f"Running centering code from {Vtest_init_mV}mV...")

    while True:
        histogram = Vin_histogram(Vtest, samples_per_val)
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

def dump_noise_sweep_histogram(Vtest_sweep, vtest_min_mv: int, vtest_max_mv: int, histograms: dict) -> bool:
    try:
        filename = reserve_dated_file(f"vin noise sweep HISTO {vtest_min_mv}mV to {vtest_max_mv}mV step{Vtest_sweep[1]-Vtest_sweep[0]}mV", directory='output/noise')
        sg.log.debug(f"Writing histograms for Vin Noise Sweep to file \"{filename}\"")
        with open(filename, 'w', newline='') as file:
            cw = csv.DictWriter(file, fieldnames=['v_test', 'bin', 'count_in_bin'])
            cw.writeheader()

            for Vtest in Vtest_sweep:
                histogram = histograms[Vtest]
                print(histogram)
                for bin_val, bin_count in histogram.items():
                    cw.writerow({
                        'v_test': Vtest,
                        'bin': bin_val,
                        'count_in_bin': bin_count
                    })
            file.close()

        sg.log.notice(f"Histograms for Vin Noise Sweep saved to \"{filename}\"")
        return True

    except Exception as e:
        sg.log.error(f"Noise sweep failed due to {type(e).__name__}: {e}")
        return False

def dump_noise_sweep_stats(Vtest_sweep, vtest_min_mv: int, vtest_max_mv: int, histograms: dict) -> bool:
    try:
        filename = reserve_dated_file(f"vin noise sweep STATS {vtest_min_mv}mV to {vtest_max_mv}mV step{Vtest_sweep[1]-Vtest_sweep[0]}mV", directory='output/noise')
        sg.log.debug(f"Writing stats for Vin Noise Sweep to file \"{filename}\"")
        with open(filename, 'w', newline='') as file:
            cw = csv.DictWriter(file, fieldnames=['v_test', 'count_main_bin', 'count_outside_bin', 'z_score', 'rms_noise_in_lsb'])
            cw.writeheader()

            for Vtest in Vtest_sweep:
                row = {}
                histogram = histograms[Vtest]
                print(histogram)
                main_bin = max(histogram, key=histogram.get) # bin that has the most most counts
                row['v_test'] = Vtest
                row['count_main_bin'] = histogram[main_bin] # how many counts in the "most popular" bin
                row['count_outside_bin'] = sum(histogram.values()) - row['count_main_bin'] # counts outside of the main bin

                if row['count_outside_bin'] == 0:
                    sg.log.warning(f"Count_outside_bin is 0 for {Vtest}mV")
                    row['z_score'] = 1e99
                    row['rms_noise_in_lsb'] = 0
                else:
                    row['z_score'] = NormalDist().inv_cdf(1 - ((row['count_outside_bin'] / (row['count_outside_bin']+row['count_main_bin']))/2))
                    row['rms_noise_in_lsb'] = 0.5 / row['z_score']
                cw.writerow(row)
            file.close()

        sg.log.notice(f"Histograms for Vin Noise Sweep stats saved to \"{filename}\"")
        return True

    except Exception as e:
        sg.log.error(f"Noise sweep failed due to {type(e).__name__}: {e}")
        return False


def Vin_noise_sweep(vtest_min_mv: int = 0, vtest_max_mv: int = 10, step_mv: int = 1, samples_per_pt: int = 1000000) -> bool:
#    if vtest_max_mv-vtest_min_mv < 10:
#       sg.log.error("Noise requires at least 10mV of a difference between min and max")
#        return
    if vtest_min_mv >= vtest_max_mv:
        sg.log.error("Noise sweep requires min < max")
        return
    if step_mv < 1 or step_mv > (vtest_max_mv - vtest_min_mv):
        sg.log.error("Noise sweep requires step to be >=1 and between min and max")
        return

    #Vtest_sweep = [x for x in range(vtest_min_mv, vtest_max_mv, int((vtest_max_mv - vtest_min_mv) / 10))]
    Vtest_sweep = [x for x in range(vtest_min_mv, vtest_max_mv, step_mv)]

    histograms = {}
    for Vtest in Vtest_sweep:
        sg.log.info(f"Generating histogram for VTest={Vtest:.2f}mV with {samples_per_pt} samples/pt")
        histograms[Vtest] = Vin_histogram(center_code(Vtest), samples_per_pt)

    dump_noise_sweep_histogram(Vtest_sweep, vtest_min_mv, vtest_max_mv, histograms)
    dump_noise_sweep_stats(Vtest_sweep, vtest_min_mv, vtest_max_mv, histograms)


    sg.log.notice(f"Noise sweep finished")
    return True

def check_dependencies(dependency_list):
    return_val = True
    for entry in dependency_list:
        if type(entry)==str:
            if not eval(entry):
                print("ERR: Must have "+entry)
                return_val = False
        else:
            at_least_one = False
            for subentry in entry:
                if eval(subentry):
                    at_least_one=True
            if not at_least_one:
                print("ERR: Must have at least one of "+str(entry))
                return_val = False

    return return_val





def RunFPGAPatternInteractive():

    print("STEP 1/5: Please enter the name of the FPGA resource to use. (This should be something like \"PXI1Slot5\")")
    fpga_slot = input("fpga_resource:")
    print("STEP 2/5: Please choose a Glue bitfile to load onto the FPGA. (This should end in \".lvbitx\")")
    input("Press enter to open file finder...")
    glue_bitfile = filedialog.askopenfilename()

    
    print("STEP 3/5: Please choose a .iospec file.")
    input("Press enter to open file finder...")
    iospec = filedialog.askopenfilename()

    print("STEP 4/5: Please choose an input file (.vcd or .glue)")
    input("Press enter to open file finder...")
    input_file = filedialog.askopenfilename()

    if ".glue" not in input_file:
        print("I detected that the file you input was a VCD. I'll convert it to a Glue file!")
        print("What strobe period (in nanoseconds) would you like to use for the Glue file? (Enter '?' for more info)")
        strobe_input = input("strobe_ns:")
        if '?' in strobe_input:
            print("The strobe period is how frequently the VCD waveforms will be sampled to generate Glue waveforms.")
            print("This is highly dependent on the digital design. For example, if you have a 10 MHz clock (100 ns")
            print("period), then you probably want a strobe of no larger than 50 ns.")
            print("Note that strobe does not affect the rate of Glue waveforms -- Glue waveforms are always output at")
            print("a rate determined by the FPGA clock speed, typically 40 MHz or 200 MHz. If you want your pattern to")
            print("be played in 'real time', select strobe = 1/(freq_fpga_clock). However, sometimes arbitrary clock")
            print("speeds can be used in Xcelium simulations, so double-check with the digital designer to be sure!")
            strobe_input = input("strobe_ns:")

        strobe_ps = 1000*float(strobe_input.strip())

        gc = GlueConverter(iospec)
        gc.VCD2Glue(input_file, strobe_ps, "temp")
        input_file = "temp_se_io.glue"

    print("STEP 5/5: What should the output file be called? (Press enter to use the default name, \"asic_output\")")
    output_file  = input("output_file:").strip()
    if len(output_file) < 2:
        output_file = "asic_output"

    print("~ Thank you! ~")
    input("Press enter to run the pattern...")

    RunFPGAPattern(fpga_slot, glue_bitfile, iospec, input_file, output_file)

def RunFPGAPattern(fpga_slot, glue_bitfile, iospec, input_glue, output_file):

    #Use GlueConverter to try to determine which FPGA should be booted from the iospec.

    #Set up classes

    
    #fpga = NiFpga(sg.log, fpga_slot)
    #fpga.start(glue_bitfile)

    #dbg = NiFpgaDebugger(sg.log, fpga)
    #dbg.configure(GLUEFPGA_DEFAULT_CFG)

    tp = PatternRunner(sg.log,DEFAULT_IOSPEC)
    


    #NOTE: FPGA Needs > 2 seconds of delay in between setup and running the first test pattern!
    time.sleep(3)

    print("Running FPGA Pattern!!!")
    
    tp.run_pattern(input_glue, outfile_tag=output_file)



## TEST ROUTINES



# Lists serial ports available in the system
def list_serial_ports():
    ports = serial.tools.list_ports.comports()
    print(f"\nThere are {len(ports)} port(s):")

    for port, name, hwid in sorted(ports):
        print(f" {port}: {name}")
    print("---")

## ARDUINO SETUP ##
def initialize_Arduino(interactive: bool = True):
    """
    Initializes connection to the Arudino HAL

    :param interactive: Whether to ask questions about settings (True), or assume defaults (False)
    """
    if sg.ARDUINO_CONNECTED:
        sg.log.warning("HAL already initialized; reinitializing")
        deinitialize_Arduino()


    while True:
        if interactive:
            SERIAL_PORT = input(f"PORT? (Hit enter for {DEFAULT_SERIAL_PORT}, ? for list) >>>")

            if SERIAL_PORT == "":
                SERIAL_PORT = DEFAULT_SERIAL_PORT
            elif SERIAL_PORT == "?":
                list_serial_ports()
                continue

            BAUD = input(f"BAUD? (Hit enter for {DEFAULT_BAUD}) >>>")

            if BAUD == "":
                BAUD = DEFAULT_BAUD
        else:
            SERIAL_PORT = DEFAULT_SERIAL_PORT
            BAUD = DEFAULT_BAUD

        sg.log.info(f"Connecting to HAL on {SERIAL_PORT}@{BAUD}")
        sg.port = open_port(SERIAL_PORT, BAUD)
        if sg.port != -1:
            print("Port opened successfully :)")
            break

        if interactive:
            sg.log.error(f"Port openning failed! Try again.")
        else:
            sg.log.warning(f"Port openning failed - falling back to interactive mode")
            interactive = True

    #Initialize communication.
    sg.log.debug("Handshaking with Arduino...")

    #Handshake function will not return unless handshake is successful.
    command_ng(sg.log, sg.port, "echo:off")
    handshake_with_arduino_ng(sg.log, sg.port)
    sg.log.info(f"HAL ID: {command_ng(sg.log, sg.port, 'IDN?')}")

    sg.ARDUINO_CONNECTED = True
    sg.log.notice("Arduino HAL connected & initialized")
    return sg.port

def deinitialize_Arduino() -> None:
    if sg.port is None:
        return

    sg.log.blocking('Deinitializing HAL')
    sg.port.close()
    sg.ARDUINO_CONNECTED = False
    sg.log.block_res() # todo: this probably should check port status

## NI SETUP ##

#Fields that must be present for a given instrument type.
instr_type_required_fields = {"NIDCPower" : ["slot"],
                              "Oscilloscope" : ["io"],
                              "AWG"          : ["io"],
                              "Supply"       : ["io"],
                              "Caribou"    : ["host","port","device"]}
                         
   
#Fields that must be present to use a given type of io.   
io_required_fields = {"VISA" : ["resource"],
                      "Prologix" : ["ipaddr", "gpibaddr"]}


#Lint checker for INSTR library.
#Returns: The # of non-NI instruments that need to be initialized, or -1 if there is an error.
def INSTR_lint():

    #non_ni_instruments = []

    for instr in INSTR.keys():
        this_type = INSTR[instr]["type"]
        if this_type not in instr_type_required_fields.keys():
            sg.log.error(f"INSTR Error: {instr} is {this_type} which is not a valid instrument type. Valid instrument types are: {instr_type_required_fileds.keys()}.")
            return -1
        
        for field in instr_type_required_fields[this_type]:
            
            if field not in INSTR[instr].keys():
                sg.log.error(f"INSTR Error: Instruments of type {this_type} must have field {field} which is not present for {instr}.")
                return -1
                
        if "io" in INSTR[instr].keys():
            this_io = INSTR[instr]["io"]
            
            if this_io not in io_required_fields.keys():
                sg.log.error(f"INSTR Error: Instrument {instr} uses io type {this_io} which is not recognized. Recognized io types are {io_required_fields.keys()}")
                return -1
            
            for field in io_required_fields[this_io]:
                if field not in INSTR[instr].keys():
                    sg.log.error(f"INSTR Error: Instruments using io type {this_io} must have field {field} which is not present for {instr}.")
                    return -1
                
                
        #if INSTR[instr]["type"] != "NIDCPower":
        #    non_ni_instruments.append(instr)
                
    sg.log.debug("INSTR lint check completed successfully.")
    
    num_instr = len(INSTR.keys())
    if num_instr > 0:
        sg.log.info(f"{TARGET_CONFIG_PY} specifies {num_instr} instruments that need to be initialized: {list(INSTR.keys())}")
    return num_instr


#Lint checker for voltage and current dictionaries.
# Rules for lint check:
# (1) All rails that are in the V_PORT or I_PORT dictionary must be initialized.
# (2) All rails which are initialized must have an entry for _INSTR, _CHAN, and _LEVEL 
def rail_lint():


    for rail in V_PORT.keys():
        if rail not in V_SEQUENCE:
            sg.log.error("CONFIG ERROR: All voltage / current rails defined in MyASIC_Config.py must be included in the initialization sequence\n"+
                         "(V_SEQUENCE or I_SEQUENCE). If you want to dynamically initialize a rail, you can do so from within MyASIC_Routines.py.\n"+
                         f"({rail} is missing from V_SEQUENCE).")
            return -1
            
    for rail in V_SEQUENCE:
        if rail not in V_INSTR.keys():
            sg.log.error(f"CONFIG ERROR: {rail} must have an entry in V_INSTR which specifies the INSTR this rail is supplied by.")
            return -1
        if rail not in V_CHAN.keys():
            sg.log.error(f"CONFIG ERROR: {rail} must have an entry in V_CHAN which specifies the instrument channel this rail is supplied by.")
            return -1
        if rail not in V_LEVEL.keys():
            sg.log.error(f"CONFIG ERROR: {rail} must have an entry in V_LEVEL which specifies the voltage setting (in volts) for this rail.")
            return -1


    for rail in I_PORT.keys():
        if rail not in I_SEQUENCE:
            sg.log.error("CONFIG ERROR: All voltage / current rails defined in MyASIC_Config.py must be included in the initialization sequence\n"+
                         "(V_SEQUENCE or I_SEQUENCE). If you want to dynamically initialize a rail, you can do so from within MyASIC_Routines.py.\n"+
                         f"({rail} is missing from I_SEQUENCE).")
            return -1
            

    for rail in I_SEQUENCE:
        if rail not in I_INSTR.keys():
            sg.log.error(f"CONFIG ERROR: {rail} must have an entry in I_INSTR which specifies the INSTR this rail is supplied by.")
            return -1
        if rail not in I_CHAN.keys():
            sg.log.error(f"CONFIG ERROR: {rail} must have an entry in I_CHAN which specifies the instrument channel this rail is supplied by.")
            return -1
        if rail not in I_LEVEL.keys():
            sg.log.error(f"CONFIG ERROR: {rail} must have an entry in I_LEVEL which specifies the current setting (in amps) for this rail.")
            return -1


            

def initialize_INSTR(interactive: bool = False):

    for instr in INSTR.keys():
    
        #If io setup is necessary, do that first.
        if "io" in INSTR[instr].keys():
            if INSTR[instr]["io"] == "VISA":
                io = initialize_VISA(INSTR[instr], interactive)
            elif INSTR[instr]["io"] == "Prologix":
                io = initialize_Prologix(INSTR[instr], interactive)
                
                
            if io == None:
                sg.log.warning(f"No I/O initialized, we will SKIP initializing {INSTR[instr]['type']}")
                continue
    
        #Next perform setup for the actual instrument.
        if INSTR[instr]["type"] == "AWG":
            print(io.inst)
            sg.INSTR[instr] = initialize_AWG(INSTR[instr], io)
            
        elif INSTR[instr]["type"] == "Oscilloscope":
            print(io.inst)
            sg.INSTR[instr] = Oscilloscope(sg.log,io)
            
            
        elif INSTR[instr]["type"] == "Supply":
            sg.INSTR[instr] = Supply(sg.log,io)
                  
            
        elif INSTR[instr]["type"] == "NIDCPower":
            sg.log.blocking(f"Initializing NI INSTR \"{instr}\"")
            sg.INSTR[instr] = NIDCPowerInstrument(INSTR[instr]["slot"])
            sg.log.block_res()

        elif INSTR[instr]["type"] == "Caribou":
            sg.INSTR[instr] = Caribou(INSTR[instr]["host"], INSTR[instr]["port"], INSTR[instr]["device"], sg.log)


        #Support the assigning of aliases.
        if "alias" in INSTR[instr].keys():
            globals()[INSTR[instr]["alias"]] = sg.INSTR[instr]
            
        sg.log.notice(f"{INSTR[instr]['type']} {instr} successfully initialized!")
        
        
def deinitialize_INSTR():
    for instr in INSTR.keys():
        
        if INSTR[instr]["type"] == "NIDCPower":
            try:
                sg.log.blocking(f"Deinitializing NI INSTR \"{instr}\"")
                sg.INSTR[instr].deinit()
                sg.log.block_res()
            except KeyError:
                sg.log.debug(f"{instr} was never initialized in the first place, skipping...")
            except Exception as e:
                sg.log.block_res(False)
                sg.log.error(f"Failed to deinitialize NI \"{instr}\": {str(e)}")
                pass # we cannot throw here - other things must de-init regardless
    
        elif INSTR[instr]["type"] == "AWG":
            try:
                sg.log.blocking(f"Setting AWG \"{instr}\" output to \"OFF\"")
                sg.INSTR[instr].set_output(False)
                sg.log.block_res()
            except KeyError:
                sg.log.debug(f"{instr} was never initialized in the first place, skipping...")
                
        elif INSTR[instr]["type"] == "Supply":
            try:
                sg.log.blocking(f"Setting Bench Supply \"{instr}\" output to \"OFF\"")
                sg.INSTR[instr].set_output_off()
                sg.log.block_res()
            except KeyError:
                sg.log.debug(f"{instr} was never initialized in the first place, skipping...")
    
        #For any instruments that use Prologix, deinitialize that:
        if "io" in INSTR[instr].keys() and INSTR[instr]["io"] == "Prologix":
            try:
                sg.log.blocking(f"Disconnecting from Prologix Instrument instr \"{instr}\"")
                sg.INSTR[instr].io.disconnect()
                sg.log.block_res()
            except KeyError:
                sg.log.debug(f"{instr} was never initialized in the first place, skipping...")

#Set up a VISA connection, interactively if requested.
def initialize_VISA(cfg, interactive = False):
    chosen_resource = None
    DEFAULT_RESOURCE = cfg["resource"]
    
    if interactive:
        while True:
            rm = pyvisa.ResourceManager()
            resources = rm.list_resources()

            print("Available resources:")
            for i in range(len(resources)):
                print(f"{i}. {resources[i]}")

            try:
                user_in = input(f"Which resource should be used for {cfg['type']} (Press Enter to use {DEFAULT_RESOURCE}, 'n' to skip)? ")
                if user_in.strip() == 'n':
                    return None
                resource_idx = int(user_in)
                chosen_resource = resources[resource_idx]
                break
            except ValueError:
                if user_in == "":
                    break
                else:
                    print("Could not parse \""+str(user_in)+"\", try again...")
        
        

    if chosen_resource is None:
        chosen_resource = DEFAULT_RESOURCE

    return VISAInterface(sg.log, chosen_resource)

#Set up a Prologix connection, interactively if requested.
def initialize_Prologix(cfg, interactive = False):
    
    DEFAULT_PROLOGIX_IPADDR = cfg["ipaddr"]
    DEFAULT_DEVICE_GPIBADDR = cfg["gpibaddr"]

    connected = False
    while True:
        if interactive:
            PROLOGIX_IPADDR = input(f"IP ADDRESS? (Hit enter to use \"{DEFAULT_PROLOGIX_IPADDR}\") >>>")

            if PROLOGIX_IPADDR == "":
                PROLOGIX_IPADDR = DEFAULT_PROLOGIX_IPADDR

            DEVICE_GPIBADDR = input(f"GPIB ADDRESS? (Hit enter to use \"{DEFAULT_DEVICE_GPIBADDR}\") >>>")

            if DEVICE_GPIBADDR == "":
                DEVICE_GPIBADDR = DEFAULT_DEVICE_GPIBADDR
        else:
            PROLOGIX_IPADDR = DEFAULT_PROLOGIX_IPADDR
            DEVICE_GPIBADDR = DEFAULT_DEVICE_GPIBADDR

        sg.log.info(f"Connecting to Device @ GPIB#{DEVICE_GPIBADDR} via IP:{PROLOGIX_IPADDR}")
        
        prologix_interface = PrologixInterface(sg.log, PROLOGIX_IPADDR, DEVICE_GPIBADDR)
        
        # Connection succesful
        if prologix_interface.is_connected():
            sg.log.info("Prologix interface successfully connected...")
            break

        prologix_interface = None
        
        if interactive:
            sg.log.error(f"Prologix connection failed! Try again.")
        else:
            sg.log.warning(f"Prologix connection failed - falling back to interactive mode")
            interactive = True
            
    return prologix_interface


def initialize_NIFPGA():
    try:
        DEFAULT_IOSPEC
        DEFAULT_FPGA_BITFILE_MAP
        setup_pr = True
    except NameError:
        sg.log.info("Could not automatically initialize Glue Converter + Pattern Runner. Make sure DEFAULT_IOSPEC and DEFAULT_FPGA_BITFILE_MAP are defined in MyASIC_Config.py")
        setup_pr = False
        
    if setup_pr:
        sg.log.debug("Initializing PatternRunner...")
        sg.pr = PatternRunner(sg.log, DEFAULT_IOSPEC, DEFAULT_FPGA_BITFILE_MAP)
        sg.log.debug("Initializing GlueConverter...")
        sg.gc = GlueConverter(DEFAULT_IOSPEC)
        time.sleep(2)


# todo: Some of the logs here about initing sources can probably be moved to generic_nidcpower
def initialize_Rails():
    global V_SEQUENCE, I_SEQUENCE, V_PORT, I_PORT

    try:
        V_SEQUENCE
    except NameError:
        sg.log.info("V_SEQUENCE not defined in Config. No Vsources will be initialized.")
        V_SEQUENCE = None
        V_PORT = {}

    try:
        I_SEQUENCE
    except NameError:
        sg.log.info("I_SEQUENCE not defined in Config. No Isources will be initialized.")
        I_SEQUENCE = None
        I_PORT = {}


    sg.log.debug("NI INSTR init")
    try:

        if V_SEQUENCE is not None:
            sg.log.debug("NI Vsource init")
            for Vsource in V_SEQUENCE:
                #time.sleep(0.5)
                sg.log.blocking(f"Initializing Vsource \"{Vsource}\" @ {V_INSTR[Vsource]}#{V_CHAN[Vsource]} to {V_LEVEL[Vsource]}V (IMax={V_CURR_LIMIT[Vsource]:.4f})")
                
                if type(V_CURR_LIMIT) == dict:
                    curr_limit = V_CURR_LIMIT[Vsource]
                else:
                    curr_limit = V_CURR_LIMIT
                
                V_PORT[Vsource] = Source_Port(sg.INSTR[V_INSTR[Vsource]], V_CHAN[Vsource],default_current_limit=curr_limit)
                V_PORT[Vsource].set_voltage(V_LEVEL[Vsource])
                V_PORT[Vsource].set_output_on()
                sg.log.block_res()
            
            sg.log.debug("NI Vsource init done")
        
            

        if I_SEQUENCE is not None:
            sg.log.debug("NI Isource init")
            for Isource in I_SEQUENCE:
                sg.log.blocking(f"Initializing Isource \"{Isource}\" @ {I_INSTR[Isource]}#{I_CHAN[Isource]} to {I_LEVEL[Isource]:.6f}")
                
                if type(I_VOLT_LIMIT) == dict:
                    volt_limit = I_VOLT_LIMIT[Isource]
                else:
                    volt_limit = I_VOLT_LIMIT
                    
                I_PORT[Isource] = Source_Port(sg.INSTR[I_INSTR[Isource]], I_CHAN[Isource],default_voltage_limit=volt_limit)
                I_PORT[Isource].set_current(I_LEVEL[Isource])
                I_PORT[Isource].set_output_on()
                sg.log.block_res()
            sg.log.debug("NI Isource init done")
        
            
    except Exception as e:
        sg.log.block_res(False)
        if isinstance(e, OSError) and hasattr(e, 'winerror') and e.winerror == -1066598273:
            sg.log.emerg("NI INSTR failed due to Windows error. Make sure you're NOT using Microsoft Store Python (see https://github.com/ni/nimi-python/issues/1904)")
        else:
            sg.log.emerg("NI INSTR failed (do you have \"NI-DCPower ver >=2022-Q4\" driver installed?)")
        raise

    sg.NI_CONNECTED = True
    sg.log.notice("NI PXI initialized")


#def cycle_NI():
#    deinitialize_NI()
#    initialize_NI()

#def deinitialize_NI() -> None:
#    for instr_name, session in INSTR.items():
#        if session is None:
#            sg.log.debug(f"Skipping NI {instr_name} deinit - not initialized")
#            continue
#
#        
#
#    sg.log.debug("NI deinit done")
#    sg.NI_CONNECTED = False

## sg.AWG SETUP ##

def initialize_AWG(instr_cfg, io) -> AgilentAWG:

    new_AWG = AgilentAWG(sg.log, io)

    new_AWG.send_line_awg("OUTP:LOAD INF") #sg.AWG will be driving a MOSFET gate; set to high impedance mode.
    #new_AWG.set_local_controls(True)
    new_AWG.display_text("Managed by Spacely")
    
    return new_AWG


        
# Given a dictionary of waves:
# {"signal1" : [0,1,1,1,0],
#  "signal2" : [0,0,0,0,1]}
#
# This function will generate a glue wave.
def genpattern_from_waves_dict(waves_dict):

    #2) Writing to an ASCII file.
    with open("genpattern.txt",'w') as write_file:
        for w in waves_dict.keys():
            write_file.write(w+":"+"".join([str(x) for x in waves_dict[w]])+"\n")
            
    #3) Convert ASCII file to Glue.
    gc = GlueConverter(DEFAULT_IOSPEC)

    gc.ascii2Glue("genpattern.txt", 1, "genpattern")


    return "genpattern_se_io.glue"







def logger_demo():
    sg.log.info("sg.log.info")
    sg.log.debug("sg.log.debug")
    sg.log.notice("sg.log.notice")
    sg.log.warning("sg.log.warning")
    sg.log.error("sg.log.error")
    sg.log.critical("sg.log.critical")
    sg.log.alert("sg.log.alert")
    sg.log.emerg("sg.log.emerg")

def auto_voltage_monitor():
    global V_SEQUENCE, I_SEQUENCE
    if sg.NI_CONNECTED:
        # Automatic Voltage Warning
        abnormal_rails = []
        abnormal_rail_voltages = []
        
        unmonitored_rails = []

        #print("(DBG) auto_voltage_monitor running")
        try:
            V_SEQUENCE
        except NameError:
            V_SEQUENCE = None

        try:
            I_SEQUENCE
        except NameError:
            I_SEQUENCE = None

        if V_SEQUENCE is not None:
            for Vsource in V_SEQUENCE:
                if Vsource in V_WARN_VOLTAGE.keys():
                    voltage = V_PORT[Vsource].get_voltage()
                    if voltage < V_WARN_VOLTAGE[Vsource][0] or voltage > V_WARN_VOLTAGE[Vsource][1]:
                        abnormal_rails.append(Vsource)
                        abnormal_rail_voltages.append(voltage)
                else:
                    unmonitored_rails.append(Vsource)


        if I_SEQUENCE is not None:
            for Isource in I_SEQUENCE:
                if Isource in I_WARN_VOLTAGE.keys():
                    voltage = I_PORT[Isource].get_voltage()
                    if voltage < I_WARN_VOLTAGE[Isource][0] or voltage > I_WARN_VOLTAGE[Isource][1]:
                        abnormal_rails.append(Isource)
                        abnormal_rail_voltages.append(voltage)
                else:
                    unmonitored_rails.append(Isource)


        if len(abnormal_rails) > 0:
            print("*** WARNING *** Abnormal voltage on: ",end='')
            for i in range(len(abnormal_rails)):
                print(abnormal_rails[i],"("+str(round(abnormal_rail_voltages[i],2))+"V) ",end='')

            print("")
        
        if len(unmonitored_rails) > 0:
            sg.log.debug(f"Unmonitored Rails: {unmonitored_rails}")
    

# merge_data_files() -- Merges 2 or more .csv data files by concatenating them horizontally. 
#  file_list -- List of filenames to concatenate. If it is empty, will prompt the user 
#               to select files using fd.askopenfilenames()
def merge_data_files(file_list=None, merged_name=None):

    if file_list == None:
        file_list = filedialog.askopenfilenames()
    
    if merged_name == None:
        merged_name = input("Name of merged file?")

    outfile_lines = [""]
    files_merged = 0
    total_cols_merged = 0
    
    for f in file_list:
        with open(f,'r') as read_file:
            lines = read_file.readlines()
        
        #Get the # of columns that this file has. It's the number of commas + 1
        #in the line with the most commas. 
        num_cols = max([x.count(",")+1 for x in lines])
        
        
        f_name = f.split("/")[-1].replace(",","-")
            
        sg.log.debug(f"Merging data file {f_name} which has {num_cols} columns")
        
        #The first row of the merged file is the name of the file we merged from.
        outfile_lines[0] = outfile_lines[0] + f_name+num_cols*","
        
        for i in range(len(lines)):
        
            this_line = lines[i].replace("\n",",")
        
            #Number of columns that should exist to the LEFT of this new file.
            cols_needed = total_cols_merged
            
            if len(outfile_lines) < i + 2:  
                outfile_lines.append(","*cols_needed+this_line)
                continue
                
            else:
                cols = outfile_lines[i+1].count(",")
                
                outfile_lines[i+1] = outfile_lines[i+1]+","*(cols_needed-cols)+this_line
            
            
        files_merged = files_merged + 1
        total_cols_merged = total_cols_merged + num_cols
        
        
    with open(merged_name+".csv",'w') as write_file:
        for line in outfile_lines:
            write_file.write(line+"\n")



## Experiments and Data Files (metadata logging) ##

class Experiment:
    
    def __init__(self, name, folders=[], initial_metadata={}):
        self.metadata = initial_metadata
        self.name = name
        self.base_path = os.sep.join(["output"]+folders+[name])
        
        
        sg.log.notice(f"Creating Experiment {name} at {self.base_path}")
        if not os.path.isdir(self.base_path):
            os.makedirs(self.base_path)
        
        
        self.data_files = []
 
    def new_data_file(self,df_name):
        self.data_files.append(DataFile(df_name,self))
        return self.data_files[-1]
 
    #Get a piece of experiment-level metadata
    def get(self,key, missing_ok=False, default=None):
        if key in self.metadata.keys():
            return self.metadata[key]
        else:
            if not missing_ok:
                sg.log.error(f"Could not find metadata {key}")
            return default
                
    #Set a piece of default experiment-level metadata
    def set(self,key, value):
        self.metadata[key] = value
        self.write_metadata()
 
    #Write all metadata in this experiment to file. (Should be done after updating metadata)       
    def write_metadata(self):
        metadata_file_name = os.sep.join([self.base_path,"meta.txt"])
        current_date = time.strftime("%Y_%m_%d")
        
        with open(metadata_file_name,"w") as write_file:
            currentTime = datetime.now().strftime("%Y-%m-%d_%a_%H-%M-%S")
            write_file.write("-----------------------------------\n")
            write_file.write(f"Metadata for Experiment {self.name}\n")
            write_file.write(f"Written at {currentTime}\n")
            write_file.write("-----------------------------------\n")
            write_file.write("Defaults:\n")
            
            for k in self.metadata.keys():
                write_file.write(f"{k} :: {self.metadata[k]}\n")
                
            write_file.write("\n\n")
            for df in self.data_files:
                write_file.write(f"\nDATA FILE:{df.name}\n")
                
                if len(df.metadata.keys()) < 1:
                    write_file.write("<default>\n")
                else:
                    for k in df.metadata.keys():
                        write_file.write(f"{k} :: {df.metadata[k]}\n")
                
        
        
        
# Class to represent a data file (i.e. xyz.csv) and all its associated metadata.    
# Will be saved under {Experiment_Directory}/{name}.csv    
class DataFile:

    def __init__(self,name,experiment):
        self.name = name
        self.e = experiment
        self.file_path = os.sep.join([self.e.base_path,f"{self.name}.csv"])
        self.file = open(self.file_path,"w")
        self.metadata = {}
       

    def get(self,key, missing_ok=False, default=None):
        #Prioritize returning metadata that's specific to this particular file.
        if key in self.metadata.keys():
            return self.metadata[key]
        else:
            return self.e.get(key, missing_ok, default)
        
    def set(self,key,value):
        self.metadata[key] = value
        self.e.write_metadata()
       
    def write(self,write_string):
        self.file.write(write_string)
        
    #Ensure file is closed when ref count drops to 0.
    def __del__(self):
        self.close()
    
    def close(self):
        self.file.close()
    
    #Check to make sure that all the items in to_check[] are actually valid metadata for this DF.
    def check(self,to_check):
        if type(to_check) == str:
            to_check = [to_check]
            
            
        for item in to_check:
            val = self.get(item)
            if val is None:
                print(val,item)
                return False
        
        return True


    


## DATA PROCESSING FUNCTIONS ##
#
# An analysis object can load data from multiple data files. It will carry out some analysis task on this data using its functions. 
#

ASHELL_HELPTEXT = """Supported Commands: 
df     --  Load a new data file
clear  -- clear loaded data files.

mean   --  Calculate mean from a freq table.
std    --  Calculate stddev from a freq table.

hist   --  Plot histograms from data.
mhist  --  Plot multi-histograms (>1 hist overlayed on same axes) from data.

outliers -- Remove outliers from histo data by specifying upper/lower bound.

"""


class Analysis():

    def __init__(self):

        #Each value in self.data is a dictionary, which contains the
        #headers and table values from a single data file. 
        self.data = {}
        #self.data_sources is a list of the data sources which are represented in self.data (as strings)
        self.data_sources = []



    # Loads data into the analysis from a DataFile object or CSV path.
    def load_df(self, df):

        if type(df) == str:
            file_path = df
        else:
            file_path = df.file_path


        sg.log.debug(f"Analysis: Loading DataFile from {file_path}...")
        
        #Flag to ensure that we only print one warning about missing columns.
        warned_missing_columns = False
        
        with open(file_path,"r") as read_file:
            lines = read_file.readlines()
            header = lines[0]
            header_tokens = [x.strip() for x in header.split(',')]
            
            raw_data = {}
            
            for tok in header_tokens:
                raw_data[tok] = []
            
            lines = lines[1:]
            for i in range(len(lines)):
                tokens = lines[i].split(',')
                
                cols = min(len(tokens), len(header_tokens))
                
                if len(tokens) != len(header_tokens) and not warned_missing_columns: 
                    sg.log.warning(f"Column count mismatch! Header has {len(header_tokens)} columns, but at least one row has {len(tokens)} columns. Only {cols} columns will be filled. \nFile path: {file_path}")
                    warned_missing_columns = True
                
               
                for j in range(cols):
                    try:
                        d = float(tokens[j])
                    except ValueError:
                        d = NaN
                        
                    raw_data[header_tokens[j]].append(d)
                    
                    

        file_name = file_path.split("/")[-1]

        self.data_sources.append(file_name)
        self.data[file_name] = raw_data
        

    #Loads data into the analysis object from a Python dictionary.
    def load_dict(self,my_dict, name=None):

        if name == None:
            n = 0
            name = f"Dict{n}"
            while name in self.data_sources:
                n = n + 1
                name = f"Dict{n}"

        sg.log.debug(f"Analysis: Loading {name}...")
        
        self.data[name] = my_dict
        self.data_sources.append(my_dict)

    def freq_avg(self,value_name, freq_name, source=None):
        """This function returns the average from data specified in a frequency table."""

        if source == None:
            if len(self.data_sources) == 1:
                source = self.data_sources[0]
            else:
                print("ERR: Must specify source for freq_avg")
                return None

        df = self.data[source]
        
        values = df[value_name]
        frequencies = df[freq_name]

        #Total # of counts = sum(frequencies)
        sumproduct = sum([values[i]*frequencies[i] for i in range(len(values))])
        n = sum(frequencies)
        

        return sumproduct/n
        
        
        
    def freq_median(self,value_name, freq_name, source=None):
        """This function returns the median from data specified in a frequency table."""

        if source == None:
            if len(self.data_sources) == 1:
                source = self.data_sources[0]
            else:
                print("ERR: Must specify source for freq_median")
                return None

        df = self.data[source]
        
        values = df[value_name]
        frequencies = df[freq_name]
        
        tmp = zip(values, frequencies)
        tmp.sort()
        values, frequencies = zip(*tmp)
        
        total_num = sum(frequencies)
        x = 0
        
        for i in range(len(values)):
            x = x + frequencies[i]
            if x > total_num/2:
                return values[i]
            elif x == total_num/2:
                return (values[i] + values[i+1])/2
        

    def freq_stddev(self,value_name, freq_name, source=None):
        """This function returns the standard deviation from data specified in a frequency table."""

        if source == None:
            if len(self.data_sources) == 1:
                source = self.data_sources[0]
            else:
                print("ERR: Must specify source for freq_avg")
                return None

        df = self.data[source]

        values = df[value_name]
        frequencies = df[freq_name]

        mean = self.freq_avg(value_name, freq_name, source)

        
        sum_squared_diffs = sum([frequencies[i]*(values[i]-mean)**2 for i in range(len(values))])

        #Divide by (n-1) for a sample standard deviation. We're never gonna have a population stddev in ASIC design.
        return np.sqrt(sum_squared_diffs / (sum(frequencies)-1))
    
    
    def exclude_outliers(self,x_key,y_key,source=None, bounds=[None,None]):
        """This function removes outliers from a histogram distribution that fall outside [lower,upper] bounds."""
        
        if source == None:
            if len(self.data_sources) == 1:
                source = self.data_sources[0]
            else:
                print("ERR: Must specify source for cancel_linear")
                return None

        df = self.data[source]
        
        bins = df[x_key]
        vals = df[y_key]
        
        removed_high_pts = 0
        removed_low_pts = 0
        
        for i in range(len(bins)):
            if bounds[0] is not None and bins[i] < bounds[0]:
                removed_low_pts = removed_low_pts + vals[i]
                vals[i] = 0
            if bounds[1] is not None and bins[i] > bounds[1]:
                removed_high_pts = removed_high_pts + vals[i]
                vals[i] = 0
        
        df[y_key] = vals
        sg.log.debug(f"Removed {removed_high_pts} points exceeding the upper bound and {removed_low_pts} points beneath the lower bound.")


    def cancel_linear(self, x_key, y_key, source=None, crop_pts = 0):
        """This function cancels the linear term from (x,y) data, which may make nonlinearity easier to analyze.
           crop_pts = # of points to crop from either side of the transfer function (may help with nonlinear bits at the end)
           """
        if source == None:
            if len(self.data_sources) == 1:
                source = self.data_sources[0]
            else:
                print("ERR: Must specify source for cancel_linear")
                return None

        df = self.data[source]
        
        x_vals = df[x_key]
        y_vals = df[y_key]
        
        if crop_pts > 0:
            y_vals = y_vals[crop_pts:len(y_vals)-crop_pts]
            x_vals = x_vals[crop_pts:len(x_vals)-crop_pts] 
        
        linear_term = [y_vals[0] + (i/len(y_vals))*(y_vals[-1]-y_vals[0]) for i in range(len(y_vals))]
        
        df[y_key] = [y_vals[i] - linear_term[i] for i in range(len(y_vals))]
        df[x_key] = x_vals




    def plot_scatter(self,x_key, y_key, source=None, save_path=None, title=None):
        """
        Plot a scatter plot of data from a dictionary.

        Parameters:
            x_key (str): Key in the dictionary for X values.
            y_key (str): Key in the dictionary for Y values.
            save_path (str, optional): Path to save the plot as a PNG file.
        """

        if source == None:
            if len(self.data_sources) == 1:
                source = self.data_sources[0]
            else:
                print("ERR: Must specify source for freq_avg")
                return None

        sg.log.debug("Analysis: Creating scatter plot...")

        data_dict = self.data[source]
        
        # Extract X and Y values from the dictionary
        x_values = data_dict.get(x_key, [])
        y_values = data_dict.get(y_key, [])

        # Check if the lengths of x_values and y_values match
        if len(x_values) != len(y_values):
            raise ValueError("Lengths of X and Y values must match.")

        # Create scatter plot
        plt.figure(figsize=(8, 6))
        plt.scatter(x_values, y_values, color='b', alpha=0.7)
        
        # Set labels and title
        plt.xlabel(x_key)
        plt.ylabel(y_key)

        if title == None:
            title = f"{source}: {y_key} vs {x_key}"
        plt.title(title)
        
        # Show grid
        plt.grid(True)
        
        # Save plot as PNG if save_path is provided
        if save_path:
            plt.savefig(save_path)
            print(f"Plot saved as {save_path}")
        else:
            plt.show()


    def _plot_scatter(self,x_key,y_key,sources):
        for source in sources:

            data_dict = self.data[source]
            
            # Extract values and frequency counts from the dictionary
            x_vals = data_dict.get(x_key, [])
            y_vals = data_dict.get(y_key, [])

            plt.scatter(x_vals, y_vals, label=source)

    def _plot_histogram(self,x_key,y_key,sources,bin_size):
        ## GENERATE A HISTOGRAM FROM EACH DATA SOURCE
        for source in sources:

            data_dict = self.data[source]
            
            # Extract values and frequency counts from the dictionary
            values = data_dict.get(x_key, [])
            frequencies = data_dict.get(y_key, [])

            # Set bins based on bin_size or default to bin width of 1
            if bin_size is None:
                bins = range(int(min(values)), int(max(values)) + 2, 1)
            else:
                bins = range(int(min(values)),int(max(values))+2, int(bin_size))
                #int((max(values) - min(values)) / bin_size)

            plt.hist(values, bins=bins, weights=frequencies, histtype='step', label=source)



    def make_plots(self,x_key, y_key, plot_type, sources=None, bin_size=None, save_path=None, title=None, output_option=0):
        """
        Plot a histogram of data from a dictionary.

        Parameters:
            values_key (str): Key in the dictionary for values.
            frequency_key (str): Key in the dictionary for frequency counts.
            sources (str, or list of str): names of data sources to be included in the histogram.
            bin_size (float, optional): Size of bins for histogram. Default is None.
            save_path (str, optional): Path to save the plot as a PNG file.
            title (str, optional): Title
            output_option(int): 1 = show, 2 = save, 3 = both
        """

        # If no source is specified, but there's only one source in data_sources, just use that.
        if sources == None:
            if len(self.data_sources) == 1:
                sources = self.data_sources[0]
            else:
                print("ERR: Must specify source for histogram")
                return None
                
        if type(sources) == str:
            sources = [sources]

        sg.log.debug("Analysis: Creating plots...")

        
        if plot_type == "Histogram":
            self._plot_histogram(x_key, y_key, sources, bin_size)
            
        elif plot_type == "Scatter Plot":
            self._plot_scatter(x_key, y_key, sources)

        else:
            print(f"{plot_type} is unknown, please select either 'Histogram' or 'Scatter Plot'")
        
        ## TITLE AND AXIS LABELS
        
        # Set labels and title
        plt.xlabel(x_key)
        plt.ylabel(y_key)

        #Default title generation
        if title == None:
            if len(sources) == 1:
                title = f'{sources[0]}: {plot_type} of {y_key} vs {x_key}'
            else:
                title = f'{plot_type} of {y_key} vs {x_key}'
        plt.title(title)
        
        #Default save path generation
        FILENAME_ILLEGAL_CHARS = [" ",".",":","?"]
        
        if save_path == None:
            for c in FILENAME_ILLEGAL_CHARS:
                title = title.replace(c,"_")
            save_path = "./output/" + title.replace(".","_").replace(" ","_") + ".png"

        # Show grid
        plt.grid(True)
        
        plt.legend()
        
        # Save plot as PNG if save_path is provided
        #1. Showing the histogram
        #2. Save the histogram
        #3. Both show and save the histogram
        if output_option == 1:
            plt.show()
        elif output_option == 2:
            plt.savefig(save_path)
            print(f"Plot saved as {save_path}")
        elif output_option == 3:
            plt.savefig(save_path)
            plt.show()
            print(f"Plot saved as {save_path}")
        else:
            print(f"make_plots() Error: Output Option must be 1, 2 or 3")
            
        plt.clf()

    
    #Returns list of sources to perform the operation on.
    # Returns: A LIST of sources the user has selected (even if that list is only 1 element).
    def _ashell_get_source(self):
        print("Select Data Source:")
        print("0. All data sources")
        
        for i in range(len(self.data_sources)):
            print(f"{i+1}. {self.data_sources[i]}")
            
        
        while True:
            try:
                user_selection = int(input("selection?").strip())
                
                if user_selection == 0:
                    return self.data_sources
                elif user_selection > 0 and user_selection < len(self.data_sources)+1:
                    return [self.data_sources[user_selection-1]]
                else:
                    print(f"Error! {user_selection} wasn't on the list.")
                
            except ValueError:
                print("Error! Please enter an integer.")
           
    
    #Given a particular source, gives the user the option to select which column they want to get data from. 
    def _ashell_get_key(self,source):
        print("Available Data Columns:")
        
        cols = list(self.data[source].keys())
        
        for i in range(len(cols)):
            print(f"{i+1}. {cols[i]}")
            
        
        while True:
            try:
                user_selection = int(input("selection?").strip())
                
                if user_selection > 0 and user_selection < len(cols)+1:
                    return cols[user_selection-1]
                else:
                    print(f"Error! {user_selection} wasn't on the list.")
                
            except ValueError:
                print("Error! Please enter an integer.")        
        

    def ashell(self):
        """Analysis shell"""
        
        
        
        while True:
            
            user_input = input(">ashell>").strip()
            
            if user_input == "exit" or user_input == "quit":
                break
             
            ## Load Data Files
            elif user_input == "df":
                df_to_load = filedialog.askopenfilenames()
                
                for df in df_to_load:
                    self.load_df(df)
            
            ## Commands that deal with Freq-Type data
            elif user_input in ["mean", "std", "hist", "mhist", "outliers"]:
            
                sources = self._ashell_get_source()
                
                print("Choose which column contains bins:")
                bins = self._ashell_get_key(sources[0])
                
                print("Choose which column contains counts:")
                counts = self._ashell_get_key(sources[0])
                
                
                if user_input == "hist" or user_input == "mhist":
                
                    bin_size = input("Bin size? (hit enter for default)").strip()
                    
                    if bin_size == "":
                        bin_size = None
                    else:
                        bin_size = float(bin_size)
                        
                    title = input("title? (hit enter for default)").strip()
                    
                    if title == "":
                        title = None

                    user_filename = input("filename? (hit enter for default)").strip()
                    output_option = int(input("Let us know, what kind of output option you would like to have? \n 1. Show the plot \n 2. Save the plot \n 3. Both show and save the plot"))
                                            
                    if user_filename == "":
                        save_path = None
                        
                    else:
                        save_path = "./output/"+user_filename
                        
                elif user_input == "outliers":
                    lower_bound = int(input("lower bound?"))
                    upper_bound = int(input("upper bound?"))
                    
                
                if user_input == "mhist":
                    self.make_plots(bins,counts, "Histogram", sources, bin_size, save_path, title, output_option)
                    
                else:
                    for s in sources:
                    
                        print(f"Data Source: {s}")
                    
                        if user_input == "std" or user_input == "mean":
                            print("Avg:",self.freq_avg(bins,counts,s))
                            print("Std:",self.freq_stddev(bins,counts,s))
                            
                        elif user_input == "hist":
                            self.make_plots(bins,counts,"Histogram", s, bin_size, save_path, title, output_option)
                        elif user_input == "outliers":
                            self.exclude_outliers(bins, counts, s, [lower_bound, upper_bound])
  
  
            ## Commands that deal with XY-Type Data
            elif user_input in ["scatter","mscatter", "cancel_linear"]:
            
                sources = self._ashell_get_source()
                
                # Get X and Y keys
                print("Choose which column contains X values:")
                x_key = self._ashell_get_key(sources[0])
                
                print("Choose which column contains Y values:")
                y_key = self._ashell_get_key(sources[0])
                
                
                # For scatterplots only, get a title.
                if user_input in ["scatter", "mscatter"]:
                    title = input("title? (hit enter for default)").strip()
                        
                    if title == "":
                        title = None

                    user_filename = input("filename? (hit enter for default)").strip()
                    output_option = int(input("Let us know, what kind of output option you would like to have? \n 1. Show the histogram \n 2. Save the histogram \n 3. Both show and save the histogram"))
                                            
                    if user_filename == "":
                        save_path = None
                        
                    else:
                        save_path = "./output/"+user_filename
                

                elif user_input == "cancel_linear":
                    crop_pts = int(input("crop_pts?"))
                    

                # Actually run the requested functions
                    
                if user_input == "mscatter":
                    self.make_plots(x_key, y_key, "Scatter Plot", sources, save_path=save_path, title=title, output_option=output_option)
                else:
                    for s in sources:
                        print(f"Data Source: {s}")
                        if user_input == "scatter":
                            self.make_plots(x_key, y_key, "Scatter Plot", s, save_path=save_path, title=title, output_option=output_option)
                        elif user_input == "cancel_linear":
                            self.cancel_linear(x_key, y_key,s,crop_pts)

            ## Clear datafiles
            elif user_input == "clear":
                print("Which data source should be removed?")
                sources_to_delete = self._ashell_get_source().copy()
                
                sg.log.debug(f"Sources to delete: {sources_to_delete}")
                
                for s in sources_to_delete:
                    sg.log.debug(f"Deleting source {s}")
                    self.data_sources.remove(s)
                    self.data.pop(s)
            
            
            elif user_input == "ldf":
                for i in range(len(self.data_sources)):
                    print(f"{i+1}. {self.data_sources[i]}")
            
            elif user_input == "":
                continue
            
            elif user_input == "help":
                print(ASHELL_HELPTEXT)
            
            else:
                print("Unrecognized.")
                print(ASHELL_HELPTEXT)
        
                
    
