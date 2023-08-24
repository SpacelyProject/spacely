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
import tkinter as tk
from tkinter import filedialog


sys.path.append(os.path.abspath("./src"))


#Import utilities from py-libs-common
from hal_serial import * #todo: this shouldn't import all symbols but just the ArudinoHAL class
from pattern_runner import *
from fnal_libawg import AgilentAWG
from fnal_ni_toolbox import * #todo: this should import specific class(es)
import fnal_log_wizard as liblog



#Global Configuration data.
from Master_Config import *
import Spacely_Globals as sg
from Spacely_Utils import *



##################################################



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
sg.log = liblog.AnsiTerminalLogger( # by default log to terminal and use ANSI
    log_term_out,
    max_level=liblog.levels.LOG_DEBUG if VERBOSE else liblog.levels.LOG_INFO,
    ansi=cmd_args.ansi
)

# If --file-log is specified we need to also log to file *in addition* to terminal
if cmd_args.file_log is not False:
    sg.log = liblog.ChainLogger([sg.log]) # add default logger (created above) to the chain
    log_file = cmd_args.file_log # user can specify file manually like --file-log super_important_test.log

    if cmd_args.file_log is None: # ...but if only --file-log is used without a value we will pick a name
        log_file = reserve_dated_file('output log', directory='logs', extension='log')

    sg.log.info(f"Logging to file {log_file}")
    file_strategy = liblog.FileOutputStrategy(log_file)
    file_logger = liblog.PlainLogger(file_strategy)
    sg.log.add_logger(file_logger)


# Ensure all resources are freed automatically on exit (even if error occured)
def exit_handler():
    sg.log.info("Freeing resources...")
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
    sg.port = initialize_Arduino(interactive=not assume_defaults)
else:
    sg.log.debug('HAL init skipped')

init_ni = cmd_args.ni
if init_ni is None and USE_NI == True:
    cmd_txt = input("DEFAULT: Set up NI sources. 'n' to Skip>>>")
    init_ni = False if cmd_txt == 'n' else True
if init_ni:
    if USE_ARDUINO and EMULATE_ASIC:
        sg.log.error('ASIC emulation enabled - NI sources should NOT be initialized!')
    else:
        initialize_NI()
else:
    sg.log.debug('NI init skipped')

init_awg = cmd_args.awg
if init_awg is None and USE_AWG == True:
    cmd_txt = input("DEFAULT: Set up AWG. 'n' to Skip>>>")
    init_awg = False if cmd_txt == 'n' else True
if init_awg:
    if USE_ARDUINO and EMULATE_ASIC:
        sg.log.error('ASIC emulation enabled - AWG should NOT be initialized!')
    else:
        initialize_AWG(interactive=not assume_defaults)

else:
    sg.log.debug('AWG init skipped')

print("# Spacely ready to take commands (see \"help\" for details)")
#Valid Commands:
# find_DNL()
# Vin_sweep()

#Command loop
while True:

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

    sg.log.debug(f"Running: {cmd_txt}")
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
            sg.port=initialize_Arduino()
        case 'ni':
            initialize_NI()
        case 'ni_mon':
            report_NI(0.5)
        case 'awg':
            initialize_AWG()
        case 'gcshell':
            if 'DEFAULT_IOSPEC' in globals():
                print("** Starting gcshell with",DEFAULT_IOSPEC,"**")
                gc = GlueConverter(DEFAULT_IOSPEC)
            else:
                gc = GlueConverter()
            gc.gcshell()
        case 'fpgadbg':
            #Start a pattern runner instance, which will initialize the FPGA
            p = PatternRunner(sg.log,DEFAULT_IOSPEC)
            dbg = list(p._interface.values())[0]
            while True:
                x = dbg.interact()
                if type(x) == list:
                    print(abbreviate_list(x))
                else:
                    print(x)
                
        case 'lr':
            for r in ROUTINES:
                print(r.__doc__)
        case 'cls':
            clean_terminal()
            print("")
            sg.log.debug("Terminal cleared on user request")
            continue

        case _: ### "Starts with" commands
            match cmd_txt[0].lower():
                case '?':
                    if not sg.ARDUINO_CONNECTED:
                        sg.log.error("Cannot send command: HAL not connected. Use \"arduino\" command to connect.")
                        continue
                    #r = command_ng(sg.log, sg.port, cmd_txt[1:])
                    r = command(sg.port, cmd_txt[1:]) # for now it uses the old command due to streaming support

                case '~':
                    #Routines should be called as "~r0"
                    ROUTINES[int(cmd_txt[2])]()

                case '#':
                    sg.log.notice(cmd_txt[1:].strip())

                case _:
                   try:
                        sg.log.debug(f"Executing \"{cmd_txt}\" as code")
                        exec(f"out = {cmd_txt}")
                        if out is not None:
                            print(f"=> {out}")
                   except Exception as e:
                        print(f"={type(e).__name__}=> ", end='')
                        print(e)
