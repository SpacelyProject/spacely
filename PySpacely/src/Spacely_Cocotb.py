import os
import re

import cocotb
from cocotb.runner import get_runner
from cocotbext.axi import AxiLiteBus, AxiLiteMaster

from Master_Config import *
import Spacely_Globals as sg
from Spacely_Utils import *

from Spacely_Caribou import parse_mem_map


COCOTB_ROUTINES_FILENAME = "_temp_cocotb_routines.py"
AUTOGEN_DIGITAL_TWIN_FILENAME = "_temp_digital_twin_hdl_top.sv"

DEFAULT_MEM_MAP_FILE = os.path.join("spacely-asic-config",TARGET,"hdl","mem_map.txt")
DEFAULT_SOURCES_FILE = os.path.join("spacely-asic-config",TARGET,"hdl","hdl_sources.txt")
DEFAULT_DIGITAL_TWIN_TOP_FILE = os.path.join("spacely-asic-config",TARGET,"hdl","CaribouDigitalTwinTop.sv")


COCOTB_ENTRY_FN ="""
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge
import cocotb

@cocotb.test()
async def cocotb_entry_fn(dut):

    #Fix CWD
    # Get the directory of the current source file
    current_dir = os.path.dirname(os.path.abspath(__file__))

    # Set the working directory to the directory of the source file
    os.chdir(current_dir)


    # Set up those globals which are needed for Cocotb.
    log_term_out = liblog.HandleOutputStrategy.create_with_stderr()
    sg.log = liblog.AnsiTerminalLogger( # by default log to terminal and use ANSI
    log_term_out,
    max_level=liblog.levels.LOG_DEBUG if VERBOSE else liblog.levels.LOG_INFO,
    ansi=True)

    sg.log.debug(">> (B.1) Entered cocotb environment, sg.log set up.")
    
    initialize_GlueConverter()

    CaribouTwin_init = False

    for inst in INSTR:
        if INSTR[inst]["type"] == "Caribou":
            sg.log.debug(">> (B.2) Initializing CariboutTwin")
            sg.INSTR[inst] = CaribouTwin(dut=dut)
            sg.pr = CaribouPatternRunner(sg.log, sg.gc, sg.INSTR[inst])
            CaribouTwin_init = True
            break


    #Start the AXI clock.
    sg.log.debug(">> (B.3) Starting AXI Clk")
    cocotb.start_soon(Clock(dut.AXI_ACLK, 10, units="ns").start())

    dut.AXI_ARESETN.value = 0
    await Timer(20, units="ns")
    dut.AXI_ARESETN.value = 1

    for _ in range(10):
        await RisingEdge(dut.AXI_ACLK)

    #Run the requested routine.
    await cocotb.external({routine_name})({routine_args})

"""

DB_DUMP_STATEMENT = """initial begin
      
      $dumpfile("DB.vcd");
      $dumpvars(0,CaribouDigitalTwinTop);
   end"""


class SpacelyCocotbException(Exception):
    pass

# The goal: Make it so that you can run your routines on the ASIC RTL using Cocotb.
# The steps:
# (1) Produce a copy of your testbench with cocotb asynchronous style syntax.
# (2) Make sure that you are using Virtual Caribou. The Virtual Caribou will have routines that emulate an AXI master.
# (3) Run the routine. 

def run_routine_cocotb(routine_name):
    global SIMULATOR, HDL_TOP_MODULE

    ## (0) Check that global variables are set.
    
    if SIMULATOR is None:
        sg.log.error("You must define the variable SIMULATOR in your Config.py file to run Cocotb.")
        return -1
        
    if HDL_TOP_MODULE is None:
        sg.log.error("You must define the variable HDL_TOP_MODULE in your Config.py file to run Cocotb.")
        return -1

    sg.log.debug(">> Preparing to run a Simulation w/ Cocotb")
    
    ## (1) Process hdl_sources.txt to obtain HDL sources.
    sg.log.debug(">> (A.1) Gathering HDL sources...")

    hdl_source_macros = {}
    source_lines = []
    
    try:
        with open(DEFAULT_SOURCES_FILE,'r') as r:
            source_lines_raw = [x.strip() for x in r.readlines()]
            

        for line in source_lines_raw:
            # a - Filter empty and commented lines.
            if not line or line.startswith("//"):
                continue
            # b - Define Macros 
            if line.startswith("DEF "):
                line_toks = line.split()
                hdl_source_macros[line_toks[1]] = line_toks[2]
                continue
            else:
                # c - For actual lines with path, replace macros, then append to source_lines[]
                for key in hdl_source_macros.keys():
                    line = line.replace("$"+key, hdl_source_macros[key])
                source_lines.append(line)


    except FileNotFoundError:
        sg.log.error(f"Please list your HDL source files in {default_source_file}.")
        return -1

    hdl_sources_with_path = [add_hdl_path(x) for x in source_lines]

    ## (2) If this is a Caribou Digital Twin run, then make sure the source file with the CaribouDigitalTwin in it is
    ##     replaced by the auto-generated top-level.

    if HDL_TOP_MODULE == "CaribouDigitalTwinTop":

        sg.log.debug(">> (A.2) Creating Digital Twin HDL")


        ## First -- Actually create the Digital Twin HDL
        create_digital_twin_hdl()

        ## Then -- Make sure that file is included in the HDL sources.
        
        if not os.path.exists(DEFAULT_DIGITAL_TWIN_TOP_FILE):
            sg.log.error("You set HDL_TOP_MODULE='CaribouDigitalTwinTop', but didn't find 'CaribouDigitalTwinTop.sv' in your HDL source files.")
            return -1
        #else:
        #    sg.log.debug(f"{DEFAULT_DIGITAL_TWIN_TOP_FILE} will be replaced by the autogenerated {AUTOGEN_DIGITAL_TWIN_FILENAME} in simulation.")

        myFile = add_hdl_path("CaribouDigitalTwinTop.sv")

        if myFile in hdl_sources_with_path:
            hdl_sources_with_path[hdl_sources_with_path.index(myFile)] = AUTOGEN_DIGITAL_TWIN_FILENAME
        else:
            hdl_sources_with_path.append(AUTOGEN_DIGITAL_TWIN_FILENAME)
        

    # (3) Create testbench

    sg.log.debug(f">> (A.3) Autogenerating Cocotb Test from {routine_name}...")
    cocotb_test_file = create_cocotb_test(routine_name)
    
    # (1) Set up the runner
    sg.log.debug(">> (A.4) Initializing simulator...")
    runner = get_runner(SIMULATOR)

   
    
    runner.build(
        sources = hdl_sources_with_path,
        hdl_toplevel = HDL_TOP_MODULE,
        clean=True,
        timescale = ('1n','1p')
        )

    # (2) Run the test
    runner.test(hdl_toplevel=HDL_TOP_MODULE,
                verbose=False,
                test_module=cocotb_test_file.replace(".py",""))



AUTOGEN_COCOTB_WARNING_PYTHON="""#  !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
#  ! WARNING! This file was automatically generated by  !
#  ! Spacely_Cocotb. You don't need to modify it, and   !
#  ! if you do, your modifications will be overwritten! !
#  !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
"""

AUTOGEN_COCOTB_WARNING_SV = AUTOGEN_COCOTB_WARNING_PYTHON.replace("#","//")
    

def add_hdl_path(filename):
    if filename.startswith("/"):
        #Assume this is already an absolute path
        return filename
    else:
        return os.path.join(os.getcwd(),"spacely-asic-config",TARGET,"hdl",filename)

def create_cocotb_test(routine_name):
    """Modifies a ROUTINE from TARGET_ROUTINES.py to be a valid Cocotb test."""

    ## (1) Read the original routines file.
    
    with open(TARGET_ROUTINES_PY,'r') as read_file:
        routines_txt = read_file.read()

    with open(TARGET_SUBROUTINES_PY,'r') as read_file:
        subroutines_txt = read_file.read()

    ## (2) Find the specific routine we are tasked to run.

    start_idx = routines_txt.find(f"\ndef {routine_name}")
    end_idx   = routines_txt.find("\ndef ",start_idx+1)

    this_routine_txt = routines_txt[start_idx:end_idx]


    ## (3) Add the entry function.
    entry_fn = COCOTB_ENTRY_FN.replace("{routine_name}",routine_name)

    #If the Routine requests dut as a parameter, we'll supply it.
    if f"def {routine_name}(dut" in this_routine_txt:
        entry_fn = entry_fn.replace("{routine_args}","dut")
    else:
        entry_fn = entry_fn.replace("{routine_args}","")
    
    this_routine_txt = this_routine_txt.replace(f"def {routine_name}(",
                                        entry_fn+f"\ndef {routine_name}(")


    ## (4) Update the routines txt

    routines_txt = AUTOGEN_COCOTB_WARNING_PYTHON + subroutines_txt + routines_txt.replace(routines_txt[start_idx:end_idx],this_routine_txt) 

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





def create_digital_twin_hdl():
    """Edit the user's hdl_top to insert AXI interfaces.""" 
    #sg.log.debug("Setting up digital twin HDL.")
    
    with open(DEFAULT_DIGITAL_TWIN_TOP_FILE,'r') as read_file:
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
    pattern = re.compile(r'/\*AXI_INTERFACE\((0x[0-9A-Fa-f]+)\)\*/(\s*)(\S?)')

    # Replace each AXI_INTERFACE comment and store the mappings
    def replacer(match):
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

    # Add AXI interfaces to each module.
    hdl_txt = pattern.sub(replacer, hdl_txt)

    # Add AXI signals to the interface of the top module.
    new_module_txt = "CaribouDigitalTwinTop (input logic AXI_ACLK,\n input logic AXI_ARESETN"
    
    for i in range(counter):
        new_module_txt += ",\n"+AXI_SIGNALS_TOP.replace("{n}",str(i))

    hdl_txt = re.sub(r'CaribouDigitalTwinTop\s*\(', new_module_txt, hdl_txt)


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

        with open(AUTOGEN_DIGITAL_TWIN_FILENAME,'r') as read_file:
            lines = read_file.readlines()

        for line in lines[5:]:
            if line.startswith("//axi:"):
                toks = line.replace("//axi:","").strip().split(",")
                self.axi_block_addr[int(toks[0])] = toks[1]
            else:
                break

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

            for field in self.mem_map.keys():
                
                #For fields which fall into this block:
                this_field_block_addr = self.mem_map[field]["IP Base Addr"]
                if this_field_block_addr == block_addr:
                    
                    if "TwinInterface" in self.mem_map[field]:
                        existing_iface = self.mem_map[field]["TwinInterface"]
                        sg.log.error(f"Mem map field {field} falls into block {block_addr} which is mapped to Digital Twin Interface {i}, but it is already assigned to Interface {existing_iface}.")

                    self.mem_map[field]["TwinInterface"] = i

        #Go back at the end and check we actually assigned an interface for every field. 
        for field in self.mem_map.keys():
            if "TwinInterface" not in self.mem_map[field]:
                sg.log.warning(f"Did not assign a Digital Twin Interface for {field}.")
            


    



    def connect_dut(self, dut):
        self.dut = dut

        sg.log.debug("Connecting CaribouTwin to dut object {dut}")

        axi_interfaces = list(self.axi_block_addr.keys())

        if len(axi_interfaces) == 0:
            sg.log.error("AXI Interfaces must be created in HDL_TOP before running connect_dut()")

        for i in axi_interfaces:
            self.axi.append(AxiLiteMaster(AxiLiteBus.from_prefix(dut, f"M{i}_AXI"),
                                          dut.AXI_ACLK,
                                          dut.AXI_ARESETN,
                                          reset_active_level=False))
            

    ######################################
    # Digital Twin Interaction Functions #
    ######################################


    def set_memory(self, mem_name, value):
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
        return x



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

    def close(self):
        pass
