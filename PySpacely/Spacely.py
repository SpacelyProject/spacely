# SPACELY #
# @todo this should be moved to src
# Here be dragons for now ;) #

# To run it:
#  cd .....\SPROCKET\
#  .\venv\Scripts\activate
#  python .\Spacely.py --help
#    /\ Note: DO NOT use "py" shortcut on Windows (it lauches a wrong Python distro!)

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

sys.path.append(os.path.abspath("./src"))
from hal_serial import * #todo: this shouldn't import all symbols but just the ArudinoHAL class
from pattern_runner import *
from fnal_libawg import AgilentAWG
from fnal_ni_toolbox import * #todo: this should import specific class(es)
import fnal_log_wizard as liblog

#Global Configuration data.
from Master_Config import *



##################################################

#Arduino port. Making this a global variable allows for
#commands that would affect the NI System or analog to send
#emulation commands to the Arduino instead.
port = None
AWG = None

ARDUINO_CONNECTED = False
NI_CONNECTED = False
AWG_CONNECTED = False
log = None


## INSTRUMENT CONTROL FUNCTIONS ##

def config_AWG_as_DC(val_mV: float) -> None:
    global port
    if USE_ARDUINO and EMULATE_ASIC:
        emucomp = str(val_mV*0.001)
        log.debug(f"EMULATE_ASCI compinp={emucomp}")
        command_ng(log, port,"compinp:"+str(val_mV*0.001))
    else:
        awgdc = str(round(val_mV/1000,4))
        #log.debug(f"AWG_as_DC set to {awgdc}")
        AWG.send_line_awg("FUNC DC")
        AWG.set_offset(val_mV)
        AWG.set_output(True)

def set_Vin_mV(val_mV: float) -> None:
    global port
    if EMULATE_ASIC:
        command_ng(log, port,"compinp:"+str(val_mV*0.001))
    else:
        AWG.set_offset(val_mV)
        #AWG.send_line("VOLT:OFFS "+str(round(val_mV/1000,4)))
        #time.sleep(0.1)


def set_pulse_mag(val_mV: float) -> None:
    pulse = round(val_mV / 1000,6)
    AWG.send_line_awg("VOLT "+str(pulse))


def config_AWG_as_Pulse(pulse_mag_mV, pulse_width_us=0.28):
    AWG.set_output(False)
    AWG.send_line_awg("FUNC PULS")

    #Pulse will be from (2.5 - pulse) to 2.5
    pulse = round(pulse_mag_mV / 1000,6)
    offset = round(2.5 - pulse_mag_mV/2000,6)
    w = round(pulse_width_us*1e-6,10)
    
    AWG.send_line_awg("PULSE:WIDTH "+str(w)) #Pw = 280 ns (just slightly longer than PreSamp)
    AWG.send_line_awg("PULSE:PERIOD 0.000009") #Period = 9 us ( < 10 us)
    
    AWG.send_line_awg("VOLT:OFFS "+str(offset))
    AWG.send_line_awg("VOLT "+str(pulse))

    #Bursts will be triggered by Trig In (w/ a positive slope)
    #Note: Trig In will be connected to PreSamp
   
    AWG.send_line_awg("BURS:MODE TRIG")
    AWG.send_line_awg("TRIG:SOUR EXT")
    AWG.send_line_awg("TRIG:SLOP POS")
    #Each Trig In will result in 1 burst
    AWG.send_line_awg("BURS:NCYC 1")

    #Enable bursts
    AWG.send_line_awg("BURS:STAT ON")

    AWG.set_output(True)


# config_AWG_as_Skipper - Sets up the AWG to mimic the output of a Skipper-CCD
# source follower, based on the external trigger.
#
# GZ 6/9/2023: I removed all flush_buffer() calls here; you shouldn't manipulate buffers externally
#              unless there's some proven bug existing that it needs it
def config_AWG_as_Skipper(pedestal_mag_mV: int, signal_mag_mV: int) -> None:
    AWG.set_output(False)

    #Output a user-defined function...
    AWG.send_line_awg("FUNC USER")

    #Set up the skipper arbitrary waveform
    AWG.send_line_awg("FREQ 1000000") #50 ns / div
    AWG.send_line_awg("VOLT:OFFS 2.5") #4.0 Vreset

    #NOTE: With Vpp = 2.0V, +1.0 = +1.0V and -1.0 = -1.0V.
    p = round(pedestal_mag_mV / 1000,6)
    s = round((signal_mag_mV + pedestal_mag_mV)/1000,6)

    #wave = [0,-p,-p,-p,-p,-p,-s,-s,-s,-s,-s,-s,0,0,0,0,0,0,0,0]

    # Modified timing:
    wave = [0,-p,-p,-p,-s,-s,-s,-s,-s,-s,0,0,0,0,0,0,0,0]

    print(wave)

    AWG.send_line_awg("DATA VOLATILE, "+", ".join([str(x) for x in wave])+"\n")

    #NOTE: There is a bug in the AWG, where sending data w/ DATA VOLATILE
    #will completely scramble the Vpp magnitude. So we need to write Vpp
    #just after sending data. EDIT: Still doesn't solve the problem. :(
    AWG.send_line_awg("VOLT 2.0") #2 Volt pp magnitude
    #AWG.send_line("VOLT:HIGH 3.5") #2 Volt pp magnitude
    #AWG.send_line("VOLT:LOW 1.5") #2 Volt pp magnitude

    #Bursts will be triggered by Trig In (w/ a positive slope)
    #Note: Trig In will be connected to PostSamp
    AWG.send_line_awg("BURS:MODE TRIG")
    AWG.send_line_awg("TRIG:SOUR EXT")
    AWG.send_line_awg("TRIG:SLOP POS")
    #Each Trig In will result in 1 burst
    AWG.send_line_awg("BURS:NCYC 1")

    #Enable bursts
    AWG.send_line_awg("BURS:STAT ON")

    AWG.send_line_awg("FUNC:USER VOLATILE")

    AWG.set_output(True)


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
    log.debug(bitstring)
    for i in range(len(bitstring)):
        if bitstring[i]=="1":
            avg = avg + 1.0/len(bitstring)

    log.debug(avg)
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
    global port

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
            log.debug(v)

            #Run the command to send the CDAC pattern 100 times.
            #x = time.perf_counter_ns()
            r = command_ng(log, port, "cdac100x:"+cdac_codes[c])
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
    global port

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
            #log.debug(Vtest_sweep[v])

            if PROGRESS and v % (len(Vtest_sweep)/20)==0:
                print("|",end="")

            r = command_ng(log, port, "conv100x")

            #Format the response
            r = r.replace("conv100x","").replace("?","").strip()

            x = liststring_avg_stdev(r)

            write_file.write((str(Vtest_sweep[v])+","+str(x[0])+","+str(x[1])+"\n").encode())

    if PROGRESS:
        print("]")


def Vin_sweep_full_chain(Vtest_min_mV: int = 10, Vtest_max_mV: int = 100, increment_uV: int = 10000):
    global port

    if Vtest_min_mV <= 2:
        log.error("In full-channel mode, step voltage must be > 2 mV")
        return
        
    filename = reserve_dated_file(f"Vin sweep FULL {Vtest_min_mV}mV to {Vtest_max_mV}mV by {increment_uV}", directory="output/sweep")
    print("Writing full-chain Vtest Sweep to "+filename)
    
    Vtest_sweep = [round(x*0.1,1) for x in range(10*Vtest_min_mV,10*Vtest_max_mV,int(increment_uV/100))]
    config_AWG_as_Pulse(Vtest_sweep[0], 1.27)

    with open(filename, 'wb') as write_file: #Overwrites the file if it exists.
        write_file.write(b'Vtest,Avg Response[codes],Std Dev[codes]\n')
        
        for v in range(len(Vtest_sweep)):
            set_pulse_mag(Vtest_sweep[v])
            r = command_ng(log, port, "samp100x")
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
    global port

    config_AWG_as_DC(Vtest_mV)

    #r = command(port, "convNx:"+str(points), printresponse=False, timeout_s=10)
    r = command_ng(log, port, f"convNx:{points}")

    #log.debug(f"convNx returned: {r}") # this will return A LOT of lines!
    log.debug(f"Number of values returned: {len(r.split())}")

    #Format the response
    liststring = r.replace("convNx:"+str(points),"").replace("?","").strip()

    return liststring_histogram(liststring)


def center_code(Vtest_init_mV: float, samples_per_val: int = 1000):
    global port

    Vtest = Vtest_init_mV
    Vtest_last = Vtest_init_mV

    count_outside = 1000

    log.info(f"Running centering code from {Vtest_init_mV}mV...")

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

        log.debug(f"Vtest:{Vtest:.2f}mV, mode:{mode}, count_below_mode:{count_below}, count_above_mode:{count_above}")

        # That shouldn't be the case really... something is probably misconnected
        if mode == 0:
            log.warning(f"Suspicious mode of 0 for Vtest={Vtest:.2f}mV")

        #If we are less centered than the previous guess, take the
        #last one and be done with it.
        #PROOF that this loop is non-infinite: count_outside is strictly decreasing and positive.
        if count_above + count_below >= count_outside:
            log.notice(f"Centered at Vtest: {Vtest_last:.2f}mV")
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
        log.debug(f"Writing histograms for Vin Noise Sweep to file \"{filename}\"")
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

        log.notice(f"Histograms for Vin Noise Sweep saved to \"{filename}\"")
        return True

    except Exception as e:
        log.error(f"Noise sweep failed due to {type(e).__name__}: {e}")
        return False

def dump_noise_sweep_stats(Vtest_sweep, vtest_min_mv: int, vtest_max_mv: int, histograms: dict) -> bool:
    try:
        filename = reserve_dated_file(f"vin noise sweep STATS {vtest_min_mv}mV to {vtest_max_mv}mV step{Vtest_sweep[1]-Vtest_sweep[0]}mV", directory='output/noise')
        log.debug(f"Writing stats for Vin Noise Sweep to file \"{filename}\"")
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
                    log.warning(f"Count_outside_bin is 0 for {Vtest}mV")
                    row['z_score'] = 1e99
                    row['rms_noise_in_lsb'] = 0
                else:
                    row['z_score'] = NormalDist().inv_cdf(1 - ((row['count_outside_bin'] / (row['count_outside_bin']+row['count_main_bin']))/2))
                    row['rms_noise_in_lsb'] = 0.5 / row['z_score']
                cw.writerow(row)
            file.close()

        log.notice(f"Histograms for Vin Noise Sweep stats saved to \"{filename}\"")
        return True

    except Exception as e:
        log.error(f"Noise sweep failed due to {type(e).__name__}: {e}")
        return False


def Vin_noise_sweep(vtest_min_mv: int = 0, vtest_max_mv: int = 10, step_mv: int = 1, samples_per_pt: int = 1000000) -> bool:
#    if vtest_max_mv-vtest_min_mv < 10:
#       log.error("Noise requires at least 10mV of a difference between min and max")
#        return
    if vtest_min_mv >= vtest_max_mv:
        log.error("Noise sweep requires min < max")
        return
    if step_mv < 1 or step_mv > (vtest_max_mv - vtest_min_mv):
        log.error("Noise sweep requires step to be >=1 and between min and max")
        return

    #Vtest_sweep = [x for x in range(vtest_min_mv, vtest_max_mv, int((vtest_max_mv - vtest_min_mv) / 10))]
    Vtest_sweep = [x for x in range(vtest_min_mv, vtest_max_mv, step_mv)]

    histograms = {}
    for Vtest in Vtest_sweep:
        log.info(f"Generating histogram for VTest={Vtest:.2f}mV with {samples_per_pt} samples/pt")
        histograms[Vtest] = Vin_histogram(center_code(Vtest), samples_per_pt)

    dump_noise_sweep_histogram(Vtest_sweep, vtest_min_mv, vtest_max_mv, histograms)
    dump_noise_sweep_stats(Vtest_sweep, vtest_min_mv, vtest_max_mv, histograms)


    log.notice(f"Noise sweep finished")
    return True


## TEST ROUTINES

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


R0_VTEST_MIN = 470
R0_VTEST_MAX = 515
R0_VTEST_INCR = 1000

def ROUTINE0_CDAC_Trim():
    """r0: Measure the DNL for every CDAC Trim code, and report the best."""
    print(ROUTINE0_CDAC_Trim.__doc__)

    global R0_VTEST_MIN, R0_VTEST_MAX, R0_VTEST_INCR

    if not check_dependencies(["ARDUINO_CONNECTED",["EMULATE_ASIC","AWG_CONNECTED"]]):
        return

    if EMULATE_ASIC:
        print("**ASIC will be EMULATED by ARDUINO**")

    Vtest_min_mV=R0_VTEST_MIN
    Vtest_max_mV=R0_VTEST_MAX
    increment_uV=R0_VTEST_INCR

    print("STATIC VALUES:\n\t> Vtest_min_mV = "+str(Vtest_min_mV)+"\n\t> Vtest_max_mV = "\
          +str(Vtest_max_mV)+"\n\t> increment_uV = "+str(increment_uV))

    print("""REQUIREMENTS:
    > Chip voltages are powered on.
    > AWG is connected to Vtest.
    > VINSF is connected to 0.0V""")

    input("Press Enter to proceed.")


    filename = reserve_dated_file(f"CapTrim DNL Sweep", directory='output/dnl')
    logfilename = reserve_dated_file(f"CapTrim DNL Sweep", directory='output/dnl', extension='log')
    logfile = open(logfilename,'w')

    with open(filename, 'wb') as write_file:
        write_file.write(b'CapTrim Code,CapTrim String,DNL\n')

        for captrim_code in range(0,64):
            captrim_string = format(captrim_code,'b').zfill(6)

            #Reverse the string because in the set_config HAL command, CapTrim is reported as little-endian.
            # Range2 = 0, TestEn = 1
            command_ng(log, port, "sc:"+captrim_string[::-1]+"01")

            print(progress_pct(captrim_code,63)," Finding DNL for CapTrim=0b"+captrim_string)

            dnl = find_DNL(Vtest_min_mV=Vtest_min_mV,Vtest_max_mV=Vtest_max_mV,increment_uV=increment_uV, logfile=logfile)

            write_file.write((",".join([str(x) for x in [captrim_code,captrim_string,dnl]])+"\n").encode())

    logfile.close()
    print("ROUTINE 0 Complete!")



def fix_latchup():
    V_PORT["VDD_ASIC"].set_voltage(1.2,current_limit=1)

#Simply do one conversion for each CapTrim value.
def ROUTINE1_CapTrim_Debug():

    for captrim_code in range(0,64):
        captrim_string = format(captrim_code,'b').zfill(6)
        #Reverse the string because in the set_config HAL command, CapTrim is reported as little-endian.
        # Range2 = 0, TestEn = 1
        command_ng(log, port, "sc:"+captrim_string[::-1]+"01")
        r = command_ng(log, port, "conv")
        r = r.replace("conv","").replace("?","").strip()
        print(captrim_code, captrim_string, int(r,2))

def ROUTINE2_Full_Channel_Scan():
    """r2: Do a Vin sweep, across the full channel (including preamplifier)."""
    Vin_sweep_full_chain(Vtest_min_mV=100,Vtest_max_mV=1000,increment_uV=10000)


def ROUTINE3_FPGA_Buffer_Lint():
    """r3: Send patterns to GlueFPGA and confirm they are read back."""


    print("""REQUIREMENTS:
        > ASIC should NOT be connected.
        """)
    input("Press Enter to continue...")
    
    fpga = NiFpga(log, "PXI1Slot5")

    #Must be a GlueDirect bitfile.
    fpga.start("C:\\Users\\Public\\Documents\\LABVIEWTEST\\GlueDirectBitfile_6_22_a.lvbitx")
    #time.sleep(1)

    dbg = NiFpgaDebugger(log, fpga)

    #Default values for several registers.
    fpga_default_config = { "Write_to_Mem" : False,
                        "Read_from_Mem": False,
                        "Run_Pattern"  : False,
                        "Buffer_In_Size": 1024,
                        "Buffer_Pass_Size":1024,
                        "FPGA_Loop_Dis": False,
                        "SE_Data_Dir":65535,
                        "SE_Data_Default":60,
                        "Set_Voltage_Family":True,
                        "Voltage_Family":4}

    #Set all registers to their default values.
    for cfg in fpga_default_config.keys():
        dbg.interact("w", cfg, fpga_default_config[cfg])

    print(dbg.interact("r","Set_Voltage_Done"))
    print(dbg.interact("r","Voltage_Family"))
    print(dbg.interact("r","Set_Voltage_Family"))
    testpat = PatternRunner(log,fpga, "C:\\Users\\Public\\Documents\\Glue_Waveforms\\test_iospec.txt")

    #NOTE: FPGA Needs > 2 seconds of delay in between setup and running the first test pattern!
    time.sleep(3)

    print("~ Test Pattern 1 ~")
    tp1_in = [i for i in range(31)]
    tp1_out = testpat.run_pattern(tp1_in)
    print("IN:",tp1_in)
    print("OUT:",tp1_out)

    print("~ Test Pattern 2 ~")
    tp2_in = [i for i in range(50000)] *2
    tp2_out = testpat.run_pattern(tp2_in,outfile="test_out.txt")
    print("IN:",abbreviate_list(tp2_in))
    print("OUT:",abbreviate_list(tp2_out))
    
    diagnose_fifo_timeout(tp2_out)
    

def ROUTINE4_XROCKET1_Pattern():
    """r4: Send testbench patterns to XROCKET1 and read them back."""


    print("""REQUIREMENTS:
        > NI FPGA should be connected to XROCKET1.
        > XROCKET1 should be powered up.
        """)
    input("Press Enter to continue...")
    
    
    #Data files

    tp1_in_file = "C:\\Users\\Public\\Documents\\Glue_Waveforms\\xrocket1_input.glue"
    tp1_out_file = "C:\\Users\\Public\\Documents\\Glue_Waveforms\\xrocket1_output.glue"
    xrocket1_iospec = "C:\\Users\\aquinn\\Desktop\\SPROCKET Test\\spacely\\PySpacely\\asic_config\\XROCKET1\\xrocket1_iospec.txt"
    glue_bitfile = "C:\\Users\\Public\\Documents\\LABVIEWTEST\\GlueDirectBitfile_6_22_a.lvbitx"

    #Set up classes
    fpga = NiFpga(log, "PXI1Slot5")
    fpga.start(glue_bitfile)

    dbg = NiFpgaDebugger(log, fpga)
    dbg.configure(GLUEFPGA_DEFAULT_CFG)

    tp = PatternRunner(log,fpga, xrocket1_iospec)
    gc = GlueConverter(xrocket1_iospec)

    #NOTE: FPGA Needs > 2 seconds of delay in between setup and running the first test pattern!
    time.sleep(3)

    print("Running XROCKET1 Test!")
    
    tp1_out = tp.run_pattern(tp1_in_file, outfile=tp1_out_file)
    gc.compare(gc.parse_glue(tp1_in_file), gc.parse_glue(tp1_out_file))
    print("OUT:",abbreviate_list(tp1_out))

    #gc.plot_glue(tp1_out_file)
    #gc.plot_glue(tp1_in_file)
    

ROUTINES = [ROUTINE0_CDAC_Trim, ROUTINE1_CapTrim_Debug, ROUTINE2_Full_Channel_Scan, ROUTINE3_FPGA_Buffer_Lint, ROUTINE4_XROCKET1_Pattern]

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
    global ARDUINO_CONNECTED
    if ARDUINO_CONNECTED:
        log.warning("HAL already initialized; reinitializing")
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

        log.info(f"Connecting to HAL on {SERIAL_PORT}@{BAUD}")
        port = open_port(SERIAL_PORT, BAUD)
        if port != -1:
            print("Port opened successfully :)")
            break

        if interactive:
            log.error(f"Port openning failed! Try again.")
        else:
            log.warning(f"Port openning failed - falling back to interactive mode")
            interactive = True

    #Initialize communication.
    log.debug("Handshaking with Arduino...")

    #Handshake function will not return unless handshake is successful.
    command_ng(log, port, "echo:off")
    handshake_with_arduino_ng(log, port)
    log.info(f"HAL ID: {command_ng(log, port, 'IDN?')}")

    ARDUINO_CONNECTED = True
    log.notice("Arduino HAL connected & initialized")
    return port

def deinitialize_Arduino() -> None:
    if port is None:
        return

    log.blocking('Deinitializing HAL')
    port.close()
    global ARDUINO_CONNECTED
    ARDUINO_CONNECTED = False
    log.block_res() # todo: this probably should check port status

## NI SETUP ##

# todo: Some of the logs here about initing sources can probably be moved to generic_nidcpower
def initialize_NI():
    global NI_CONNECTED
    if NI_CONNECTED:
        log.warning("NI already initialized; reinitializing")
        deinitialize_NI()

    log.debug("NI INSTR init")
    try:
        for instr_name in INSTR_INIT_SEQUENCE:
            log.blocking(f"Initializing NI INSTR \"{instr_name}\"")
            INSTR[instr_name] = nidcpower_init(instr_name)
            log.block_res()
        log.debug("NI INSTR init done")

        log.debug("NI Vsource init")
        for Vsource in V_SEQUENCE:
            #time.sleep(0.5)
            log.blocking(f"Initializing Vsource \"{Vsource}\" @ {V_INSTR[Vsource]}#{V_CHAN[Vsource]} to {V_LEVEL[Vsource]}V (IMax={V_CURR_LIMIT[Vsource]:.4f})")
            V_PORT[Vsource] = Source_Port(INSTR[V_INSTR[Vsource]], V_CHAN[Vsource],default_current_limit=V_CURR_LIMIT[Vsource])
            V_PORT[Vsource].set_voltage(V_LEVEL[Vsource])
            log.block_res()
        log.debug("NI Vsource init done")

        log.debug("NI Isource init")
        for Isource in I_SEQUENCE:
            log.blocking(f"Initializing Isource \"{Isource}\" @ {I_INSTR[Isource]}#{I_CHAN[Isource]} to {I_LEVEL[Isource]:.6f}")
            I_PORT[Isource] = Source_Port(INSTR[I_INSTR[Isource]], I_CHAN[Isource],default_voltage_limit=I_VOLT_LIMIT)
            I_PORT[Isource].set_current(I_LEVEL[Isource])
            log.block_res()
        log.debug("NI Isource init done")
    except Exception as e:
        log.block_res(False)
        if isinstance(e, OSError) and hasattr(e, 'winerror') and e.winerror == -1066598273:
            log.emerg("NI INSTR failed due to Windows error. Make sure you're NOT using Microsoft Store Python (see https://github.com/ni/nimi-python/issues/1904)")
        else:
            log.emerg("NI INSTR failed (do you have \"NI-DCPower ver >=2022-Q4\" driver installed?)")
        raise

    NI_CONNECTED = True
    log.notice("NI PXI initialized")


def cycle_NI():
    deinitialize_NI()
    initialize_NI()

def deinitialize_NI() -> None:
    for instr_name, session in INSTR.items():
        if session is None:
            log.debug(f"Skipping NI {instr_name} deinit - not initialized")
            continue

        try:
            log.blocking(f"Deinitializing NI INSTR \"{instr_name}\"")
            nidcpower_deinit(session)
            INSTR[instr_name] = None
            log.block_res()
        except Exception as e:
            log.block_res(False)
            log.error(f"Failed to deinitialize NI \"{instr_name}\": {str(e)}")
            pass # we cannot throw here - other things must de-init regardless

    log.debug("NI deinit done")
    global NI_CONNECTED
    NI_CONNECTED = False

## AWG SETUP ##

def initialize_AWG(interactive: bool = True) -> AgilentAWG:
    global AWG_CONNECTED
    global AWG
    if AWG_CONNECTED or AWG is not None:
        log.warning("AWG already initialized; reinitializing")
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

        log.info(f"Connecting to AWG @ GPIB#{AWG_GPIBADDR} via IP:{PROLOGIX_IPADDR}")
        AWG = AgilentAWG(log, PROLOGIX_IPADDR, AWG_GPIBADDR)
        AWG.connect()
        AWG.set_limit(V_LEVEL["Vref"])

        # Connection succesful
        if AWG.is_connected():
            break

        AWG = None
        AWG_CONNECTED = False
        if interactive:
            log.error(f"AWG connection failed! Try again.")
        else:
            log.warning(f"AWG connection failed - falling back to interactive mode")
            interactive = True


    AWG_CONNECTED = True


    AWG.send_line_awg("OUTP:LOAD INF") #AWG will be driving a MOSFET gate; set to high impedance mode.
    AWG.set_local_controls(True)
    AWG.display_text("Managed by Spacely")

    log.notice("AWG connected & initialized")
    return AWG

def deinitialize_AWG() -> None:
    global AWG_CONNECTED
    global AWG

    if AWG is None:
        log.debug(f"Skipping AWG deinit - not initialized")
        return

    log.blocking(f"Deinitializing AWG")
    AWG.set_output(False)
    AWG.disconnect()
    log.block_res()
    AWG_CONNECTED = False

### MAIN ###

# Parse command line arguments
argp = argparse.ArgumentParser(prog='Spacely')
argp.add_argument('--hal', action=argparse.BooleanOptionalAction, help='Perform Arudino HAL init')
argp.add_argument('--ni', action=argparse.BooleanOptionalAction, help='Perform NI voltage sources init')
argp.add_argument('--awg', action=argparse.BooleanOptionalAction, help='Perform AWG (wave generator) init')
argp.add_argument('-d', '--defaults', action='store_true', help='Assume defaults for Arduino ports etc. (otherwise it will ask)')
argp.add_argument('--file-log', const=None, default=False, nargs='?', action='store', help='When specified saves a copy of a log to a given file')
argp.add_argument('--ansi', action=argparse.BooleanOptionalAction, help='Whether to enable ANSI (color) output')
cmd_args = argp.parse_args()

# Setup logging
log_term_out = liblog.HandleOutputStrategy.create_with_stderr()
log = liblog.AnsiTerminalLogger( # by default log to terminal and use ANSI
    log_term_out,
    max_level=liblog.levels.LOG_DEBUG if VERBOSE else liblog.levels.LOG_INFO,
    ansi=cmd_args.ansi
)

# If --file-log is specified we need to also log to file *in addition* to terminal
if cmd_args.file_log is not False:
    log = liblog.ChainLogger([log]) # add default logger (created above) to the chain
    log_file = cmd_args.file_log # user can specify file manually like --file-log super_important_test.log

    if cmd_args.file_log is None: # ...but if only --file-log is used without a value we will pick a name
        log_file = reserve_dated_file('output log', directory='logs', extension='log')

    log.info(f"Logging to file {log_file}")
    file_strategy = liblog.FileOutputStrategy(log_file)
    file_logger = liblog.PlainLogger(file_strategy)
    log.add_logger(file_logger)

# Ensure all resources are freed automatically on exit (even if error occured)
def exit_handler():
    log.info("Freeing resources...")
    deinitialize_AWG()
    deinitialize_NI()
    deinitialize_Arduino()

atexit.register(exit_handler)

print("+*+*+*+*+*+*+*+*+*+*+*+*+*+*+*+*+*+")
print("+       Welcome to Spacely!       +")
print("+ Let's do some science together. +")
print("+*+*+*+*+*+*+*+*+*+*+*+*+*+*+*+*+*+\n")
if USE_ARDUINO and EMULATE_ASIC:
    print("**ASIC will be EMULATED by ARDUINO**")


assume_defaults = cmd_args.defaults
#Default Setup
init_hal = cmd_args.hal
if init_hal is None and USE_ARDUINO == True: # only ask if cmd arg wasn't specified
    cmd_txt = input("DEFAULT: Connect to Arduino. 'n' to Skip>>>")
    init_hal = False if cmd_txt == 'n' else True # init by default
if init_hal:
    port = initialize_Arduino(interactive=not assume_defaults)
else:
    log.debug('HAL init skipped')

init_ni = cmd_args.ni
if init_ni is None and USE_NI == True:
    cmd_txt = input("DEFAULT: Set up NI sources. 'n' to Skip>>>")
    init_ni = False if cmd_txt == 'n' else True
if init_ni:
    if USE_ARDUINO and EMULATE_ASIC:
        log.error('ASIC emulation enabled - NI sources should NOT be initialized!')
    else:
        initialize_NI()
else:
    log.debug('NI init skipped')

init_awg = cmd_args.awg
if init_awg is None and USE_AWG == True:
    cmd_txt = input("DEFAULT: Set up AWG. 'n' to Skip>>>")
    init_awg = False if cmd_txt == 'n' else True
if init_awg:
    if EMULATE_ASIC:
        log.error('ASIC emulation enabled - AWG should NOT be initialized!')
    else:
        initialize_AWG(interactive=not assume_defaults)

else:
    log.debug('AWG init skipped')

print("# Spacely ready to take commands (see \"help\" for details)")
#Valid Commands:
# find_DNL()
# Vin_sweep()

#Command loop
while True:
    try:
        cmd_txt = input('> ')
    # DO NOT add "EOFError" here - it will break report_NI(1) and
    # anything that uses KeyboardInterrupt! Python has a broken exception
    # unwinding on Windows. If you do this, run report_NI(1), press Ctrl+C
    # the inner function will handle Ctrl+C just fine. But any subsequent
    # use of Ctrl+C (e.g. here) will crash Python event loop in a strange
    # way where print() starts reporting exceptions and atexit() handler WILL
    # NOT execute.
    # See (esp. comments!): https://stackoverflow.com/a/31131378
    # It appears to be, as per usual, a problem with Windows.
    except KeyboardInterrupt:
        print("exit")
        break

    log.debug(f"Running: {cmd_txt}")
    ### Full commands
    match cmd_txt.lower():
        case '': # noop - just print another command prompt
            continue
        case 'exit':
            break
        case '?' | 'help':
            print("Spacely can execute the follwing commands:\n")
            print("\t? or help - show this help message")
            print("\texit - terminate the console; same as Ctrl+C")
            print("\tarduino - (re)initialize HAL")
            print("\tni - (re)initialize NI instruments")
            print("\tni_mon - starts printing live values from NI")
            print("\tawg - (re)initialize Arbitrary Wave Generator (AWG)")
            print("\tlr - list routines")
            print("\n")
            print("\t~r<num> - execute routine <num> (e.g. ~r0); see \"lr\" for list")
            print("\t?<cmd> - perform <cmd> RPC to HAL (e.g. ?sc to show config)")
            print("\t# <text> - logs <text> to logs (e.g. to document things)")
            print("\n")
            print("\tcls - CLear Screen")
            print("Any unknown command will be treated as Python code and executed")
            print("Spacely also supports command line options:")
            print("\n")
            argp.print_help()
            print("\n")
            continue

        case 'initialize_Arduino()':
            print("Use 'arduino' to initialize the Arduino. :-)")

        case 'arduino':
            port=initialize_Arduino()
        case 'ni':
            initialize_NI()
        case 'ni_mon':
            report_NI(0.5)
        case 'awg':
            initialize_AWG()
        case 'gcshell':
            gc = GlueConverter()
            gc.gcshell()
        case 'lr':
            for r in ROUTINES:
                print(r.__doc__)
        case 'cls':
            clean_terminal()
            print("")
            log.debug("Terminal cleared on user request")
            continue

        case _: ### "Starts with" commands
            match cmd_txt[0].lower():
                case '?':
                    if not ARDUINO_CONNECTED:
                        log.error("Cannot send command: HAL not connected. Use \"arduino\" command to connect.")
                        continue
                    #r = command_ng(log, port, cmd_txt[1:])
                    r = command(port, cmd_txt[1:]) # for now it uses the old command due to streaming support

                case '~':
                    #Routines should be called as "~r0"
                    ROUTINES[int(cmd_txt[2])]()

                case '#':
                    log.notice(cmd_txt[1:].strip())

                case _:
                   try:
                        log.debug(f"Executing \"{cmd_txt}\" as code")
                        exec(f"out = {cmd_txt}")
                        if out is not None:
                            print(f"=> {out}")
                   except Exception as e:
                        print(f"={type(e).__name__}=> ", end='')
                        print(e)
