import tkinter as tk
from tkinter import filedialog
from datetime import datetime
import os
from os import stat

WINDOWS_OS = ('nt' in os.name)

if not WINDOWS_OS:
    from pwd import getpwuid
    import fcntl

from PearyClient import PearyClient, Device, Failure
from VirtualCaribou import VirtualCaribouClient
from fnal_libinstrument import Source_Instrument

import Spacely_Globals as sg



# Spacely Exclusive Resources
#
# We use exclusive resources to lock access to system resources that two Spacely processes should not simultaneously access.
# Each of these resources must have a unique "handle"
# The first process to request the resource will:
# (1) Acquire a lock on a file named after the handle.
# (2) Write to that file information about the lock.
# (3) When it's done, delete that file and release the lock.
#
# Other processes that try to request the resource in the middle will fail to acquire a lock on the file. 
                
class Exclusive_Resource:

    def __init__(self, handle, description):
        self.handle = handle
        self.description = description

        #Store lockfiles in a sub-directory of /tmp/
        #Change directory permissions to 777 so that we can not have issues deleting files.
        LOCKFILE_DIR = "/tmp/spacely-lockfiles/"

        # (1) Try to make the directory
        os.makedirs(LOCKFILE_DIR, exist_ok=True)

        # (2) If we are the owner of the directory, then try changing its permissions.
        # (if we're not the owner, not our problem.)
        dir_owner = getpwuid(stat(LOCKFILE_DIR).st_uid).pw_name
        if dir_owner == os.getlogin():
            #sg.log.debug("We own /tmp/spacely-lockfiles, setting permission bits.")
            os.chmod(LOCKFILE_DIR,0o777)

        
        self.lockfilename = f"{LOCKFILE_DIR}{self.handle}.lck"

        self.VERBOSE = True


    def acquire(self):

        if self.VERBOSE:
            sg.log.debug(f"Attempting to acquire Resource {self.handle}...")
        
        acquire_user = os.getlogin()
        acquire_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        #Ensure the file exists
        #If Spacely has the file open, we won't be able to open w/ 'a' permission.
        try:
            self.fp = open(self.lockfilename,'a')
            os.chmod(self.lockfilename,0o777)
            self.fp.close()
            
        except PermissionError:
            pass

        #We want to be able to write at the beginning, but if we fail to get the lock,
        #we also want to be able to read.
        self.fp = open(self.lockfilename,'r+')
        

        try:
            fcntl.flock(self.fp.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

            self.fp.write(f"{self.description} was locked by user {acquire_user} at time {acquire_time}\n")
            self.fp.flush()
            os.fsync(self.fp)
            #self.fp.close()

            sg.log.info(f"Resource {self.handle} acquired!")

        except BlockingIOError:
            with open(self.lockfilename,"r") as read_file:
                lockfile_text = read_file.read()
            sg.log.error(f"FAILED TO ACQUIRE RESOURCE: {lockfile_text}")
            return -1

    def release(self):
        if self.VERBOSE:
            sg.log.debug(f"Releasing Resource {self.handle}...")
            
        os.remove(self.lockfilename)
        fcntl.flock(self.fp.fileno(), fcntl.LOCK_UN)

        


#V1.5 CaR Board I2C Tree (Useful for debugging)

class INA226():
    def __init__(self, address, ID, name=""):
        self.part = "INA226"
        self.address = address
        self.ID = ID
        self.name = name
        self.registers = {0 : "Configuration Register",
                          1 : "Shunt Voltage Register",
                          2 : "Bus Voltage Register",
                          3 : "Power Register",
                          4 : "Current Register",
                          5 : "Calibration Register",
                          6 : "Mask/Enable Register",
                          7 : "Alert Limit Register",
                          0xFE : "Manufacturer ID Register",
                          0xFF : "Die ID Register"}

class DAC7678():
    def __init__(self, address, ID, name=""):
        self.part = "DAC7678"
        self.address = address
        self.ID = ID
        self.name = name
        self.registers = {}
        
        
class ADS7828():
    def __init__(self, address, ID, name=""):
        self.part = "DAC7678"
        self.address = address
        self.ID = ID
        self.name = name
        self.registers = {132: "SE Channel 1"}

class PCA9539():
    def __init__(self, address, ID, name=""):
        self.part = "PCA9539"
        self.address = address
        self.ID = ID
        self.name = name
        self.registers = {0 : "Input Port 0",
                          1 : "Input Port 1",
                          2 : "Output Port 0",
                          3 : "Output Port 1",
                          4 : "Polarity Inversion Port 0",
                          5 : "Polarity Inversion Port 1",
                          6 : "Direction Port 0",
                          7 : "Direction Port 1"}
                          


I2C_COMPONENTS = { 0 : [PCA9539(0x76,"U15"), PCA9539(0x75,"U31")],
                   1 : [INA226(0x40,"U53","pwr_out_1"), INA226(0x41, "U52","pwr_out_2"), INA226(0x42, "U55","pwr_out_3"), INA226(0x43, "U54","pwr_out_4"),
                        INA226(0x44,"U57","pwr_out_5"), INA226(0x45, "U56","pwr_out_6"), INA226(0x46, "U59","pwr_out_7"), INA226(0x4a, "U58","pwr_out_8")],
                   3 : [ADS7828(0x48,"U77","vol_in")]}






#class Device_emu(object):
#    
#    def __init__(self, client):
#        self._client = client
#        
#        
#   def _request():
        
# Reasons why we run Spacely on Linux instead of on the ZCU102:
# (1) We would have to get direct internet access on the ZCU102, which is annoying.
# (2) If the ZCU102 crashes, Spacely goes down with it, and there may be no record of what caused it.
# (3) We may have to re-flash the entire image of the ZCU102 and we don't want to screw up Spacely.
# (4) Big picture, we want to treat the ZCU102 like a test instrument, not a place where long-term test data and analysis lives. 


class Caribou(Source_Instrument):

    def __init__(self, pearyd_host, pearyd_port, device_name, log):
        """Initialize a new Caribou instrument.
        
           Arguments:
           pearyd_host -- Hostname for the ZCU102 running peary, for instance "192.168.1.24"
                          ** Set this argument to "EMULATE" in order to emulate Peary.
           pearyd_port -- Port to connect to peary on, typically 1234
           device_name -- Name of the Peary software device, typically "SpacelyCaribouBasic"
           log -- Reference to a logger object, typically sg.log
           """

        self._host = pearyd_host
        self._port = pearyd_port
        self._device_name = device_name
        self.log = log
        self.client_connected = False
        self.client_connected = False

        if self._host == "EMULATE":
            self.log.info("Due to settings in your Config file, Peary will be EMULATED in this session.")
            self.emulate_peary = True
        else:
            self.emulate_peary = False


        #Acquire an exclusive lock to Caribou system.
        if WINDOWS_OS:
            self.log.info("INFO: Exclusive locks on Spacely-Caribou are not implemented for Windows, please be careful if multiple users are using the same system.")
        else:
            self.lock = Exclusive_Resource(f"Caribou_{pearyd_host}", f"Caribou system at IP address {pearyd_host}")

            if self.lock.acquire() == -1:
                self.log.error("Failed to initialize Caribou, exiting.")
                exit()
        
        try:
            if self.emulate_peary:
                self._client = VirtualCaribouClient(host=self._host, port = self._port, logger=self.log)
            else:
                self._client = PearyClient(host=self._host, port=self._port)
        except (ConnectionRefusedError, OSError) as e:
            self.log.error(f"Could not connect to pearyd at {self._host}:{self._port}")
            self.log.error(f"Error message was: {e}")
            self.log.error("Failed to initialize Caribou, exiting.")
            exit() 

        self.client_connected = True

        #When set true, all memory read/writes will be logged to the console.
        self.debug_memory = False
        
        #List of AXI-addressable registers, to be used for running axi_shell
        self.axi_registers = None
        
        self._dev = self._client.ensure_device(self._device_name)

        #Send a message to check that the interface is operational.
        self._client.keep_alive()

        #self.configure_car()
    
    #Initialization steps that will need to be taken if & only if CaR board is attached.  
    def init_car(self):
        self.log.debug("~ ~ CaR Board Initialization ~ ~")

        #PCA9539 controls enable signals to power supplies.
        self.log.debug("[Step 1] Setting PCA9539 Dir to Output")
        self.car_i2c_write(0,0x76,6,0)
        self.car_i2c_write(0,0x76,7,0)
        

    def set_axi_registers(self, regmap):
        """Sets AXI registers for use by axi_shell and (if enabled) VirtualCaribou"""
        self.axi_registers = regmap
        
        if self.emulate_peary:
            self._client.load_firmware(regmap)

    #def load_virtual_fw(self, regmap):
    #    """Loads virtual firmware onto a VirtualCaribou instance, if used."""
    #    
    #    if not self.emulate_peary:
    #        self.log.error("SpacelyCaribou.load_virtual_fw() can only be called when using VirtualCaribou!")
    #        return -1 
    #        
    #    self._client.load_firmware(regmap)
    
    
    def close(self):
        try:
            self._client._close()
        except AttributeError:
            self.log.warning("<SpacelyCaribou> Attempted to close client port, but no client.")
        
        if not WINDOWS_OS:
            self.lock.release()

    #Wrapper for the PearyClient._request method that allows us to do Spacely-level error handling.
    def request(self, cmd, *args):
        try:
            return self._dev._request(cmd, *args)
        except Failure as e:
            self.log.error(f"PearyClient Failure: Command '{e.cmd}' failed with Code {e.code} ({e.reason})")
            return -1
        

    def get_memory(self, mem_name):
        """Return the contents of an FPGA Memory Register"""
        return_val = int(self._dev.get_memory(mem_name))
        if self.debug_memory:
            self.log.debug(f"<AXI> Read {mem_name}: {return_val}")
        return return_val

    def set_memory(self, mem_name, value):
        """Set the contents of an FPGA Memory Register"""
        if self.debug_memory:
            self.log.debug(f"<AXI> Set {mem_name} = {value}")
        return self._dev.set_memory(mem_name,value)

    def dly_min_axi_clk(self, clk_cycles):
        """Ensure a delay of a minimum number of AXI clock cycles."""

        # In Spacely-Caribou, AXI clk speed is 100 MHz.
        # This expression won't be accurate for a small number of clock
        # cycles, but it doesn't need to be b/c the overhead is so large.
        time.sleep(10e-9*clk_cycles)

    def get_voltage(self, name):
        """Get the voltage of a named DAC channel."""
        return self._dev.get_voltage(name)

    def set_voltage(self, name, value, curr_limit=None):
        """Set the voltage of a named DAC channel."""
        if curr_limit != None:
            self.log.warning("Spacely-Caribou Warning: Current limits for V supplies not implemented.")
        return self.request('set_voltage',name, value)
    
    def get_current(self, name):
        """Get the current of a named DAC channel."""
        return self._dev.get_current(name)

    def set_current(self, name, value, volt_limit=None):
        """Set the current of a named DAC channel."""
        if volt_limit != None:
            self.log.warning("Spacely-Caribou Warning: Voltage limits for I supplies not implemented.")
        return self._dev.set_current(name, value)


    def set_input_cmos_level(self, voltage):
        return self._dev._request("setInputCMOSLevel",voltage)

    def set_output_cmos_level(self,voltage):
        return self._dev._request("setOutputCMOSLevel",voltage)

    # NOTE: set_output_on() and set_output_off() take channels, not rail names, as arguments. Use V_CHAN[] or I_CHAN[]
    def set_output_on(self, channel):
        return self._dev.switch_on(channel)

    def set_output_off(self, channel):
        return self._dev.switch_off(channel)
        
    def disable_all_pwr_rails(self):
        for idx in range(1,9):
            rail_name = f"PWR_OUT_{idx}"
            self.set_output_off(rail_name)

    def setUsrclkFreq(self, frequency):
        return self._dev._request("setUsrclkFreq", frequency)
    
    def configureSI5345(self, config_num):
        return self._dev._request("configureSI5345", config_num)

    def stream_memory(self, mem_name,N):
        return self._dev._request("streamMemoryToFile",mem_name,N)
    
    def disableSI5345(self):
        return self._dev._request("disableSI5345")

    def checkSI5345Locked(self):
        return self._dev._request("requestSI5345Locked")

    def car_i2c_write(self, bus, comp_addr, mem_addr, data):
        return self._dev._request("car_i2c_write",bus, comp_addr, mem_addr, data)

    def car_i2c_read(self, bus, comp_addr, mem_addr, length):
        return self._dev._request("car_i2c_read",bus,comp_addr,mem_addr,length) 
    
    def car_i2c_shell(self):

        # Loop 1: Bus Selection
        while True:
            print("I2C Bus Options:")
            print("0. Si5345, Board ID, etc")
            print("1. INA226 Monitors")
            print("2. SEARAY")
            print("3. Bias DACs, slow ADCs")

            user_bus = input("bus?")

            if user_bus == "exit" or user_bus == "q":
                return

            try:
                user_bus = int(user_bus)
                if user_bus < 0 or user_bus > 3:
                    print("Invalid bus choice!")
                    continue
            except TypeError:
                print("Invalid bus choice!")
                continue

            # Loop 2: Component Selection
            while True:
                print("Component Options:")
                for i in range(len(I2C_COMPONENTS[user_bus])):
                    comp = I2C_COMPONENTS[user_bus][i]
                    print(f"{i}. 0x{comp.address:02x} {comp.part} {comp.name}")

                user_comp = input("component?")

                if user_comp == "q":
                    break

                try:
                    user_comp = I2C_COMPONENTS[user_bus][int(user_comp)]
                except (IndexError, TypeError):
                    print("Invalid Component Choice!")
                    continue

                # Loop 3: Memory Selection
                print("Component Options:")
                for i in user_comp.registers.keys():
                    regname = user_comp.registers[i]
                    print(f"{i} -- {regname}")
                while True:
                    

                    user_reg = input("register?")

                    if user_reg == 'q':
                        break

                    try:
                        user_reg = int(user_reg)
                        if user_reg not in user_comp.registers.keys():
                            print("(reg not in reg list)")
                            #continue
                    except TypeError:
                        print("Invalid Reg Choice!")
                        continue

                    user_rw = input("r/w?")

                    if user_rw == "r":
                        raw_read_data = self.car_i2c_read(user_bus, user_comp.address, user_reg,2)
                        print(f"Raw read data: {raw_read_data}")
                        i2c_data = int(raw_read_data)
                        print(f"HEX: {i2c_data:04x} \n BIN:{i2c_data:16b}")
                        
                    elif user_rw == "w":
                        try:
                            user_data = int(input("data?"))
                            self.car_i2c_write(user_bus, user_comp.address, user_reg,user_data)
                            #print(f"RETURN DATA: {i2c_data}")
                        except ValueError:
                            print("Enter numeric data!")



    def axi_shell(self):
        """Microshell to interact with the AXI registers and debug the design."""

        if self.axi_registers is None:
            self.log.error("Cannot run Caribou.axi_shell unless Caribou.axi_registers are defined.")
            return
                        
        register_list = self.axi_registers

        for x in register_list.keys():
            print(x)
            
        fw_choice = input("Which fw module would you like to interact with?")
        
        AXI_REGISTERS = register_list[fw_choice]

        while True:

            # Print register contents
            i = 0
            for reg in AXI_REGISTERS:
                reg_contents = self.get_memory(reg)
                
                print(f"{i}. {reg : <16} -- {reg_contents}")
                i = i+1

            write_reg_num = input("write which?").strip()

            if write_reg_num == "":
                continue

            if write_reg_num == "q":
                return

            write_reg = AXI_REGISTERS[int(write_reg_num)]

            write_val = int(input("val?"))

            self.set_memory(write_reg, write_val)
    
        
##########################################################################################
# Helper Functions for Creating Firmware
##########################################################################################
# Reminder about the format for Firmware Description files:
#
# PARAMETER  {name} {default_value}
#PORT  {name}  {length}     {direction (1=output, 0=input)}
#REGISTER  {name}  {length}   {type (0=read/write, 1=readonly, 2=trigger/pulse)}
#
#

class FW_Parameter():
    def __init__(self,name):
        self.name = name
        self.default_value = None

class FW_IO_Port():
    def __init__(self,name):
        self.name = name
        self.length = None #Can be an integer or a string parameter name.
        self.direction = None

class FW_Register():
    def __init__(self,name):
        self.name = name
        self.length = None #Can be an integer or a string parameter name.
        self.reg_type = None
        #Is this a special auto-generated register which holds the value of a parameter?
        self.is_param_reg = False
        self.param_name = None


def parse_firmware_description(fw_des_lines):
    """Returns three lists: parameters, ports, and registers described by a fw_description file.
       
       Arguments:
       fw_des_lines -- List of strings representing the lines in a fw_description file.
    """

    parameters = []
    ports = []
    registers = []
    
    for line in fw_des_lines:
        
        line = line.strip()
        
        #Skip blank lines
        if len(line) == 0:
            continue
        
        #Skip commented lines
        if line.startswith("//"):
            continue

        tokens = line.split()


        if tokens[0] == "PARAMETER":
            p = FW_Parameter(tokens[1])
            p.default_value = int(tokens[2])
            parameters.append(p)

        elif tokens[0] == "PORT":
            p = FW_IO_Port(tokens[1])
            try:
                p.length = int(tokens[2])
            except ValueError as e:
                #In addition to an integer, it's okay for length to be the name of a parameter.
                param_names = [p.name for p in parameters]
                if tokens[2] in [p.name for p in parameters]:
                    p.length = tokens[2]
                else:
                    sg.log.error(f"FW Description Parse Error on line '{line}': {tokens[2]} is neither an integer nor one of the parameters previously defined ({param_names}).\n{e}")
                    return -1
            try:
                p.direction = int(tokens[3])
            except ValueError as e:
                sg.log.error(f"FW Description Parse Error on line '{line}'\n{e}")
                return -1
            ports.append(p)

        elif tokens[0] == "REGISTER":
            r = FW_Register(tokens[1])
            try:
                r.length = int(tokens[2])
            except ValueError as e:
                #In addition to an integer, it's okay for length to be the name of a parameter.
                param_names = [p.name for p in parameters]
                if tokens[2] in [p.name for p in parameters]:
                    r.length = tokens[2]
                else:
                    sg.log.error(f"FW Description Parse Error on line '{line}': {tokens[2]} is neither an integer nor one of the parameters previously defined ({param_names}).\n{e}")
                    return -1
            try:
                r.reg_type = int(tokens[3])
            except ValueError as e:
                sg.log.error(f"FW Description Parse Error on line '{line}'\n{e}")
                return -1
            registers.append(r)



    # Automatically add registers which return the value of parameters.
    for p in parameters:
        r = FW_Register(f"param_{p.name}")
        r.length = 32
        r.type = 1 #readonly
        r.is_param_reg = True
        r.param_name = p.name
        registers.append(r)

    return (parameters, ports, registers)
        

def gen_virtual_fw():
    """Generates a Python object that serves as a virtualization of the firmware."""
    pass


def gen_fw(fw_name=None,fw_des_filename=None):
    """Generates XX_top.v, XX_interface.sv, and README.md files for a fw block in Spacely-Caribou format"""
    
    input_folder = os.path.join(".","src","FirmwareTemplate")
    output_folder = os.path.join(".","output","Autogenerated Firmware")

    sg.log.debug(f"Creating {output_folder}")

    os.makedirs(output_folder,exist_ok=True)

    if fw_name == None:
        fw_name = input("What name does your firmware module have?")

    if fw_des_filename == None:
        fw_des_filename = filedialog.askopenfilename()

    with open(fw_des_filename,'r') as read_file:
        fw_des_lines = read_file.readlines()

    parse_result = parse_firmware_description(fw_des_lines)

    if parse_result == -1:
        return
    else:
        param, port, reg = parse_result

    ##################
    # myModule_top.v #
    ##################
    with open(os.path.join(input_folder,"myModule_top.v"),"r") as read_file:
        top_txt = read_file.read()

    top_txt = top_txt.replace("myModule",fw_name)
    top_txt = top_txt.replace("((PARAMETERS))",write_PARAMETERS(param,port,reg))
    top_txt = top_txt.replace("((TOP_IO_PORTS))",write_TOP_IO_PORTS(param,port,reg))
    top_txt = top_txt.replace("((IO_INST))",write_IO_INST(param,port,reg))
    top_txt = top_txt.replace("((PARAMETERS_INST))",write_PARAMETERS_INST(param,port,reg))

    with open(os.path.join(output_folder,f"{fw_name}_top.v"),"w") as write_file:
        write_file.write(top_txt)
    sg.log.notice(f"Successfully wrote {fw_name}_top.v to /output/ folder!")

    #########################
    # myModule_interface.sv #
    #########################

    with open(os.path.join(input_folder,"myModule_interface.sv"),"r") as read_file:
        int_txt = read_file.read()

   
    int_txt = int_txt.replace("((PARAMETERS))",write_PARAMETERS(param,port,reg))
    int_txt = int_txt.replace("((INTERFACE_IO_PORTS))",write_INTERFACE_IO_PORTS(param,port,reg))
    int_txt = int_txt.replace("((REG_NUM))",str(len(reg)))
    int_txt = int_txt.replace("((REG_ADDRESS_MAP))",write_REG_ADDRESS_MAP(param,port,reg))
    int_txt = int_txt.replace("((REG_DEF))",write_REG_DEF(param,port,reg))
    int_txt = int_txt.replace("((REG_WRITE))",write_REG_WRITE(param,port,reg))
    int_txt = int_txt.replace("((REG_READ))",write_REG_READ(param,port,reg))
    int_txt = int_txt.replace("((MODULE))",write_MODULE(param,port,reg))
    int_txt = int_txt.replace("((PARAM_REG_ASSIGN))",write_PARAM_REG_ASSIGN(param,port,reg))
    int_txt = int_txt.replace("myModule",fw_name)

    with open(os.path.join(output_folder,f"{fw_name}_interface.sv"),"w") as write_file:
        write_file.write(int_txt)

    sg.log.notice(f"Successfully wrote {fw_name}_interface.sv to /output/ folder!")

    #############
    # README.md #
    #############
    with open(os.path.join(input_folder,"README.md"),"r") as read_file:
        readme_txt = read_file.read()
    readme_txt = readme_txt.replace("((PARAMETER_DOCS))",write_PARAMETER_DOCS(param,port,reg))
    readme_txt = readme_txt.replace("((REGISTER_DOCS))",write_REGISTER_DOCS(param,port,reg))
    readme_txt = readme_txt.replace("((IO_DOCS))",write_IO_DOCS(param,port,reg))
    readme_txt = readme_txt.replace("((FW_MEM_MAP))",write_FW_MEM_MAP(param,port,reg))
    readme_txt = readme_txt.replace("myModule",fw_name)
    
    with open(os.path.join(output_folder,f"README.md"),"w") as write_file:
        write_file.write(readme_txt)
    
    sg.log.notice(f"Successfully wrote README.md to /output/ folder!")
    

def write_PARAMETERS(param, port, reg):
    """Write code that instantiates parameters in the header of a function."""
    PARAMETERS = ""
    for p in param:
        PARAMETERS = PARAMETERS + f"parameter integer {p.name}={p.default_value},\n"
    return PARAMETERS

def write_TOP_IO_PORTS(param,port,reg):
    """Write code that creates I/O ports for XX_top.v"""
    TOP_IO_PORTS = ""
    for p in port:
        if p.direction == 1:
            Direction = "output"
        elif p.direction == 0:
            Direction = "input"
        if type(p.length) == str:
            Bits = f"[{p.length}-1:0]"
        elif  p.length > 1:
            Bits = f"[{p.length-1}:0]"
        else:
            Bits = ""
        TOP_IO_PORTS = TOP_IO_PORTS + f"{Direction} wire {Bits} {p.name},\n"

    return TOP_IO_PORTS

def write_INTERFACE_IO_PORTS(param,port,reg):
    """Write code that creates I/O ports for XX_interface.sv"""
    INTERFACE_IO_PORTS = ""
    for p in port:
        if p.direction == 1:
            Direction = "output"
        elif p.direction == 0:
            Direction = "input"
        if type(p.length) == str:
            Bits = f"[{p.length}-1:0]"
        elif p.length > 1:
            Bits = f"[{p.length-1}:0]"
        else:
            Bits = ""
        INTERFACE_IO_PORTS = INTERFACE_IO_PORTS + f"{Direction} logic {Bits} {p.name},\n"

    return INTERFACE_IO_PORTS

def write_IO_INST(param,port,reg):
    """Write code that connects I/O ports by name in an instantiated block."""
    IO_INST = ""
    for p in port:
        IO_INST = IO_INST + f".{p.name}({p.name}),\n"
    return IO_INST

def write_PARAMETERS_INST(param,port,reg):
    """Write code that connects parameters by name in an instantiated block."""
    PARAMETERS_INST = ""
    for p in param:
        PARAMETERS_INST = PARAMETERS_INST + f".{p.name}({p.name}),\n"
    return PARAMETERS_INST

def write_REG_ADDRESS_MAP(param,port,reg):
    """Write code that assigns a register address to each register."""
    REG_ADDRESS_MAP = ""
    i = 0
    for r in reg:
        REG_ADDRESS_MAP = REG_ADDRESS_MAP + f"localparam byte unsigned ADDRESS_{r.name} = {i};\n"
        i = i + 1
    return REG_ADDRESS_MAP

def write_REG_DEF(param,port,reg):
    """Write code that creates each register as fpga_reg_XYZ"""
    REG_DEF = ""
    for r in reg:
        if type(r.length) == str:
            REG_DEF = REG_DEF + f"logic [{r.length}-1:0] fpga_reg_{r.name};\n"
        elif r.length > 1:
            REG_DEF = REG_DEF + f"logic [{r.length-1}:0] fpga_reg_{r.name};\n"
        else:
            REG_DEF = REG_DEF + f"logic                  fpga_reg_{r.name};\n"
    return REG_DEF


def write_REG_READ(param,port,reg):
    """Write code that allows reading of each register."""
    REG_READ = ""
    for r in reg:
        REG_READ = REG_READ + f"assign reg_rddin[ADDRESS_{r.name}] = fpga_reg_{r.name};\n"
    return REG_READ

def write_REG_WRITE(param,port,reg):
    """Write code that allows all writeable registers to be written to."""
    REG_WRITE = "always_ff @(posedge S_AXI_ACLK) begin\n    if (~S_AXI_ARESETN) begin\n"
    for r in reg:
        if r.reg_type == 0 or r.reg_type == 2:
            REG_WRITE = REG_WRITE + f"        fpga_reg_{r.name} <= '0;\n"
    REG_WRITE = REG_WRITE + "    end\n    else begin\n"
    for r in reg:
        if r.reg_type == 0:
            REG_WRITE = REG_WRITE + f"        if (reg_wrByteStrobe[ADDRESS_{r.name}] == 4'b1111)\n"
            if type(r.length) == str:
                REG_WRITE = REG_WRITE + f"            fpga_reg_{r.name} <= reg_wrdout[{r.length}-1:0];\n"
            elif r.length > 1:
                REG_WRITE = REG_WRITE + f"            fpga_reg_{r.name} <= reg_wrdout[{r.length-1}:0];\n"
            else:
                REG_WRITE = REG_WRITE + f"            fpga_reg_{r.name} <= reg_wrdout[0];\n"
        if r.reg_type == 2:
            REG_WRITE = REG_WRITE + f"        if (reg_wrByteStrobe[ADDRESS_{r.name}] == 4'b1111)\n"
            REG_WRITE = REG_WRITE + f"            fpga_reg_{r.name} <= 1;\n"
            REG_WRITE = REG_WRITE + f"        else\n"
            REG_WRITE = REG_WRITE + f"            fpga_reg_{r.name} <= 0;\n"
    REG_WRITE = REG_WRITE + "    end\n"
    REG_WRITE = REG_WRITE + "end //always_ff \n"
    return REG_WRITE

def write_MODULE(param,port,reg):
    """Write code that instantiates the actual firmware module inside the wrapper."""
    MODULE = "myModule "
    if len(param) > 0:
        MODULE = MODULE + "#("
        for i in range(len(param)):
            p = param[i]
            MODULE = MODULE + f"\n.{p.name}({p.name})"
            if i < len(param)-1:
                MODULE = MODULE + ","
            else:
                MODULE = MODULE + ")"
    MODULE = MODULE + "myModule_int ("
    for i in range(len(reg)):
        r = reg[i]
        #Param regs are special and do not get connected to the module.
        if not r.is_param_reg:
            MODULE = MODULE + f"\n.{r.name}(fpga_reg_{r.name}),"
    for i in range(len(port)):
        p = port[i]
        MODULE = MODULE + f"\n.{p.name}({p.name})"
        if i < len(port)-1:
            MODULE = MODULE + ","
        else:
            MODULE = MODULE + ");"

    return MODULE

def write_PARAM_REG_ASSIGN(param,port,reg):
    """Write code that assigns param_regs their appropriate value."""
    PARAM_REG_ASSIGN = ""
    for r in reg:
        if r.is_param_reg:
            PARAM_REG_ASSIGN += f"assign fpga_reg_{r.name} = {r.param_name};\n"

    return PARAM_REG_ASSIGN

def write_PARAMETER_DOCS(param,port,reg):
    """Generate a fillable table with entries for each parameter."""
    PARAMETER_DOCS = ""
    for p in param:
        PARAMETER_DOCS = PARAMETER_DOCS + f"|{p.name} | {p.default_value} | (TODO: What is the function of this parameter?) |\n"
    return PARAMETER_DOCS

def write_REGISTER_DOCS(param,port,reg):
    """Generate a fillable table with entries for each register."""
    REGISTER_DOCS = ""
    for r in reg:
        if r.reg_type == 0:
            Read = "Y"
            Write = "Y"
        elif r.reg_type == 1:
            Read = "Y"
            Write = "N"
        elif r.reg_type == 2:
            Read = "N"
            Write = "Y"

        if r.is_param_reg:
            REGISTER_DOCS = REGISTER_DOCS + f"|{r.name} | {r.length} | {Read} | {Write} | Yields the actual value of parameter {r.param_name} |\n"
        else:  
            REGISTER_DOCS = REGISTER_DOCS + f"|{r.name} | {r.length} | {Read} | {Write} | (TODO: What is the function of this register?) |\n"
    return REGISTER_DOCS

def write_IO_DOCS(param,port,reg):
    """Generage a fillable table with entries for each I/O pin."""
    IO_DOCS = ""
    for p in port:
        if p.direction == 1:
            Direction = "output"
        else:
            Direction = "input"
            
        IO_DOCS = IO_DOCS + f"|{p.name}| {p.length}b {Direction} | (TODO: What clock domain is this I/O in?) | (TODO: What is the function of this I/O and what should it be connected to?)|\n"
    return IO_DOCS


    

def write_FW_MEM_MAP(param,port,reg):
    """Writes a memory map of all registers that were instantiated."""
    FW_MEM_MAP = ""

    variable_length_regs = []
    
    for i in range(len(reg)):
        r = reg[i]
        offset = hex(4*i)

        if type(r.length) == str:
            mask = hex_mask(32)
            variable_length_regs.append(r.name)
        else:
            mask = hex_mask(r.length)
            
        if r.reg_type == 0:
            Read = "True"
            Write = "True"
        elif r.reg_type == 1:
            Read = "True"
            Write = "False"
        elif r.reg_type == 2:
            Read = "False"
            Write = "True"
        FW_MEM_MAP = FW_MEM_MAP + f"{r.name},{offset},{mask},{Read},{Write}\n\n"

    if len(variable_length_regs) > 0:
        variable_length_regs = ", ".join(variable_length_regs)
        FW_MEM_MAP += f"**Note:** The following registers have parameterizable size: {variable_length_regs}.  In this memory map, 32b are reserved for each of these registers, the maximum allowed with a standard Spacely-Caribou AXI bus."
        
    return FW_MEM_MAP

# Returns a hex string with all 1's for the first N bits.
def hex_mask(N1):
    mask = 0
    for i in range(N1):
        mask = mask | 1 << i
    return hex(mask)

##########################################################################################
# Helper Functions for Creating Peary Cpp Devices
##########################################################################################

    
#Given the raw lines extracted from mem_map.txt, this function checks for correctness.
#If correct, a nested dict is returned with info for every mem field.
#Otherwise, -1 is returned.
#
# Structure of the dictionary:
#
#   mem_map["reg_name"] = {"IP Base Addr" : 0x400000000
#                          "Register Offs": (int)
#                          "Mask"         : (int)
#                          "Readable"     : (bool)
#                          "Writeable"    : (bool)}
#
def parse_mem_map(mem_map_lines):

    mem_map = {}

    ip_base_address = -1

    for line in mem_map_lines:

        line = line.strip()

        #Skip blank lines
        if len(line) == 0:
            continue

        #Skip commented lines
        if line.startswith("//"):
            continue

        #Base Address Line
        if line.startswith("*BASE"):
            base_address_token = line.split()[1]

            try:
                ip_base_address = int(base_address_token,0)
                continue
            except ValueError:
                sg.log.error(f"Parse Error determining base address from '{line}', '{base_address_token}' is not an integer.")
                return -1

        if ip_base_address == -1:
            sg.log.error(f"Parse Error: Please define IP base address with '*BASE <base address>' before the first mem map entry.")
            return -1
            
        tokens = line.split(",")

        #Create a new memory map entry.
        if tokens[0] in mem_map.keys():
            sg.log.error(f"Duplicate memory field {tokens[0]}")
            return -1
        else:
            mem_map[tokens[0]] = {}


        mem_map[tokens[0]]["IP Base Addr"] = ip_base_address

        # Each line should have five entries: the field name, and then Offs/Mask/Read/Write
        if len(tokens) < 5:
            sg.log.error(f"Parse error for mem field {tokens[0]}: Some of the required fields are missing.")
            return -1

        try:
             mem_map[tokens[0]]["Register Offs"] = int(tokens[1],0)
        except ValueError:
            sg.log.error(f"Parse error in Register Offs for mem field {tokens[0]} (should be an int in hex or dec)")
            return -1

        try:
             mem_map[tokens[0]]["Mask"] = int(tokens[2],0)
        except ValueError:
            sg.log.error(f"Parse error in Mask for mem field {tokens[0]} (should be an int in hex or dec)")
            return -1
        
        try:
            mem_map[tokens[0]]["Readable"] = ( (tokens[3].lower() == "true") or (tokens[3] == "1") )
        except ValueError:
            sg.log.error(f"Parse error in 'Readable' for mem field {tokens[0]} (should be an int or str)")
            return -1

        try:
            mem_map[tokens[0]]["Writeable"] = ( (tokens[4].lower() == "true") or (tokens[4] == "1") )
        except ValueError:
            sg.log.error(f"Parse error in 'Writeable' for mem field {tokens[0]} (should be an int or str)")
            return -1
        

    return mem_map

#Returns an integer formatted as a string-format hex.
def print_hex(myInt):
    return f'{myInt:#08x}'


def gen_mem_map():
    
    mem_map_filename = filedialog.askopenfilename()

    with open(mem_map_filename,'r') as read_file:
        mem_map_lines = read_file.readlines()

    mem_map = parse_mem_map(mem_map_lines)


    print(mem_map_to_str(mem_map))

    

#Creates a C++ code representation of a memory map in dictionary form.
def mem_map_to_str(mem_map):

    s = "#define FPGA_REGS \\\n { \\\n"

    for field in mem_map.keys():

        register_address = print_hex(mem_map[field]["IP Base Addr"] + mem_map[field]["Register Offs"] - 0x400000000)
        mask = print_hex(mem_map[field]["Mask"])

        #Account for the fact that bools have lowercase in C++, uppercase in Python.
        if mem_map[field]["Readable"]:
            read = "true"
        else:
            read = "false"

        if mem_map[field]["Writeable"]:
            write = "true"
        else:
            write = "false"

        s = s + "  {\""+field+"\", {FPGA_MEM, register_t<size_t>("
        s = s +f"{register_address}, {mask}, {read}, {write}, false)" + "}}, \\\n"


    s = s + "}\n"

    return s
    
    

def generate_peary_device(name=None, filename=None):

    ## GET DEVICE NAME
    if name == None:
        user_devname = input("Please enter a name for your Peary device:")
    else:
        user_devname = name
        
    devname = user_devname
    
 
    FILENAME_ILLEGAL_CHARS = [" ",".",":","?"]
        
        
    for c in FILENAME_ILLEGAL_CHARS:
        devname = devname.replace(c,"_")

    if devname != user_devname:
        sg.log.debug(f"Device name {user_devname} was automatically updated to {devname}")


    ## GET mem_map.txt
    if filename == None:
        print("To generate a Peary device, you will need a Memory Map. Press enter when you are ready to select your mem_map.txt...")
        input("")

        mem_map_filename = filedialog.askopenfilename()
    else:
        mem_map_filename = filename

    with open(mem_map_filename,'r') as read_file:
        mem_map_lines = read_file.readlines()

    mem_map = parse_mem_map(mem_map_lines)

    if mem_map == -1:
        return

    ## WRITE Device Files
    input_folder = os.path.join(".","src","PearyDeviceTemplate")
    output_folder = os.path.join(".","output",devname)
    DEVNAME_STR = "((devname))"
    MEMMAP_STR = "((mem_map))"
    
    sg.log.debug(f"Creating {output_folder}")

    os.makedirs(output_folder,exist_ok=True)

    # CMakeLists.txt
    sg.log.debug("Writing CMakeLists.txt")
    with open(os.path.join(input_folder,"CMakeLists.txt"),"r") as read_file:
        CMakeLists_contents = read_file.read()

    with open(os.path.join(output_folder,"CMakeLists.txt"),"w") as write_file:
        write_file.write(CMakeLists_contents.replace(DEVNAME_STR,devname))

    # Device.cpp
    sg.log.debug(f"Writing {devname}Device.cpp")
    with open(os.path.join(input_folder,"Device.cpp"),"r") as read_file:
        DeviceCpp_contents = read_file.read()

    with open(os.path.join(output_folder,devname+"Device.cpp"),"w") as write_file:
        write_file.write(DeviceCpp_contents.replace(DEVNAME_STR,devname))

    # Device.hpp
    sg.log.debug(f"Writing {devname}Device.hpp")
    with open(os.path.join(input_folder,"Device.hpp"),"r") as read_file:
        DeviceHpp_contents = read_file.read()

    with open(os.path.join(output_folder,devname+"Device.hpp"),"w") as write_file:
        write_file.write(DeviceHpp_contents.replace(DEVNAME_STR,devname))


    # Defaults.hpp
    sg.log.debug(f"Writing {devname}Defaults.hpp")
    with open(os.path.join(input_folder,"Defaults.hpp"),"r") as read_file:
        DefaultsHpp_contents = read_file.read()


    DefaultsHpp_contents = DefaultsHpp_contents.replace(DEVNAME_STR,devname)
    DefaultsHpp_contents = DefaultsHpp_contents.replace(MEMMAP_STR,mem_map_to_str(mem_map))
    
    with open(os.path.join(output_folder,devname+"Defaults.hpp"),"w") as write_file:
        write_file.write(DefaultsHpp_contents)

    # README.md

    with open(os.path.join(output_folder,"README.md"),"w") as write_file:
        write_file.write(f"# {devname} \n\n")
        write_file.write("This is a Peary Device auto-generated by Spacely on "+datetime.now().strftime("%Y-%m-%d %a %H:%M:%S")+". \n\n")
        write_file.write("Original mem_map.txt:\n")
        for line in mem_map_lines:
            write_file.write(line)


    
    sg.log.notice(f"Successfully wrote Peary Device for {devname}!")
