import os
import re

import cocotb
import logging
from cocotb.runner import get_runner
from cocotbext.axi import AxiLiteBus, AxiLiteMaster
from cocotb.triggers import ClockCycles

from Master_Config import *
import Spacely_Globals as sg
from Spacely_Utils import *

from Spacely_Caribou import parse_mem_map


def add_hdl_path(filename):
    if filename.startswith("/"):
        #Assume this is already an absolute path
        return filename
    else:
        return os.path.join(os.getcwd(),"spacely-asic-config",sg.TARGET,"hdl",filename)


## Interal switch which instructs vanessa whether to output logs or not.
vanessa_verbose = True




def calculate_global_filenames():
    """Based on TARGET and TOP_MODULE global variables, generate the filenames in the global namespace which define where
       various necessary files will be found or stored. This is done in a function to make it easier to update the names
       after changing these global variables if you care to.
       """
    global COCOTB_ROUTINES_FILENAME, AUTOGEN_DIGITAL_TWIN_FILENAME, AUTOGEN_FIRMWARE_TWIN_FILENAME 
    global  DEFAULT_MEM_MAP_FILE, DEFAULT_SOURCES_FILE, DEFAULT_HDL_TOP_FILE, DEFAULT_HDL_TOP_FILE_FULL_PATH
    global  DEFAULT_FW_TOP_FILE, DEFAULT_FW_TOP_FILE_FULL_PATH, COCOTB_ENTRY_FN, DB_DUMP_STATEMENT
    global DEFAULT_HDL_TOP_FILE_SV, DEFAULT_HDL_TOP_FILE_V, DEFAULT_FW_TOP_FILE_SV, DEFAULT_FW_TOP_FILE_V
    
    COCOTB_ROUTINES_FILENAME = "_temp_cocotb_routines.py"
    AUTOGEN_DIGITAL_TWIN_FILENAME = "_temp_digital_twin_hdl_top.sv"
    AUTOGEN_FIRMWARE_TWIN_FILENAME = "_temp_digital_twin_fw_top.v"

    DEFAULT_MEM_MAP_FILE = os.path.join("spacely-asic-config",sg.TARGET,"hdl","mem_map.txt")
    if sg.HDL_SOURCES == None:
        DEFAULT_SOURCES_FILE = os.path.join("spacely-asic-config",sg.TARGET,"hdl","hdl_sources.txt")
    else:
        DEFAULT_SOURCES_FILE = os.path.join("spacely-asic-config",sg.TARGET,"hdl",sg.HDL_SOURCES)
    DEFAULT_HDL_TOP_FILE_SV = os.path.join("spacely-asic-config",sg.TARGET,"hdl",f"{sg.HDL_TOP_MODULE}.sv")
    DEFAULT_HDL_TOP_FILE_V = os.path.join("spacely-asic-config",sg.TARGET,"hdl",f"{sg.HDL_TOP_MODULE}.v")
    DEFAULT_FW_TOP_FILE_SV = os.path.join("spacely-asic-config",sg.TARGET,"hdl",f"{sg.FW_TOP_MODULE}.sv")
    DEFAULT_FW_TOP_FILE_V = os.path.join("spacely-asic-config",sg.TARGET,"hdl",f"{sg.FW_TOP_MODULE}.v")

    if os.path.exists(DEFAULT_HDL_TOP_FILE_SV):
        DEFAULT_HDL_TOP_FILE = DEFAULT_HDL_TOP_FILE_SV
    else:
        DEFAULT_HDL_TOP_FILE = DEFAULT_HDL_TOP_FILE_V

    DEFAULT_HDL_TOP_FILE_FULL_PATH = add_hdl_path(DEFAULT_HDL_TOP_FILE.split(os.sep)[-1])

    if os.path.exists(DEFAULT_FW_TOP_FILE_SV):
        DEFAULT_FW_TOP_FILE = DEFAULT_FW_TOP_FILE_SV
    else:
        DEFAULT_FW_TOP_FILE = DEFAULT_FW_TOP_FILE_V

    DEFAULT_FW_TOP_FILE_FULL_PATH = add_hdl_path(DEFAULT_FW_TOP_FILE.split(os.sep)[-1])

    COCOTB_ENTRY_FN ="""
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge
import cocotb
import os

import Spacely_Globals as sg
from Master_Config import *
from Spacely_Utils import *

@cocotb.test()
async def cocotb_entry_fn(dut):

    #Fix CWD
    # Get the directory of the current source file
    current_dir = os.path.dirname(os.path.abspath(__file__))

    # Set the working directory to the directory of the source file
    os.chdir(current_dir)

    # Retrieve text variables set before we entered this test.
    sg.load_pickle()

    # Set up those globals which are needed for Cocotb.
    log_term_out = liblog.HandleOutputStrategy.create_with_stderr()
    sg.log = liblog.AnsiTerminalLogger( # by default log to terminal and use ANSI
    log_term_out,
    max_level=liblog.levels.LOG_DEBUG if sg.VERBOSE else liblog.levels.LOG_INFO,
    ansi=True)

    sg.log.debug(">> (B.1) Entered cocotb environment, sg.log set up.")
    
    initialize_GlueConverter()

    #CaribouTwin_init = False

    if sg.TWIN_MODE > 0:
        sg.log.debug(">> (B.2) Initializing CaribouTwin")
        sg.INSTR["car"] = CaribouTwin(dut=dut)
        sg.pr = CaribouPatternRunner(sg.log, sg.gc, sg.INSTR["car"])
        
        #Start the AXI clock.
        sg.log.debug(">> (B.3) Starting AXI Clk")
        cocotb.start_soon(Clock(dut.AXI_ACLK, 10, units="ns").start())

        dut.AXI_ARESETN.value = 0
        await Timer(20, units="ns")
        dut.AXI_ARESETN.value = 1

        for _ in range(10):
            await RisingEdge(dut.AXI_ACLK)

    #Run onstartup() code if defined.
    try:
        await cocotb.external(onstartup)()
        sg.log.debug(">> (B.4) Completed onstartup() code.")
    except NameError:
        sg.log.debug(">> (B.4) No onstartup() code is defined.")

    #Run the requested routine.
    {routine_call}

"""

    DB_DUMP_STATEMENT = """initial begin
      
      $dumpfile("DB.vcd");
      $dumpvars(0,{sg.HDL_TOP_MODULE});
   end"""
    try:
        DB_DUMP_STATEMENT = DB_DUMP_STATEMENT.replace("{sg.HDL_TOP_MODULE}",sg.HDL_TOP_MODULE)
    except TypeError:
        #There will be a type error if sg.HDL_TOP_MODULE is not defined. This is fine,
        #we'll catch it later if anyone tries to actually run Cocotb LOL. 
        pass



#Run this function once on building the file.
calculate_global_filenames()

    
class SpacelyCocotbException(Exception):
    pass


# Returns:
# - hdl_source_macros: A dictionary of macros
# - source_lines: A list of lines defining the actual paths to files we want to include.
def parse_sources_file(filename):

    hdl_source_macros = {}
    source_lines = []
    
    try:
        with open(filename,'r') as r:
            source_lines_raw = [x.strip() for x in r.readlines()]
            

        for line in source_lines_raw:
            # a - Filter empty and commented lines.
            if not line or line.startswith("//"):
                continue

            # b - Recursively parse subfiles.
            if line.startswith("SOURCES "):
                line_toks = line.split()
                subfile_path = os.path.join("spacely-asic-config",sg.TARGET,"hdl",line_toks[1])
                if subfile_path != filename: #Ignore simple recursive calls
                    subfile_macros, subfile_source_lines = parse_sources_file(subfile_path)
                    source_lines.extend(subfile_source_lines)
                    hdl_source_macros.update(subfile_macros)
                    
            # c - Define Macros 
            elif line.startswith("DEF "):
                line_toks = line.split()
                hdl_source_macros[line_toks[1]] = line_toks[2]
                continue
            else:
                # d - For actual lines with paths, replace macros, then append to source_lines[]
                for key in hdl_source_macros.keys():
                    line = line.replace("$"+key, hdl_source_macros[key])
                source_lines.append(line)


    except FileNotFoundError:
        sg.log.error(f"Expected to find a list of HDL source files in {DEFAULT_SOURCES_FILE}, but this file was not found.")

    return hdl_source_macros, source_lines


# The goal: Make it so that you can run your routines on the ASIC RTL using Cocotb.
# The steps:
# (1) Produce a copy of your testbench with cocotb asynchronous style syntax.
# (2) Make sure that you are using Virtual Caribou. The Virtual Caribou will have routines that emulate an AXI master.
# (3) Run the routine. 

def run_routine_cocotb(routine_name):

    ## (0) Check that global variables are set.
    
    if sg.SIMULATOR is None:
        sg.log.error("You must define the variable sg.SIMULATOR in your Config.py file to run Cocotb.")
        return -1
        
    if sg.HDL_TOP_MODULE is None:
        sg.log.error("You must define the variable sg.HDL_TOP_MODULE in your Config.py file to run Cocotb.")
        return -1

    if sg.TWIN_MODE is None:
        sg.log.warning("Warning, using sg.TWIN_MODE=0 as a default.")
        TWIN_MODE = 0

    sg.log.debug(">> Preparing to run a Simulation w/ Cocotb")
    
    ## (1) Process hdl_sources.txt to obtain HDL sources.
    sg.log.debug(">> (A.1) Gathering HDL sources...")

    hdl_source_macros = {}
    source_lines = []

    hdl_source_macros, source_lines = parse_sources_file(DEFAULT_SOURCES_FILE)
    

    hdl_sources_with_path = [add_hdl_path(x) for x in source_lines]

    ## (2) If this is a Caribou Digital Twin run, then make sure the source file with the CaribouDigitalTwin in it is
    ##     replaced by the auto-generated top-level.

    if sg.TWIN_MODE > 0:

        sg.log.debug(">> (A.2) Creating Digital Twin HDL")

        # Check that HDL_TOP_MODULE can be found, and remove it from the hdl_sources.
        if not os.path.exists(DEFAULT_HDL_TOP_FILE):
            sg.log.error(f"When using sg.TWIN_MODE = {sg.TWIN_MODE}, your HDL top module {sg.HDL_TOP_MODULE} must be in {DEFAULT_HDL_TOP_FILE_SV} or {DEFAULT_HDL_TOP_FILE_V}")
            return -1

        if DEFAULT_HDL_TOP_FILE_FULL_PATH in hdl_sources_with_path:
            hdl_sources_with_path.remove(DEFAULT_HDL_TOP_FILE_FULL_PATH)

        hdl_sources_with_path.append(AUTOGEN_DIGITAL_TWIN_FILENAME)

        ### TWIN_MODE = 2 Only: Preprocess FW top level from Vivado
        if sg.TWIN_MODE == 2:

            if not os.path.exists(DEFAULT_HDL_TOP_FILE):
                sg.log.error(f"When using sg.TWIN_MODE = 2, your FW top module {sg.FW_TOP_MODULE} must be in {DEFAULT_FW_TOP_FILE_SV} or {DEFAULT_FW_TOP_FILE_V}")
                return -1

            if DEFAULT_FW_TOP_FILE_FULL_PATH in hdl_sources_with_path:
                hdl_sources_with_path.remove(DEFAULT_FW_TOP_FILE_FULL_PATH)

            hdl_sources_with_path.append(AUTOGEN_FIRMWARE_TWIN_FILENAME)

            aba, abn = axi_block_info_from_mem_map(DEFAULT_MEM_MAP_FILE)
            vanessa(DEFAULT_FW_TOP_FILE,aba, abn)

        ### Finally, preprocess HDL top level. 

        create_digital_twin_hdl()
        
        

    # (3) Create testbench

    sg.log.debug(f">> (A.3) Autogenerating Cocotb Test from {routine_name}...")
    cocotb_test_file = create_cocotb_test(routine_name)
    
    # (1) Set up the runner
    sg.log.debug(">> (A.4) Initializing simulator...")
    runner = get_runner(sg.SIMULATOR)

   
    
    runner.build(
        sources = hdl_sources_with_path,
        hdl_toplevel = sg.HDL_TOP_MODULE,
        clean=False,
        build_dir="cocotb_build_dir",
        build_args = sg.COCOTB_BUILD_ARGS, 
        timescale = ('1n','1p')
        )

    sg.log.debug(">> (A.5) Running the test...")

    # (2) Run the test

    # NOTE: COCOTB_LOG_LEVEL >= INFO is required to get result messages from cocotb.regression, which can tell you why your
    # test failed if it did, so it's kind of important to have at least this much logging.
    #COCOTB Log Levels: TRACE, DEBUG, INFO, WARNING, ERROR, CRITICAL

    sg.save_pickle()
    
    runner.test(hdl_toplevel=sg.HDL_TOP_MODULE,
                verbose=False,
                build_dir="cocotb_build_dir",
                extra_env={"COCOTB_LOG_LEVEL":"INFO"},
                test_module=cocotb_test_file.replace(".py",""))

    sg.clear_pickle()

AUTOGEN_COCOTB_WARNING_PYTHON="""#  !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
#  ! WARNING! This file was automatically generated by  !
#  ! Spacely_Cocotb. You don't need to modify it, and   !
#  ! if you do, your modifications will be overwritten! !
#  !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
"""

AUTOGEN_COCOTB_WARNING_SV = AUTOGEN_COCOTB_WARNING_PYTHON.replace("#","//")
    



def create_cocotb_test(routine_name):
    """Modifies a ROUTINE from TARGET_ROUTINES.py to be a valid Cocotb test."""

    ## (1) Read the original routines file.
    
    with open(sg.TARGET_ROUTINES_PY,'r') as read_file:
        routines_txt = read_file.read()

    #Remember that TARGET_SUBROUTINES_PY is a list.
    subroutines_txt = ""
    for subroutine_file in sg.TARGET_SUBROUTINES_PY:
        with open(subroutine_file,'r') as read_file:
            subroutines_txt = subroutines_txt + "\n\n" + read_file.read()

    ## (2) Find the specific routine we are tasked to run.
    USER_ROUTINE_IS_ASYNC = False
    
    start_idx = routines_txt.find(f"\ndef {routine_name}")
    if start_idx == -1:
        start_idx = routines_txt.find(f"\nasync def {routine_name}")

        if start_idx == -1:
            sg.log.error("Could not find the requested routine in create_cocotb_test.")
            return -1
        else:
            USER_ROUTINE_IS_ASYNC = True

    #Start searching for the end_idx after the start_idx
    idx = start_idx +1
    while True:
        #Each iteration of the loop, find the next newline.
        idx = routines_txt.find("\n",idx+1)
        #If we get to the end of the file, just return -1
        if idx == -1 or idx + 1 > len(routines_txt):
            end_idx = -1
            break
        #Otherwise check if the next character is non-whitespace and if so, return this index.
        if routines_txt[idx+1] not in ' \t': 
            end_idx = idx
            break

    
    this_routine_txt = routines_txt[start_idx:end_idx]


    ## (3) Add the entry function.

    if f"def {routine_name}(dut" in this_routine_txt:
        routine_args = "dut"
    else:
        routine_args = ""
    
    if USER_ROUTINE_IS_ASYNC:
        entry_fn = COCOTB_ENTRY_FN.replace("{routine_call}",f"await {routine_name}({routine_args})")
    else:
        entry_fn = COCOTB_ENTRY_FN.replace("{routine_call}",f"await cocotb.external({routine_name})({routine_args})")
    
    
    this_routine_txt = entry_fn + "\n" + this_routine_txt


    ## (4) Update the routines txt

    routines_txt = AUTOGEN_COCOTB_WARNING_PYTHON + subroutines_txt + "\n\n" + routines_txt.replace(routines_txt[start_idx:end_idx],this_routine_txt) 

    #routines_txt = routines_txt.replace("\nfrom","##")
    #routines_txt = routines_txt.replace("\nimport","##")

    ## (5) Write to file
    
    temp_file = COCOTB_ROUTINES_FILENAME
    
    with open(temp_file,'w') as write_file:
        write_file.write(routines_txt)

    return temp_file





##############################
# Caribou Digital Twin Class #
##############################

#AXI signal definitions which should be added at the top, for Cocotb to connect to.
#!! NOTE !! the signal names need to be in lowercase for Cocotb to recognize them. 
AXI_SIGNALS_TOP = """
    input wire [10 : 0]                       M{n}_AXI_awaddr,
    input wire [2 : 0] 			      M{n}_AXI_awprot,
    input wire 				      M{n}_AXI_awvalid,
    output wire 			      M{n}_AXI_awready,
    input wire [31 : 0]                       M{n}_AXI_wdata,
    input wire [3 : 0]                        M{n}_AXI_wstrb,
    input wire 				      M{n}_AXI_wvalid,
    output wire 			      M{n}_AXI_wready,
    output wire [1 : 0] 		      M{n}_AXI_bresp,
    output wire 			      M{n}_AXI_bvalid,
    input wire 				      M{n}_AXI_bready,
    input wire [10 : 0]                       M{n}_AXI_araddr,
    input wire [2 : 0] 			      M{n}_AXI_arprot,
    input wire 				      M{n}_AXI_arvalid,
    output wire 			      M{n}_AXI_arready,
    output wire [31 : 0]                      M{n}_AXI_rdata,
    output wire [1 : 0] 		      M{n}_AXI_rresp,
    output wire 			      M{n}_AXI_rvalid,
    input wire 				      M{n}_AXI_rready"""


AXI_SIGNALS_TOP_NONANSI_1 = """ 
     M{n}_AXI_awaddr, 
     M{n}_AXI_awprot,  
     M{n}_AXI_awvalid,
     M{n}_AXI_awready,
     M{n}_AXI_wdata,
     M{n}_AXI_wstrb,
     M{n}_AXI_wvalid,
     M{n}_AXI_wready,
     M{n}_AXI_bresp,
     M{n}_AXI_bvalid,
     M{n}_AXI_bready,
     M{n}_AXI_araddr,
     M{n}_AXI_arprot,
     M{n}_AXI_arvalid,
     M{n}_AXI_arready,
     M{n}_AXI_rdata,
     M{n}_AXI_rresp,
     M{n}_AXI_rvalid,
     M{n}_AXI_rready
"""

AXI_SIGNALS_TOP_NONANSI_2 = """
    input wire [10 : 0]                       M{n}_AXI_awaddr;
    input wire [2 : 0] 			      M{n}_AXI_awprot;
    input wire 				      M{n}_AXI_awvalid;
    output wire 			      M{n}_AXI_awready;
    input wire [31 : 0]                       M{n}_AXI_wdata;
    input wire [3 : 0]                        M{n}_AXI_wstrb;
    input wire 				      M{n}_AXI_wvalid;
    output wire 			      M{n}_AXI_wready;
    output wire [1 : 0] 		      M{n}_AXI_bresp;
    output wire 			      M{n}_AXI_bvalid;
    input wire 				      M{n}_AXI_bready;
    input wire [10 : 0]                       M{n}_AXI_araddr;
    input wire [2 : 0] 			      M{n}_AXI_arprot;
    input wire 				      M{n}_AXI_arvalid;
    output wire 			      M{n}_AXI_arready;
    output wire [31 : 0]                      M{n}_AXI_rdata;
    output wire [1 : 0] 		      M{n}_AXI_rresp;
    output wire 			      M{n}_AXI_rvalid;
    input wire 				      M{n}_AXI_rready;"""



#AXI signal connections which should be added to each module.
AXI_SIGNALS_MOD = """.S_AXI_ACLK(AXI_ACLK),
        .S_AXI_ARADDR(M{n}_AXI_araddr[10:0]),
        .S_AXI_ARESETN(AXI_ARESETN),
        .S_AXI_ARPROT(M{n}_AXI_arprot),
        .S_AXI_ARREADY(M{n}_AXI_arready),
        .S_AXI_ARVALID(M{n}_AXI_arvalid),
        .S_AXI_AWADDR(M{n}_AXI_awaddr[10:0]),
        .S_AXI_AWPROT(M{n}_AXI_awprot),
        .S_AXI_AWREADY(M{n}_AXI_awready),
        .S_AXI_AWVALID(M{n}_AXI_awvalid),
        .S_AXI_BREADY(M{n}_AXI_bready),
        .S_AXI_BRESP(M{n}_AXI_bresp),
        .S_AXI_BVALID(M{n}_AXI_bvalid),
        .S_AXI_RDATA(M{n}_AXI_rdata),
        .S_AXI_RREADY(M{n}_AXI_rready),
        .S_AXI_RRESP(M{n}_AXI_rresp),
        .S_AXI_RVALID(M{n}_AXI_rvalid),
        .S_AXI_WDATA(M{n}_AXI_wdata),
        .S_AXI_WREADY(M{n}_AXI_wready),
        .S_AXI_WSTRB(M{n}_AXI_wstrb),
        .S_AXI_WVALID(M{n}_AXI_wvalid)"""

#Necessary connections to pass through AXI bus M{n} to the top level.
AXI_PASSTHROUGH = """,.M{n}_AXI_araddr(M{n}_AXI_araddr[10:0]),
        .M{n}_AXI_arprot(M{n}_AXI_arprot),
        .M{n}_AXI_arready(M{n}_AXI_arready),
        .M{n}_AXI_arvalid(M{n}_AXI_arvalid),
        .M{n}_AXI_awaddr(M{n}_AXI_awaddr[10:0]),
        .M{n}_AXI_awprot(M{n}_AXI_awprot),
        .M{n}_AXI_awready(M{n}_AXI_awready),
        .M{n}_AXI_awvalid(M{n}_AXI_awvalid),
        .M{n}_AXI_bready(M{n}_AXI_bready),
        .M{n}_AXI_bresp(M{n}_AXI_bresp),
        .M{n}_AXI_bvalid(M{n}_AXI_bvalid),
        .M{n}_AXI_rdata(M{n}_AXI_rdata),
        .M{n}_AXI_rready(M{n}_AXI_rready),
        .M{n}_AXI_rresp(M{n}_AXI_rresp),
        .M{n}_AXI_rvalid(M{n}_AXI_rvalid),
        .M{n}_AXI_wdata(M{n}_AXI_wdata),
        .M{n}_AXI_wready(M{n}_AXI_wready),
        .M{n}_AXI_wstrb(M{n}_AXI_wstrb),
        .M{n}_AXI_wvalid(M{n}_AXI_wvalid)"""



def create_digital_twin_hdl():
    """Edit the user's hdl_top to insert AXI interfaces.""" 
    #sg.log.debug("Setting up digital twin HDL.")
    
    with open(DEFAULT_HDL_TOP_FILE,'r') as read_file:
        hdl_txt = read_file.read()

    hdl_txt = implement_digital_twin_axi_interfaces(hdl_txt)
    
    hdl_txt = hdl_txt.replace("endmodule",DB_DUMP_STATEMENT+"\nendmodule")

    with open(AUTOGEN_DIGITAL_TWIN_FILENAME,'w') as write_file:
        write_file.write(hdl_txt)




def implement_digital_twin_axi_interfaces(hdl_txt):
    """Given a string representing a .sv file, it will instantiate 
    AXI interfaces at all the blocks which are supposed to have them.
    """

    # Initialize counter and dictionary for mappings
    counter = 0
    hex_dict = {}

    # Regular expression pattern to match AXI_INTERFACE comments with hex numbers,
    # followed by optional whitespace and an optional next character (captured in group 2)
    pattern_iface =    re.compile(r'/\*AXI_INTERFACE\((0x[0-9A-Fa-f]+)\)\*/(\s*)(\S?)')
    pattern_passthru = re.compile(r'/\*AXI_PASSTHROUGH\(([0-9]+)\)\*/(\s*)(\S?)')
    
    # Replace each AXI_INTERFACE comment and store the mappings
    def replacer_iface(match):
        nonlocal counter
        hex_value = match.group(1)
        whitespace = match.group(2)
        next_char = match.group(3)
        hex_dict[counter] = hex_value
        replacement = AXI_SIGNALS_MOD.replace("{n}",str(counter))
        counter += 1

        # Determine if a trailing comma is needed
            
        if next_char != ')':
            replacement+=","

        # Add back in the whitespace / next_char.
        return replacement + whitespace + next_char


    def replacer_passthru(match):
        nonlocal counter
        num_ifaces = int(match.group(1))
        whitespace = match.group(2)
        next_char = match.group(3)
        counter += num_ifaces
        
        replacement = ".AXI_ACLK(AXI_ACLK),.AXI_ARESETN(AXI_ARESETN)"
        for i in range(num_ifaces):
            replacement += AXI_PASSTHROUGH.replace("{n}",str(i))
            #if i < num_ifaces - 1:
            #    replacement +=",\n"

        if next_char != ')':
            replacement +=","

        return replacement + whitespace + next_char
        

    
    # Add AXI interfaces to each module.
    hdl_txt = pattern_iface.sub(replacer_iface, hdl_txt)

    # Add AXI Passthroughs if necessary
    hdl_txt = pattern_passthru.sub(replacer_passthru, hdl_txt)

    # Add AXI signals to the interface of the top module.
    new_module_txt = f"{sg.HDL_TOP_MODULE} (input logic AXI_ACLK,\n input logic AXI_ARESETN"
    
    for i in range(counter):
        new_module_txt += ",\n"+AXI_SIGNALS_TOP.replace("{n}",str(i))

    hdl_txt = re.sub(fr'{sg.HDL_TOP_MODULE}\s*\(', new_module_txt, hdl_txt)


    new_header_txt = AUTOGEN_COCOTB_WARNING_SV

    for key in hex_dict.keys():
        new_header_txt += "//axi:"+str(key)+","+str(hex_dict[key])+"\n"
    
    hdl_txt = new_header_txt + hdl_txt
    
    if counter == 0:
        sg.log.error("Didn't find any blocks which have AXI interfaces! Did you forget to add comments, or is the HDL_TOP file wrong?")
        
    # Return the text after modification.
    return hdl_txt





class CaribouTwin(Source_Instrument):


    def __init__(self,  mem_map_file=DEFAULT_MEM_MAP_FILE, dut=None):
        """Creates a CaribouTwin Object. 
           Parameters:
        hdl_top_file -- HDL file which is the top (including Caribou and ASIC RTL)
        mem_map_file -- mem_map.txt file associated with the Caribou FW. 

        """
        
        # The CaribouTwin has an individual AXI interface for each block.

        # axi_block_addr keeps track of which block address applies to each
        # numbered AXI interface.
        # Key = (int) # corresponding to AXI interface.
        # Val = Hex block address. 
        self.axi_block_addr = {}

        # axi is a list of the axi interfaces by number.
        self.axi = []

        # Dictionaries of voltages and currents to implement the get/set interface.
        self.voltages = {}
        self.currents = {}

        #Dictionary that will map memory fields to addresses / AXI interfaces.
        self.mem_map = {}

        self.debug_memory = False
  
        sg.log.debug(">>  Setting up AXI Interfaces based on mem_map.txt")
        self._setup_axi(mem_map_file)
        
        if dut is not None:
            sg.log.debug(">>  Connecting AXI Interfaces to dut.")
            self.connect_dut(dut)

        #self._print_data()


    def _print_data(self):
        """Print the data structures stored in this object, for debug purposes."""
        print("AXI BLOCK ADDRESSES")
        print(self.axi_block_addr)
        print("AXI INTERFACES")
        print(self.axi)
        print("MEMORY MAPS")
        print(self.mem_map)

    def _setup_axi(self, mem_map_file):
        """Get mem_map information from file, and use it to map each field to an Axi Interface."""


        # #############################################
        # # Step 0: Get AXI Interfaces from HDL file. #
        # #############################################

        self.axi_block_addr, self.axi_block_num = axi_block_info_from_mem_map(mem_map_file)
        
        #with open(AUTOGEN_DIGITAL_TWIN_FILENAME,'r') as read_file:
        #    lines = read_file.readlines()

        #for line in lines[5:]:
         #   if line.startswith("//axi:"):
         #       toks = line.replace("//axi:","").strip().split(",")
         #       self.axi_block_addr[int(toks[0])] = toks[1]
         #   else:
         #       break

        axi_interfaces = list(self.axi_block_addr.keys())

        if len(axi_interfaces) == 0:
            sg.log.error("No AXI interfaces found in Digital Twin HDL file!")
            return -1
        
       

        # ########################################
        # # Step 1: Parse mem_map to dictionary. #
        # ########################################
        #
        # Structure of the dictionary (from Spacely_Caribou.py)
        #
        #   mem_map["reg_name"] = {"IP Base Addr" : 0x400000000
        #                          "Register Offs": (int)
        #                          "Mask"         : (int)
        #                          "Readable"     : (bool)
        #                          "Writeable"    : (bool)}
        #

        with open(mem_map_file,'r') as read_file:
            lines = read_file.readlines()
        
        result = parse_mem_map(lines)

        if result == -1:
            sg.log.error("CaribouTwin memory map read failed due to previous parse error!")
            return -1

        self.mem_map = result


        # #############################################################
        # # Step 2: Assign Digital Twin Interfaces for each register. #
        # #############################################################

        for i in axi_interfaces:
            block_addr = int(self.axi_block_addr[i],16)
            block_num  = self.axi_block_num[i]

            for field in self.mem_map.keys():
                
                #For fields which fall into this block:
                this_field_block_addr = self.mem_map[field]["IP Base Addr"]
                if this_field_block_addr == block_addr:
                    
                    if "TwinInterface" in self.mem_map[field]:
                        existing_iface = self.mem_map[field]["TwinInterface"]
                        sg.log.error(f"Mem map field {field} falls into block {block_addr} which is mapped to Digital Twin Interface {i}, but it is already assigned to Interface {existing_iface}.")

                    self.mem_map[field]["TwinInterface"] = block_num 

        #Go back at the end and check we actually assigned an interface for every field. 
        for field in self.mem_map.keys():
            if "TwinInterface" not in self.mem_map[field]:
                sg.log.warning(f"Did not assign a Digital Twin Interface for {field}.")
            


    



    def connect_dut(self, dut):
        self.dut = dut

        sg.log.debug(f"Connecting CaribouTwin to dut object {dut}")

        axi_interfaces = list(self.axi_block_num.values())

        if len(axi_interfaces) == 0:
            sg.log.error("AXI Interfaces must be created in HDL_TOP before running connect_dut()")

        for i in range(len(axi_interfaces)):
            self.axi.append(AxiLiteMaster(AxiLiteBus.from_prefix(dut, f"M{i}_AXI"),
                                          dut.AXI_ACLK,
                                          dut.AXI_ARESETN,
                                          reset_active_level=False))

            self.axi[-1].write_if.log.setLevel(logging.WARNING)
            self.axi[-1].read_if.log.setLevel(logging.WARNING)
            

    ######################################
    # Digital Twin Interaction Functions #
    ######################################


    def set_memory(self, mem_name, value):
        if self.debug_memory:
            sg.log.debug(f"<AXI> Write {mem_name}: {value}")
        try:
            iface_num = self.mem_map[mem_name]['TwinInterface']
            base_addr = self.mem_map[mem_name]['IP Base Addr']
            reg_offs  = self.mem_map[mem_name]['Register Offs']
            addr = base_addr + reg_offs
        except KeyError:
            raise SpacelyCocotbException(f"Unrecognized AXI register {mem_name}")

        try:
            cocotb.function(self.axi[iface_num].write_dword)(reg_offs,value, byteorder='little')
        except IndexError:
            sg.log.error(f"CaribouTwin: Tried to access axi interface #{iface_num}, but it doesn't exist. Only {len(self.axi)} axi interfaces have been initialized.")
            return -1

    def get_memory(self, mem_name):
        try:
            iface_num = self.mem_map[mem_name]['TwinInterface']
            base_addr = self.mem_map[mem_name]['IP Base Addr']
            reg_offs  = self.mem_map[mem_name]['Register Offs']
            addr = base_addr + reg_offs
        except KeyError:
            raise SpacelyCocotbException(f"Unrecognized AXI register {mem_name}")

        try:
            x = cocotb.function(self.axi[iface_num].read_dword)(reg_offs)

        except IndexError:
            sg.log.error(f"CaribouTwin: Tried to access axi interface #{iface_num}, but it doesn't exist. Only {len(self.axi)} axi interfaces have been initialized.")
            x = -1

        if self.debug_memory:
            sg.log.debug(f"<AXI> Read {mem_name}: {x}")
        return x


    async def dly_min_axi_clk_async(self,clk_cycles):
        await ClockCycles(self.dut.AXI_ACLK,clk_cycles)
    
    def dly_min_axi_clk(self, clk_cycles):
        """Ensure a delay of a minimum number of AXI clock cycles."""
        cocotb.function(self.dly_min_axi_clk_async)(clk_cycles)

    def set_voltage(self, channel, nominal_voltage, current_limit):
        self.voltages[channel] = nominal_voltage
      
    def set_current(self, channel, nominal_current, voltage_limit):
        self.currents[channel] = nominal_current

    def get_voltage(self, channel):
        return self.voltages[channel]
      
    def get_current(self, channel):
        return self.currents[channel]
        
    def set_output_on(self, channel):
        pass
        
    def set_output_off(self, channel):
        pass

    def disable_all_pwr_rails(self):
        pass

    def init_car(self):
        sg.log.debug("Ran Caribou.init_car() (no effect in digital twin simulation)")

    def check_init_car(self):
        pass

    def auto_set_axi_registers(self, module_list):
        pass

    def set_axi_registers(self, regmap):
        pass

    def set_input_cmos_level(self, voltage):
        pass

    def set_output_cmos_level(self, vltage):
        pass

    def close(self):
        pass





    
def vlog(print_str):
    global vanessa_verbose
    if vanessa_verbose:
        print("[vanessa] ",print_str)


def first_word_non_reserved(input_string):
    """Checks an input string for the first word, and returns true if it is not a reserved keyword, 
    otherwise False."""

    RESERVED_KWORDS = ["wire", "input", "output", "logic"]

    # Extract the first word-like sequence (non-whitespace characters)
    match = re.match(r'\s*(\S+)', input_string)
    if match:
        first_word = match.group(1)
        #print("first_word:",first_word)
        # Check if the first word contains only alphanumeric characters and is not "wire"
        if re.match(r'^\w+$', first_word) and first_word.lower() not in RESERVED_KWORDS:
            #print("True!")
            return True
    return False

def get_signal_connection(string, sig_name):
    # Create a regex pattern for the keyword followed by parentheses
    pattern = fr'{re.escape(sig_name)}\s*\(([^)]+)\)'
    #print("pattern: ", pattern)
    #print("string: ", string)
    match = re.search(pattern, string)
    if match:
        # Return the text inside the parentheses
        return match.group(1)
    return None

def replace_axi_prefix(string, old_prefix, new_prefix):
    """Replaces the AXI prefix in a signal connection, while also making sure the remainder of the signal 
    connection is in lowercase for the benefit of Cocotb."""
    # Create a regex pattern for the substring in parentheses starting with the old prefix
    pattern = fr'\((\s*{re.escape(old_prefix)}[^\)]*)\)'
    
    # Define a replacement function for the matched text
    def replacement(match):
        # Extract the matched substring and remove the old prefix
        old_text = match.group(1)
        without_old_prefix = old_text[len(old_prefix):].strip()
        # Build the new substring with the new prefix and lowercase text
        return f'({new_prefix}{without_old_prefix.lower()})'
    
    # Perform the replacement using re.sub
    return re.sub(pattern, replacement, string)


def axi_block_info_from_mem_map(mem_map_file):
    """The function axi_block_info_from_mem_map() parses the mem_map.txt file and returns two dictionaries:
- axi_block_addr maps block names to hex addresses
- axi_block_num  maps block names to AXI interface nums.

The mem_map.txt file must contain the optional annotations which give the name of the block with each AXI address."""

    axi_block_addr = {}
    axi_block_num = {}
    idx = 0

    with open(mem_map_file,'r') as read_file:
        lines = read_file.readlines()

    for line in lines:

        line = line.strip()

        #Skip blank lines
        if len(line) == 0:
            continue

        #Skip commented lines
        if line.startswith("//"):
            continue

        #Base Address Line
        if line.startswith("*BASE"):
            toks = line.split()

            if len(toks) != 3:
                sg.log.error("mem_map.txt parse error! In order to extract AXI block address table, every *BASE line should have a single comment after the base address giving the RTL instance which uses that address, for example \"*BASE 0x400000000 myBlock1\". The following line does not fit this format:\n"+line)
                return -1
            
            base_address_token = toks[1]
            instance_name = toks[2]

            if instance_name.startswith("//"):
                instance_name = instance_name[2:]

            axi_block_addr[instance_name] = base_address_token
            axi_block_num[instance_name] = idx
            idx = idx + 1

    return (axi_block_addr, axi_block_num)


def vanessa(vivado_netlist_file, axi_block_addr, axi_block_num):
    """vanessa (Vivado Netlist Examination for Spacely Simulation) parses a simulation netlist that
       is autogenerated from Vivado and prepares it for use in a Cocotb simulation environment.
       Vanessa also sounds like the kind of name you'd give to a futuristic evil AI, but YMMV.
       """
    
    vlog(f"Reading Vivado simulation netlist from: {vivado_netlist_file}")
    
    with open(vivado_netlist_file,'r') as read_file:
        netlist_lines = read_file.readlines()


    lines_to_keep = [True]*len(netlist_lines)

    #index of line we are currently evaluating.
    i = 0

    while True:
        while not netlist_lines[i].startswith("module "):
            i += 1

        top_name = netlist_lines[i].split()[-1]
        start_top_idx = i

        if top_name == sg.FW_TOP_MODULE:
            vlog(f"Found top module {top_name}")
            break
        else:
            vlog(f"Found a module named {top_name}, skipping because it is not sg.FW_TOP_MODULE={sg.FW_TOP_MODULE}")
            i += 1

    j = i
    while not netlist_lines[j].startswith("endmodule"):
        j += 1
        # Strip Xilinx directives which are enclosed in (* *)
        if netlist_lines[j].strip().startswith("(*"):
            # Remove all occurrences of text enclosed in (* *)
            netlist_lines[j] = re.sub(r'\(\*.*?\*\)', '', netlist_lines[j])

    end_top_idx = j

    vlog(f"  Lines {start_top_idx}~{end_top_idx} belong to the top module.")

    i +=1
    
    MODULES_TO_DISCARD = ["ps8_0_axi_periph", "zynq_ultra_ps_e_0", "rst_ps8_0"]

    # Loop to find all of the modules under the top module.
    i = start_top_idx;
    while i < end_top_idx-1:
        i += 1
        
        while not first_word_non_reserved(netlist_lines[i]) and i < end_top_idx-1:
            i += 1

        if i == end_top_idx - 1:
            break
            
        try:
            line_toks = netlist_lines[i].split()
            mod_type = line_toks[0]
            mod_name = line_toks[1]
        except IndexError:
            sg.log.error(f"Failed to parse this line as a module instantiation '{netlist_lines[i]}'")
            return -1
        start_mod_idx = i

        vlog(f"Found a module named {mod_name} of type {mod_type}.")

        

        j = i
        while not ");" in  netlist_lines[j]:
            j += 1

        end_mod_idx = j

        vlog(f"  Lines {start_mod_idx}~{end_mod_idx} belong to this module.")

        j = i
        aclk_connection = None
        reset_connection = None
        arvalid_connection = None
        axi_prefix = None

        # If this is one of the modules we are supposed to discard, discard it.

        discard_this = False
        
        for x in MODULES_TO_DISCARD:
            if x in mod_type:
                discard_this = True
                break

        if discard_this:
            vlog(f"  Discarding this module because it is of type {x}")
            for j in range(start_mod_idx, end_mod_idx+1):
                lines_to_keep[j] = False
            continue

        # Otherwise, figure out all of its AXI signal connections.

        if mod_name not in axi_block_addr.keys():
            vlog("  No AXI block address is listed for this module.")
        else:
            block_addr = axi_block_addr[mod_name]
            block_num = axi_block_num[mod_name]
            vlog(f"  This module should have an AXI connection w/ address = {block_addr}")

            j = start_mod_idx
            while j < end_mod_idx:
                j += 1
                
                if ".S_AXI_ACLK" in netlist_lines[j]:
                    aclk_connection = get_signal_connection(netlist_lines[j],".S_AXI_ACLK")
                    vlog(f"  AXI ACLK is connected to {aclk_connection}")

                elif ".s_axi_aclk" in netlist_lines[j]:
                    aclk_connection = get_signal_connection(netlist_lines[j],".s_axi_aclk")
                    vlog(f"  AXI ACLK is connected to {aclk_connection}")

                if ".S_AXI_ARESETN" in netlist_lines[j]:
                    reset_connection = get_signal_connection(netlist_lines[j],".S_AXI_ARESETN")
                    vlog(f"  AXI ARESETN is connected to {reset_connection}")

                elif ".s_axi_aresetn" in netlist_lines[j]:
                    reset_connection = get_signal_connection(netlist_lines[j],".s_axi_aresetn")
                    vlog(f"  AXI ARESETN is connected to {reset_connection}")

                if ".S_AXI_ARVALID" in netlist_lines[j]:
                    arvalid_connection = get_signal_connection(netlist_lines[j],".S_AXI_ARVALID")
                    vlog(f"  AXI ARVALID is connected to {arvalid_connection}")

                elif ".s_axi_arvalid" in netlist_lines[j]:
                    arvalid_connection = get_signal_connection(netlist_lines[j],".s_axi_arvalid")
                    vlog(f"  AXI ARVALID is connected to {arvalid_connection}")

                if arvalid_connection is not None:
                    if arvalid_connection.endswith("ARVALID"):
                        axi_prefix = arvalid_connection.replace("ARVALID","")
                        vlog(f"  Inferring that AXI prefix is: {axi_prefix}")
                    else:
                        vlog("!!Error!! Couldn't infer an AXI prefix from this connection :(")
        
            if axi_prefix is None or aclk_connection is None or reset_connection is None:
                #If we fail to make a connection, that's a big enough deal to escalate to Spacely.
                sg.log.warning("Warning: Spacely-Cocotb failed to make an AXI connection to a block, set vanessa_verbose=True for details.")
                vlog("Error! There is an incomplete AXI connection to this block, couldn't figure out what to do with it.")
                vlog(f"    -> aclk_connection is {aclk_connection}")
                vlog(f"    -> reset_connection is {reset_connection}")
                vlog(f"    -> axi_prefix is {axi_prefix}")
            else:
                #axi_interface_order.append(mod_name)
                #axi_idx = len(axi_interface_order) - 1
                vlog(f"  Replacing old AXI interface with connection to generic M{block_num}_AXI...")
                for j in range(start_mod_idx, end_mod_idx+1):
                    netlist_lines[j] = netlist_lines[j].replace(f"({aclk_connection})","(AXI_ACLK)")
                    netlist_lines[j] = netlist_lines[j].replace(f"({reset_connection})","(AXI_ARESETN)")                  
                    if f"({axi_prefix}" in netlist_lines[j]:
                         netlist_lines[j] = replace_axi_prefix(netlist_lines[j],axi_prefix, f"M{block_num}_AXI_")
 



    ## Add I/Os to the top level (TBA)

    vlog("Adding new I/O connections...")
    
    #netlist_lines[start_top_idx] = netlist_lines[start_top_idx].replace(top_name, "CaribouDigitalTwinTop")
    
    # Add AXI signals to the interface of the top module.
    new_io_txt_1 = "(AXI_ACLK,\n  AXI_ARESETN"
    new_io_txt_2 = "input wire AXI_ACLK; \n input wire AXI_ARESETN; \n"
    
    for i in axi_block_num.values(): #range(len(axi_interface_order)):
        new_io_txt_1 += ",\n"+AXI_SIGNALS_TOP_NONANSI_1.replace("{n}",str(i))

    for i in axi_block_num.values(): #range(len(axi_interface_order)):
        new_io_txt_2 += AXI_SIGNALS_TOP_NONANSI_2.replace("{n}",str(i))

    netlist_lines[start_top_idx+1] = netlist_lines[start_top_idx+1].replace("(",new_io_txt_1+",\n")
        
    j = start_top_idx
    while j < end_top_idx:
        if ");" in netlist_lines[j]:
            break
        j += 1

    #Add the second half of the non-ansi port declarations.
    netlist_lines[j] = netlist_lines[j].replace(");",");\n"+new_io_txt_2)

    lines_to_write = [item for item, condition in zip(netlist_lines, lines_to_keep) if condition]

    vlog("Generating header text...")

    new_header_txt = AUTOGEN_COCOTB_WARNING_SV

    for key in axi_block_addr.keys():
        block_addr = axi_block_addr[key]
        idx = axi_block_num[key] #axi_interface_order.index(key)
        new_header_txt += "//axi:"+str(idx)+","+str(block_addr)+"\n"

    with open(AUTOGEN_FIRMWARE_TWIN_FILENAME,'w') as write_file:
        write_file.write(new_header_txt)
        write_file.writelines(lines_to_write)
