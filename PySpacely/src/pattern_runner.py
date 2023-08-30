from fnal_ni_toolbox import *
import fnal_log_wizard as liblog
from abc import ABC
import os
import time
from threading import Thread

################## GlueFPGA Implementation Constants ################
# When you read back waveforms from the FPGA, you will read back this many zeros first.
FPGA_READBACK_OFFSET = 3
FPGA_CLOCK_HZ = 40e6

GLUEFPGA_DEFAULT_BITFILES = {"PXI1Slot5/NI6583":"C:\\Users\\Public\\Documents\\LABVIEWTEST\\GlueDirectBitfile_6_27_b.lvbitx"}

GLUEFPGA_DEFAULT_CFG = { "Run_Test_Fifo_Loopback" : False,
                        "Run_Pattern"  : False,
                        "Buffer_In_Size": 1024,
                        "Buffer_Pass_Size":1024,
                        "FPGA_Loop_Dis": False,
                        "se_io_data_dir":0,
                         "lvds_data_dir":0,
                         "lvds_clockout_en":False,
                        "SE_Data_Default":60,
                        "Set_Voltage_Family":True,
                        "Voltage_Family":1} # Change back to 4!

#####################################################################


#PatternRunner usage model:
#
# At the top level of Spacely, we will initialize an FPGA resource with a given bitfile.
# This is similar to how we initialize other instruments, and it makes sense because
# the Glue bitfile should be relatively universal, not changing per pattern.
#
# Each PatternRunner will be used to run a specific pattern, for example programming
# a config register, or communicating over SPI. The PatternRunner class requires
# (1) An iospec. This tells it which FPGA resources will be used for running the patterns,
#     and which IOs should be write versus read.
# (2) A dictionary, which gives it access to the available FPGA resources, indexed by hardware name.
#     **Note: If fpga_dict is not supplied, PatternRunner() will initialize the FPGAs by itself.
# (3)(optionally) the pattern it is supposed to run, which we can also update later.
#
# fpga_dict example = {"PXI1Slot5/NI6583": <NiFpga Object>}
#
# For basic example, see ROUTINE4


class PatternRunner(ABC):
    _fpga: NiFpga = None

    def __init__(self, logger: liblog.Logger, iospecfile, fpga_dict=None, pattern=None):
        self._log = logger
        self._interface = {}

        #Init an instance of GlueConverter to handle GlueWave() operations.
        self.gc = GlueConverter(iospecfile)

        if fpga_dict == None:
            self._fpga_dict = self.initialize_hardware(self._log,GLUEFPGA_DEFAULT_BITFILES)

        for hw in self._fpga_dict.keys():
            self._interface[hw] = NiFpgaDebugger(logger, self._fpga_dict[hw])
            self._interface[hw].configure(GLUEFPGA_DEFAULT_CFG)

            print("(DBG) Pulsing Set_Voltage_Family")
            #Pulse "Set_Voltage_Family" to ensure voltage family is actually set correctly.
            self._interface[hw].interact("w","Set_Voltage_Family",False)
            time.sleep(1)
            self._interface[hw].interact("w","Set_Voltage_Family",True)
            time.sleep(1)
            self._interface[hw].interact("w","Set_Voltage_Family",False)
        
        self._return_data = []

##        #Read iospec file and parse it into a dictionary.
##        with open(iospecfile,"r") as read_file:
##            iospec_lines = read_file.readlines()
##            
##        #Lines in the iospec file have the format:
##        #{signal name},{I/O},{port number}
##        for line in iospec_lines:
##            if len(line) > 1 and not line.startswith("//"):
##                a = line.split(",")
##                self._iospec[a[0]] = [a[1],int(a[2])]


        self._update_io_dir()
        self._update_io_defaults()

        if pattern is not None:
            self.update_pattern(pattern)


    # initialize_hardware() - This function sets up a hardware dictionary and initializes
    #  all FPGAs required for the I/Os in iospec. 
    def initialize_hardware(self,log,default_bitfiles):
        hardware_dict = {}

        #For every hardware resource required by an I/O...
        for hw in self.gc.IO_hardware.values():
            fpga_name = "/".join(hw.split("/")[0:2])
            slot_name = hw.split("/")[0]
            
            if fpga_name not in hardware_dict.keys():
                print("(DBG) Initializing FPGA Hardware:",fpga_name,"...")
                hardware_dict[fpga_name] = NiFpga(log, slot_name)
                hardware_dict[fpga_name].start(default_bitfiles[fpga_name])

        return hardware_dict

    # _update_io_defaults() - Sets all IOs to their default state from iospec.
    def _update_io_defaults(self):
        
        #Make an io_default value for each FPGA resource we use
        hw_list = list(set(self.gc.IO_hardware.values()))
        io_default = {}
        for hw in hw_list:
            io_default[hw] = 0

        #For each ASIC input I/O, set the corresponding io_dir bit.
        for io in self.gc.Input_IOs:
            hw = self.gc.IO_hardware[io]
            pos = self.gc.IO_pos[io]
            default = self.gc.IO_default[io]
            #INPUTS to the ASIC are OUTPUTS from Glue, so set their IO dir to 1.
            if default > 0:
                io_default[hw] = io_default[hw] + (1 << pos)

        #Write all these updated I/O dirs to the right hardware.
        for hw in hw_list:
            fpga_name = "/".join(hw.split("/")[0:2])
            fifo = hw.split("/")[2]
            
            #TODO: UPDATE FOR MULTI-HARDWARE
            if "se_io" in fifo: #Only supports NI6583/se_io for the moment...
                print("(DBG) Programming", hw, "I/O Defaults as:",io_default[hw])
                print("WARNING!!! Need to update this function for multi-hardware")
                self._interface[fpga_name].interact("w","SE_Data_Default",io_default[hw])


    # _update_io_dir - Updates the direction of FPGA IOs to conform to the iospec.
    def _update_io_dir(self) -> None:

        #Make an io_dir value for each FPGA resource we use
        hw_list = list(set(self.gc.IO_hardware.values()))
        io_dir = {}
        for hw in hw_list:
            io_dir[hw] = 0

        #For each ASIC input I/O, set the corresponding io_dir bit.
        for io in self.gc.Input_IOs:
            hw = self.gc.IO_hardware[io]
            pos = self.gc.IO_pos[io]
            #INPUTS to the ASIC are OUTPUTS from Glue, so set their IO dir to 1.
            io_dir[hw] = io_dir[hw] + (1 << pos)

        #Write all these updated I/O dirs to the right hardware.
        for hw in hw_list:
            fpga_name = "/".join(hw.split("/")[0:2])
            fifo = hw.split("/")[2]
            print("(DBG) Programming", hw, "I/O Direction as:",io_dir[hw])
            self._interface[fpga_name].interact("w",fifo+"_data_dir",io_dir[hw])


    # setup_pattern() - Performs the following tasks to prepare for running a pattern:
    #   -- Configures the host buffer size to be sufficient
    #   -- Sets Buffer_Pass_Size on the FPGA
    #   -- Loads the pattern into host memory
    #   -- sets up (but doesn't run) a reader thread that will dump into a slot in self._return_data
    def setup_pattern(self,pattern):

        print("(DBG) Setting up pattern for hardware resource:",pattern.hardware_str)

        #Identify the correct fifos and debugger based on the hardware specification of pattern.
        in_fifo_name = pattern.fifo_name+"_fifo_from_pc"
        in_fifo = self._fpga_dict[pattern.fpga_name].get_fifo(in_fifo_name)
        out_fifo_name = pattern.fifo_name+"_fifo_to_pc"
        out_fifo = self._fpga_dict[pattern.fpga_name].get_fifo(out_fifo_name)
        dbg = self._interface[pattern.fpga_name]

        #Ensure that there is enough memory on the host side for the pattern we want to run.
        if in_fifo.ref.buffer_size < pattern.len+FPGA_READBACK_OFFSET:
            in_fifo.ref.configure(pattern.len+FPGA_READBACK_OFFSET)

        if out_fifo.ref.buffer_size < pattern.len+FPGA_READBACK_OFFSET:
            out_fifo.ref.configure(pattern.len+FPGA_READBACK_OFFSET)

            
        #Update Pattern Size in the FPGA
        dbg.interact("w","Buffer_Pass_Size",pattern.len+FPGA_READBACK_OFFSET)

        # (Allow host memory settings to sink in.)
        time.sleep(1)

        #Check Actual allocated buffer size
        print("(DBG) out buffer size:",out_fifo.ref.buffer_size)
        print("(DBG) in buffer size:",in_fifo.ref.buffer_size)

        #Load the pattern into FIFO memory.
        dbg.interact("w",in_fifo_name,pattern.vector)

        # Create a thread to read back the io fifo in parallel.
        return_data_idx = len(self._return_data)
        self._return_data.append([])
        reader = Thread(target=self.thread_read, args=(pattern.len+FPGA_READBACK_OFFSET,pattern,return_data_idx))

        return reader

    # run_pattern() - Function for running a Glue Wave and getting the results.
    # PARAMETERS:
    #           pattern - A list of GlueWave() objects or .glue files that can be read to GlueWave() objects
    #           outfile - Optional .glue filename to write the result to.
    def run_pattern(self,patterns,outfile_tag=None):

        #Make sure "patterns" is a list :p
        if type(patterns) is not list:
            patterns = [patterns]

        #If it's a filename, we use read_glue() to get the actual GlueWave() object.
        for i in range(len(patterns)):
            if type(patterns[i]) == str:
                patterns[i] = self.gc.read_glue(patterns[i])
                print("(DBG) Pattern Len from File:",len(patterns[i].vector))

        #Set up buffers and reader threads.
        reader_threads = []
        for pattern in patterns:
            reader_threads.append(self.setup_pattern(pattern))

        if len(self._interface.values()) > 1:
            print("ERROR: NOT YET IMPLEMENTED! If we have multiple distinct pieces of hardware, how to ensure they start simultaneously?")
            exit()
        else:
            dbg = list(self._interface.values())[0]

        ## Critical Timing: Must be < timeout ##
        for t in reader_threads:
            t.start()
        dbg.interact("w","Run_Pattern",True)
        ## End Critical Timing ##

        for t in reader_threads:
            t.join()

        dbg.interact("w","Run_Pattern",False)


        #Process the data returned by each thread.
        for i in range(len(self._return_data)):
            data = self._return_data[i][FPGA_READBACK_OFFSET:patterns[i].len+FPGA_READBACK_OFFSET]

            out_pattern = GlueWave(data,1e12/FPGA_CLOCK_HZ,patterns[i].hardware,{"GLUE_TIMESTEPS":str(len(data))})

            #Write a glue output file.
            if outfile_tag is not None:
                self.gc.write_glue(out_pattern,outfile_tag+"_"+patterns[i].hardware_str.replace("/","_")+".glue")

        #Clear self._return_data so it can be used next time.
        self._return_data = []
        

    # thread_read() - Function for reading back a fifo_to_pc output asynchronously using a thread;
    #                 requires the length to read, and a copy of the input GlueWave() so it can extract hardware info.
    def thread_read(self, read_len, in_pattern,return_data_idx):
        #y is a tuple, where y[0] is the returned glue waveform.

        dbg = self._interface[in_pattern.fpga_name]
        out_fifo_name = in_pattern.fifo_name+"_fifo_to_pc"
    
        y = dbg.interact("r",out_fifo_name,read_len)

        self._return_data[return_data_idx] = y[0]

    ### MEM Functions work on a version of Glue that uses on-fpga memory. ###
    ### ... at this point, these are pretty much deprecated. ###
    
##    # update_pattern - Given a Glue pattern as an integer list OR a filename,
##    #                   place that pattern in FPGA memory.
##    def MEM_update_pattern(self, pattern) -> None:
##
##        if type(pattern) == str:
##            with open(pattern, "r") as read_file:
##                pattern_file_text = read_file.read()
##
##            pattern = [int(x) for x in pattern_file_text.split(",")]
##        
##        self._interface.interact("w","io_fifo_from_pc", pattern)
##        self._interface.interact("w","Write_to_Mem",True)
##        self._interface.interact("w","Write_to_Mem",False)
##
##
##        
##    def MEM_run_pattern_once(self) -> None:
##        self._interface.interact("w","Run_Pattern",True)
##        self._interface.interact("w","Run_Pattern",False)
##
##
##    def MEM_read_output(self) -> list[int]:
##        self._interface.interact("w","Read_from_Mem",True)
##        self._interface.interact("w","Read_from_Mem",False)
##        y = self._interface.interact("r","io_fifo_to_pc",1024)
##        #y is a tuple, where y[0] is the returned glue waveform.
##        return y[0]
##        pass
##
##    def MEM_read_output_file(self, outfile) -> None:
##        out = self.MEM_read_output()
##
##        with open(outfile,"w") as write_file:
##            write_file.write([str(x) for x in out].join(", "))



# ASSUMPTION: The intended pattern is a uniformly increasing set of integers.
# rp = Returned pattern
def diagnose_fifo_timeout(rp):

    pattern_started = False
    in_timeout = False
    timeout_count = 0
    last_timeout = 0
    this_timeout = 0

    for i in range(len(rp)):
        if i > 2 and rp[i] == 3 and rp[i-1] == 2 and rp[i-2] == 1 and rp[i-3] == 0:
           pattern_started = True

        if pattern_started:

            if in_timeout:
                #Timeout ends
                if rp[i] == this_timeout + 1:
                    print("(WARN) Timeout at value",this_timeout,"lasting",timeout_count,"cycles. (",(this_timeout-last_timeout),"counts since last timeout. )")
                    in_timeout = False
                    timeout_count = 0
                    last_timeout = this_timeout

                #It was a skip timeout.
                elif rp[i] == rp[i-1] + 1:
                    print("(WARN) Skip from",this_timeout,"to",rp[i-1])
                    in_timeout = False
                    timeout_count = 0
                    last_timeout = this_timeout
                #Timeout continues.
                else:
                    timeout_count = timeout_count + 1


            else:
                #Timeout begins
                if rp[i] != rp[i-1] + 1:
                    in_timeout = True
                    timeout_count = 1
                    this_timeout = rp[i-1]

                #Normal count continues.
                else:
                    continue

    if not pattern_started:
        print("(ERR) No incrementing pattern detected in this Glue wave :(")

    if this_timeout == 0:
        print("(INFO) No timeouts detected :D")
                
            


##class GenericPatternRunner(PatternRunner):
##    _default_regs_config = {
##        "Write_to_Mem": False,
##        "Read_from_Mem": False,
##        "Run_Pattern": False,
##        "Buffer_In_Size": 1024,
##        "Buffer_Out_Size": 512,
##        "Buffer_Pass_Size": 512,
##        "FPGA_Loop_Dis": False
##    }
##
##    def __init__(self, logger: liblog.Logger, fpga_resource: str, fpga_bitfile: str = None):
##        if fpga_bitfile is None:
##            src_path = os.path.dirname(os.path.realpath(__file__))
##            fpga_bitfile = f"{src_path}/../resources/generic_pattern_runner.lvbitx"
##        super().__init__(logger, fpga_resource, fpga_bitfile)
##
##    def initialize(self) -> None:
##        super().initialize()
##
##        for name, val in self._default_regs_config:
##            self._log.debug(f"Setting \"{name}\" register to default value of \"{val}\"")
##            self._fpga.get_register(name).value = val
