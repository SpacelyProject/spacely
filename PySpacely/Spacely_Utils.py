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


sys.path.append(os.path.abspath("./src"))


#Import utilities from py-libs-common
from hal_serial import * #todo: this shouldn't import all symbols but just the ArudinoHAL class
from pattern_runner import *
from fnal_libawg import AgilentAWG
from fnal_ni_toolbox import * #todo: this should import specific class(es)
import fnal_log_wizard as liblog

from Master_Config import *
import Spacely_Globals as sg

# SPACELY GLOBAL VARIABLES






def config_AWG_as_DC(val_mV: float) -> None:
    if USE_ARDUINO and EMULATE_ASIC:
        emucomp = str(val_mV*0.001)
        sg.log.debug(f"EMULATE_ASCI compinp={emucomp}")
        command_ng(sg.log, sg.port,"compinp:"+str(val_mV*0.001))
    else:
        awgdc = str(round(val_mV/1000,4))
        #sg.log.debug(f"AWG_as_DC set to {awgdc}")
        sg.AWG.send_line_awg("FUNC DC")
        sg.AWG.set_offset(val_mV)
        sg.AWG.set_output(True)

def set_Vin_mV(val_mV: float) -> None:
    if USE_ARDUINO and EMULATE_ASIC:
        command_ng(sg.log, sg.port,"compinp:"+str(val_mV*0.001))
    else:
        sg.AWG.set_offset(val_mV)
        #sg.AWG.send_line("VOLT:OFFS "+str(round(val_mV/1000,4)))
        #time.sleep(0.1)


def set_pulse_mag(val_mV: float) -> None:
    pulse = round(val_mV / 1000,6)
    sg.AWG.send_line_awg("VOLT "+str(pulse))


def config_AWG_as_Pulse(pulse_mag_mV, pulse_width_us=0.28):
    sg.AWG.set_output(False)
    sg.AWG.send_line_awg("FUNC PULS")

    #Pulse will be from (2.5 - pulse) to 2.5
    pulse = round(pulse_mag_mV / 1000,6)
    offset = round(2.5 - pulse_mag_mV/2000,6)
    w = round(pulse_width_us*1e-6,10)
    
    sg.AWG.send_line_awg("PULSE:WIDTH "+str(w)) #Pw = 280 ns (just slightly longer than PreSamp)
    sg.AWG.send_line_awg("PULSE:PERIOD 0.000009") #Period = 9 us ( < 10 us)
    
    sg.AWG.send_line_awg("VOLT:OFFS "+str(offset))
    sg.AWG.send_line_awg("VOLT "+str(pulse))

    #Bursts will be triggered by Trig In (w/ a positive slope)
    #Note: Trig In will be connected to PreSamp
   
    sg.AWG.send_line_awg("BURS:MODE TRIG")
    sg.AWG.send_line_awg("TRIG:SOUR EXT")
    sg.AWG.send_line_awg("TRIG:SLOP POS")
    #Each Trig In will result in 1 burst
    sg.AWG.send_line_awg("BURS:NCYC 1")

    #Enable bursts
    sg.AWG.send_line_awg("BURS:STAT ON")

    sg.AWG.set_output(True)


# config_AWG_as_Skipper - Sets up the AWG to mimic the output of a Skipper-CCD
# source follower, based on the external trigger.
#
# GZ 6/9/2023: I removed all flush_buffer() calls here; you shouldn't manipulate buffers externally
#              unless there's some proven bug existing that it needs it
def config_AWG_as_Skipper(pedestal_mag_mV: int, signal_mag_mV: int) -> None:
    sg.AWG.set_output(False)

    #Output a user-defined function...
    sg.AWG.send_line_awg("FUNC USER")

    #Set up the skipper arbitrary waveform
    sg.AWG.send_line_awg("FREQ 1000000") #50 ns / div
    sg.AWG.send_line_awg("VOLT:OFFS 2.5") #4.0 Vreset

    #NOTE: With Vpp = 2.0V, +1.0 = +1.0V and -1.0 = -1.0V.
    p = round(pedestal_mag_mV / 1000,6)
    s = round((signal_mag_mV + pedestal_mag_mV)/1000,6)

    #wave = [0,-p,-p,-p,-p,-p,-s,-s,-s,-s,-s,-s,0,0,0,0,0,0,0,0]

    # Modified timing:
    wave = [0,-p,-p,-p,-s,-s,-s,-s,-s,-s,0,0,0,0,0,0,0,0]

    print(wave)

    sg.AWG.send_line_awg("DATA VOLATILE, "+", ".join([str(x) for x in wave])+"\n")

    #NOTE: There is a bug in the AWG, where sending data w/ DATA VOLATILE
    #will completely scramble the Vpp magnitude. So we need to write Vpp
    #just after sending data. EDIT: Still doesn't solve the problem. :(
    sg.AWG.send_line_awg("VOLT 2.0") #2 Volt pp magnitude
    #sg.AWG.send_line("VOLT:HIGH 3.5") #2 Volt pp magnitude
    #sg.AWG.send_line("VOLT:LOW 1.5") #2 Volt pp magnitude

    #Bursts will be triggered by Trig In (w/ a positive slope)
    #Note: Trig In will be connected to PostSamp
    sg.AWG.send_line_awg("BURS:MODE TRIG")
    sg.AWG.send_line_awg("TRIG:SOUR EXT")
    sg.AWG.send_line_awg("TRIG:SLOP POS")
    #Each Trig In will result in 1 burst
    sg.AWG.send_line_awg("BURS:NCYC 1")

    #Enable bursts
    sg.AWG.send_line_awg("BURS:STAT ON")

    sg.AWG.send_line_awg("FUNC:USER VOLATILE")

    sg.AWG.set_output(True)


def abbreviate_list(big_list):
    #It's well known that any number smaller than 210 is not that big.
    if len(big_list) < 106:
        return str(big_list)
    else:
        s1 = ",".join([str(x) for x in big_list[:50]])
        s2 = ",".join([str(x) for x in big_list[-50:]])
        return "["+s1+".........."+s2+"] (total # elems = "+str(len(big_list))+")"


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

def report_NI(repeat_delay: float|None = 1):
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
            time.sleep(repeat_delay)

    except KeyboardInterrupt:
        clean_terminal()
        print(tabulate_all_rails())

#Updates the voltage limit of all Isources.
def update_all_Vlimit(new_voltage_limit):
    for key in I_PORT.keys():
        I_PORT[key].update_voltage_limit(new_voltage_limit)

## HELPER FUNCTIONS ##

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

# todo: Some of the logs here about initing sources can probably be moved to generic_nidcpower
def initialize_NI():
    if sg.NI_CONNECTED:
        sg.log.warning("NI already initialized; reinitializing")
        deinitialize_NI()

    sg.log.debug("NI INSTR init")
    try:
        for instr_name in INSTR_INIT_SEQUENCE:
            sg.log.blocking(f"Initializing NI INSTR \"{instr_name}\"")
            INSTR[instr_name] = nidcpower_init(instr_name)
            sg.log.block_res()
        sg.log.debug("NI INSTR init done")

        sg.log.debug("NI Vsource init")
        for Vsource in V_SEQUENCE:
            #time.sleep(0.5)
            sg.log.blocking(f"Initializing Vsource \"{Vsource}\" @ {V_INSTR[Vsource]}#{V_CHAN[Vsource]} to {V_LEVEL[Vsource]}V (IMax={V_CURR_LIMIT[Vsource]:.4f})")
            V_PORT[Vsource] = Source_Port(INSTR[V_INSTR[Vsource]], V_CHAN[Vsource],default_current_limit=V_CURR_LIMIT[Vsource])
            V_PORT[Vsource].set_voltage(V_LEVEL[Vsource])
            sg.log.block_res()
        sg.log.debug("NI Vsource init done")

        sg.log.debug("NI Isource init")
        for Isource in I_SEQUENCE:
            sg.log.blocking(f"Initializing Isource \"{Isource}\" @ {I_INSTR[Isource]}#{I_CHAN[Isource]} to {I_LEVEL[Isource]:.6f}")
            I_PORT[Isource] = Source_Port(INSTR[I_INSTR[Isource]], I_CHAN[Isource],default_voltage_limit=I_VOLT_LIMIT)
            I_PORT[Isource].set_current(I_LEVEL[Isource])
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


def cycle_NI():
    deinitialize_NI()
    initialize_NI()

def deinitialize_NI() -> None:
    for instr_name, session in INSTR.items():
        if session is None:
            sg.log.debug(f"Skipping NI {instr_name} deinit - not initialized")
            continue

        try:
            sg.log.blocking(f"Deinitializing NI INSTR \"{instr_name}\"")
            nidcpower_deinit(session)
            INSTR[instr_name] = None
            sg.log.block_res()
        except Exception as e:
            sg.log.block_res(False)
            sg.log.error(f"Failed to deinitialize NI \"{instr_name}\": {str(e)}")
            pass # we cannot throw here - other things must de-init regardless

    sg.log.debug("NI deinit done")
    sg.NI_CONNECTED = False

## sg.AWG SETUP ##

def initialize_AWG(interactive: bool = True) -> AgilentAWG:
    if sg.AWG_CONNECTED or sg.AWG is not None:
        sg.log.warning("AWG already initialized; reinitializing")
        deinitialize_AWG()

    connected = False
    while True:
        if interactive:
            PROLOGIX_IPADDR = input(f"IP ADDRESS? (Hit enter to use \"{DEFAULT_PROLOGIX_IPADDR}\") >>>")

            if PROLOGIX_IPADDR == "":
                PROLOGIX_IPADDR = DEFAULT_PROLOGIX_IPADDR

            AWG_GPIBADDR = input(f"GPIB ADDRESS? (Hit enter to use \"{DEFAULT_AWG_GPIBADDR}\") >>>")

            if AWG_GPIBADDR == "":
                AWG_GPIBADDR = DEFAULT_AWG_GPIBADDR
        else:
            PROLOGIX_IPADDR = DEFAULT_PROLOGIX_IPADDR
            AWG_GPIBADDR = DEFAULT_AWG_GPIBADDR

        sg.log.info(f"Connecting to AWG @ GPIB#{AWG_GPIBADDR} via IP:{PROLOGIX_IPADDR}")
        sg.AWG = AgilentAWG(sg.log, PROLOGIX_IPADDR, AWG_GPIBADDR)
        sg.AWG.connect()
        sg.AWG.set_limit(V_LEVEL["Vref"])

        # Connection succesful
        if sg.AWG.is_connected():
            break

        sg.AWG = None
        sg.AWG_CONNECTED = False
        if interactive:
            sg.log.error(f"AWG connection failed! Try again.")
        else:
            sg.log.warning(f"AWG connection failed - falling back to interactive mode")
            interactive = True


    sg.AWG_CONNECTED = True


    sg.AWG.send_line_awg("OUTP:LOAD INF") #sg.AWG will be driving a MOSFET gate; set to high impedance mode.
    sg.AWG.set_local_controls(True)
    sg.AWG.display_text("Managed by Spacely")

    sg.log.notice("sg.AWG connected & initialized")
    return sg.AWG

def deinitialize_AWG() -> None:

    if sg.AWG is None:
        sg.log.debug(f"Skipping AWG deinit - not initialized")
        return

    sg.log.blocking(f"Deinitializing AWG")
    sg.AWG.set_output(False)
    sg.AWG.disconnect()
    sg.log.block_res()
    sg.AWG_CONNECTED = False


def auto_voltage_monitor():
    if sg.NI_CONNECTED:
        # Automatic Voltage Warning
        abnormal_rails = []
        abnormal_rail_voltages = []

        for Vsource in V_SEQUENCE:
            voltage = V_PORT[Vsource].get_voltage()
            if Vsource in V_WARN_VOLTAGE.keys():
                if voltage < V_WARN_VOLTAGE[Vsource][0] or voltage > V_WARN_VOLTAGE[Vsource][1]:
                    abnormal_rails.append(Vsource)
                    abnormal_rail_voltages.append(voltage)
        for Isource in I_SEQUENCE:
            voltage = I_PORT[Isource].get_voltage()
            if Isource in I_WARN_VOLTAGE.keys():
                if voltage < I_WARN_VOLTAGE[Isource][0] or voltage > I_WARN_VOLTAGE[Isource][1]:
                    abnormal_rails.append(Isource)
                    abnormal_rail_voltages.append(voltage)

        if len(abnormal_rails) > 0:
            print("*** WARNING *** Abnormal voltage on: ",end='')
            for i in range(len(abnormal_rails)):
                print(abnormal_rails[i],"("+str(round(abnormal_rail_voltages[i],2))+"V) ",end='')

            print("")
    

