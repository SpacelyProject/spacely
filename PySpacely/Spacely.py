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
import ast


sys.path.append(os.path.abspath("./src"))


#Import utilities from py-libs-common
from hal_serial import * #todo: this shouldn't import all symbols but just the ArudinoHAL class
from pattern_runner import *

from fnal_libinstrument import *
from fnal_libIO import *
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
argp.add_argument('--instr', action=argparse.BooleanOptionalAction, help='Perform non-NI Instrument init')
#argp.add_argument('--scope', action=argparse.BooleanOptionalAction, help='Perform Oscilloscope init')
argp.add_argument('-d', '--defaults', action='store_true', help='Assume defaults for Arduino ports etc. (otherwise it will ask)')
argp.add_argument('--skipall', action='store_true', help='Skip initialization of all instruments.')
argp.add_argument('--file-log', const=None, default=False, nargs='?', action='store', help='When specified saves a copy of a log to a given file')
argp.add_argument('--ansi', action=argparse.BooleanOptionalAction, help='Whether to enable ANSI (color) output')
argp.add_argument('-r', type=int, default=None, help='Routine to automatically run.')
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

#Static EXIT_HANDLER_RAN variable ensures that exit handler will only run once.
EXIT_HANDLER_RAN = False

def exit_handler():
    global EXIT_HANDLER_RAN
    if not EXIT_HANDLER_RAN:
        sg.log.info("(Exit Handler) Freeing resources...")
        deinitialize_INSTR()
        deinitialize_Arduino()
        
        EXIT_HANDLER_RAN = True


#We intend that the exit handler should run at the end of the loop
#(see below) but just in case we crash in some other way, we register it here.
atexit.register(exit_handler)

print("+*+*+*+*+*+*+*+*+*+*+*+*+*+*+*+*+*+")
print("+       Welcome to Spacely!       +")
print("+ Let's do some science together. +")
print("+*+*+*+*+*+*+*+*+*+*+*+*+*+*+*+*+*+\n")




if USE_ARDUINO and EMULATE_ASIC:
    print("**ASIC will be EMULATED by ARDUINO**")

assume_defaults = cmd_args.defaults
skip_all = cmd_args.skipall

if not assume_defaults:
    print("Did you know you can skip interactive initialization with --defaults ?")

# # # Default Setup # # #

num_instr = INSTR_lint()
rail_lint_result = rail_lint()

if num_instr == -1 or rail_lint_result == -1:
    exit()

#Arduino HAL
init_hal = cmd_args.hal is not None
if not init_hal and not skip_all and USE_ARDUINO == True: # only ask if cmd arg wasn't specified
    cmd_txt = input("DEFAULT: Connect to Arduino. 'n' to Skip>>>")
    init_hal = False if cmd_txt == 'n' else True # init by default
if init_hal:
    sg.port = initialize_Arduino(interactive=not assume_defaults)
else:
    sg.log.debug('HAL init skipped')

#NI Chassis
init_ni = (cmd_args.ni is not None) or (assume_defaults and USE_NI)
if not init_ni and not skip_all and USE_NI == True:
    cmd_txt = input("DEFAULT: Set up NIFPGA 'n' to Skip>>>")
    init_ni = False if cmd_txt == 'n' else True
if init_ni:
    if USE_ARDUINO and EMULATE_ASIC:
        sg.log.error('ASIC emulation enabled - NI sources should NOT be initialized!')
    else:
        initialize_NIFPGA()
else:
    sg.log.debug('NI init skipped')

#Other non-NI Instruments
init_instr = (cmd_args.instr is not None) or (assume_defaults and len(INSTR) > 0)
if not init_instr and not skip_all and num_instr > 0:
    cmd_txt = input(f"DEFAULT: Initialize {num_instr} Test Instruments. 'n' to Skip>>>")
    init_instr = False if cmd_txt == 'n' else True
if init_instr:
    if USE_ARDUINO and EMULATE_ASIC:
        sg.log.error('ASIC emulation enabled - instruments should NOT be initialized!')
    else:
        initialize_INSTR(interactive=not assume_defaults)

else:
    sg.log.debug('INSTR init skipped')

#Always initialize rails, if we've initialized the instruments that supply them.
if init_instr:
    initialize_Rails()


#Oscilloscope
#init_scope = (cmd_args.scope is not None) or (assume_defaults and USE_SCOPE)
#if not init_scope and USE_SCOPE == True:
#    cmd_txt = input("DEFAULT: Set up Oscilloscope. 'n' to Skip>>>")
#    init_scope = False if cmd_txt == 'n' else True
#if init_scope:
#    initialize_scope(interactive=not assume_defaults)
#
#else:
#    sg.log.debug('Scope init skipped')


# # # # # #

try:
    V_WARN_VOLTAGE
except NameError:
    print("ERROR: V_WARN_VOLTAGE not defined in ASIC config file.")
    print("       No automatic voltage checking will be performed.")
    V_WARN_VOLTAGE = None


try:
    #Get routines from file.
    with open(TARGET_ROUTINES_PY) as file:
        node = ast.parse(file.read())
        functions = [n for n in node.body if isinstance(n, ast.FunctionDef)]

    ROUTINES = [f for f in functions if f.name.startswith("ROUTINE")]

    #Write back routine # annotations to file. 
    with open(TARGET_ROUTINES_PY,"r") as read_file:
        routines_py_lines = read_file.readlines()

    annotation_update_needed = False
    new_routines_py_lines = []

    for i in range(len(routines_py_lines)):
        #For each line that looks like a routine,
        if routines_py_lines[i].startswith("def ROUTINE"):
            #Find which # routine is defined there.
            for j in range(len(ROUTINES)):
                if ROUTINES[j].name+"(" in routines_py_lines[i]:
                    annotation = f"#<<Registered w/ Spacely as ROUTINE {j}, call as ~r{j}>>\n"

                    new_routines_py_lines.append(annotation)

                    #If this annotation does not already exist on the previous line...
                    if i == 0 or annotation not in routines_py_lines[i-1]:
                        annotation_update_needed = True


        #Filter out the old annotations. If they are correct they should have been added above.
        if not routines_py_lines[i].startswith("#<<Registered w/ Spacely"):
            new_routines_py_lines.append(routines_py_lines[i])

    if annotation_update_needed:
        sg.log.debug(f"Updating annotations in {TARGET_ROUTINES_PY}...")
        with open(TARGET_ROUTINES_PY,"w") as write_file:
            for i in range(len(new_routines_py_lines)):
                write_file.write(new_routines_py_lines[i])

except FileNotFoundError as e:
    sg.log.warning("ASIC_Routines.py file could not be found, no routines were loaded.")
    print(e)
    ROUTINES = []
        
#Run On-startup routine
try:
    onstartup()
    sg.log.debug(f"Executed onstartup() code from {TARGET_ROUTINES_PY}")
except NameError:
    pass

#Auto-run command, if defined.
if cmd_args.r is not None:
    start_timestamp = datetime.now()
    routine_idx = int(cmd_args.r)
    sg.log.debug(f"Evaluating: {ROUTINES[routine_idx].name}()")
    eval(f"{ROUTINES[routine_idx].name}()")
    runtime = str(datetime.now().replace(microsecond=0) - start_timestamp.replace(microsecond=0))
    sg.log.info(f"This Routine took: {runtime}")


print("# Spacely ready to take commands (see \"help\" for details)")

#Command loop
while True:


    #Report any abnormal voltages
    if V_WARN_VOLTAGE is not None:
        auto_voltage_monitor()

    
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

    #sg.log.debug(f"Running: {cmd_txt}")
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
            initialize_NIFPGA()
        case 'ni_mon':
            report_NI(0.5)
        case 'ni_mon -a':
            report_NI(1, True)
        case 'ioshell':
            sg.pr.ioshell()
        case 'ashell':
            a = Analysis()
            a.ashell()
        case 'run_pattern':
            glue_waves = filedialog.askopenfilenames()
            sg.pr.run_pattern(glue_waves,outfile_tag="result")
        case 'gcshell':
            if 'DEFAULT_IOSPEC' in globals():
                print("** Starting gcshell with",DEFAULT_IOSPEC,"**")
                gc = GlueConverter(DEFAULT_IOSPEC)
            else:
                gc = GlueConverter()
            gc.gcshell()
        case 'fpgadbg':
            #Start a pattern runner instance, which will initialize the FPGA
            p = PatternRunner(sg.log,DEFAULT_IOSPEC, DEFAULT_FPGA_BITFILE_MAP)
            dbg = list(p._interface.values())[0]
            while True:
                x = dbg.interact()
                if type(x) == list:
                    print(abbreviate_list(x))
                else:
                    print(x)
                
        case 'lr':
            try:
                for r in range(len(ROUTINES)):
                    routine_name = ROUTINES[r].name.replace("ROUTINE","").replace("_"," ")
                    routine_docs = eval(f"{ROUTINES[r].name}.__doc__")
                    print(f"{r:<2} {routine_name: <33} -- {routine_docs}")
            except FileNotFoundError:
                sg.log.error(f"Could not find asic_config\\{TARGET}\\{TARGET}_Routines.py")
            
            print(f"(To add a new routine to this list, define a function in {TARGET_ROUTINES_PY} and give it a name starting with the word \"ROUTINE\".)")
            if len(ROUTINES) == 0:
                print("No routines to show!")
                    
                    
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
                    start_timestamp = datetime.now()
                    routine_idx = int(cmd_txt[2:].strip())

                    if routine_idx >= 0 and routine_idx < len(ROUTINES):
                        sg.log.debug(f"Evaluating: {ROUTINES[routine_idx].name}()")
                        eval(f"{ROUTINES[routine_idx].name}()")
                        runtime = str(datetime.now().replace(microsecond=0) - start_timestamp.replace(microsecond=0))
                        sg.log.info(f"This Routine took: {runtime}")
                    else:
                        sg.log.error(f"Invalid routine # {routine_idx} (out of range)")

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


#Intended exit path
exit_handler()
