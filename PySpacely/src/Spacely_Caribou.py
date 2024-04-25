import tkinter as tk
from tkinter import filedialog
from datetime import datetime
import os

from PearyClient import PearyClient, Device

import Spacely_Globals as sg

# Reasons why we run Spacely on Linux instead of on the ZCU102:
# (1) We would have to get direct internet access on the ZCU102, which is annoying.
# (2) If the ZCU102 crashes, Spacely goes down with it, and there may be no record of what caused it.
# (3) We may have to re-flash the entire image of the ZCU102 and we don't want to screw up Spacely.
# (4) Big picture, we want to treat the ZCU102 like a test instrument, not a place where long-term test data and analysis lives. 


class Caribou():

    def __init__(self, pearyd_host, pearyd_port, device_name, log):

        self._host = pearyd_host
        self._port = pearyd_port
        self._device_name = device_name
        self.log = log
        self.client_connected = False

        try:
            self._client = PearyClient(host=self._host, port=self._port)
        except (ConnectionRefusedError, OSError) as e:
            self.log.error(f"Could not connect to pearyd at {self._host}:{self._port}")
            self.log.error(f"Error message was: {e}")
            return 

        self.client_connected = True
        
        self._dev = self._client.ensure_device(self._device_name)

        #Send a message to check that the interface is operational.
        self._client.keep_alive()


    def get_memory(self, mem_name):
        """Return the contents of an FPGA Memory Register"""
        return self._dev.get_memory(mem_name)

    def set_memory(self, mem_name, value):
        """Set the contents of an FPGA Memory Register"""
        return self._dev.set_memory(mem_name,value)

#Given the raw lines extracted from mem_map.txt, this function checks for correctness.
#If correct, a nested dict is returned with info for every mem field.
#Otherwise, -1 is returned.
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
            base_address_token = line.split()[-1]

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
            mem_map[tokens[0]]["Readable"] = bool(tokens[3])
        except ValueError:
            sg.log.error(f"Parse error in 'Readable' for mem field {tokens[0]} (should be an int)")
            return -1

        try:
            mem_map[tokens[0]]["Writeable"] = bool(tokens[4])
        except ValueError:
            sg.log.error(f"Parse error in 'Writeable' for mem field {tokens[0]} (should be an int)")
            return -1
        

    return mem_map

#Returns an integer formatted as a string-format hex.
def print_hex(myInt):
    return f'{myInt:#08x}'
            
#Creates a C++ code representation of a memory map in dictionary form.
def mem_map_to_str(mem_map):

    s = "#define FPGA_REGS \\ \n { \\ \n"

    for field in mem_map.keys():

        register_address = print_hex(mem_map[field]["IP Base Addr"] + mem_map[field]["Register Offs"] - 0x400000000)
        mask = print_hex(mem_map[field]["Mask"])
        read = mem_map[field]["Readable"]
        write = mem_map[field]["Writeable"]

        s = s + "  {\""+field+"\", {FPGA_MEM, register_t<size_t>("
        s = s +f"{register_address}, {mask}, {read}, {write}, false)" + "}}, \\ \n"


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
