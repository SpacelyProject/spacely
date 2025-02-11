from fnal_ni_toolbox import *
import fnal_log_wizard as liblog
from abc import ABC
import os
import time
from threading import Thread


#####################################################################
##                CARIBOU PATTERN RUNNER                           ##
#####################################################################


class CaribouPatternRunner:
    
    def __init__(self, logger, gc, Caribou_inst):
        self._log = logger
        self.gc = gc
        self.car = Caribou_inst
        
        # Return mode for run_pattern():
        # 0 - Don't return anything (i.e. no need to read back samples)
        # 1 - Return GlueWave object
        # 2 - Write to file and return file name.
        
        self.default_return_mode = 1
    
    def run_pattern(self, glue_wave, tsf=1, return_mode=None, read_only=False):
        """Runs a pattern from a Glue Wave on a Spacely-Caribou APG.
           Returns the name of the sampled Glue Wave, or -1 on error.
           """

        
        #Parse glue file names OR python objects
        if type(glue_wave) == str:
            glue_wave = self.gc.read_glue(glue_wave)

        #Give up on error.    
        if glue_wave == -1:
            self._log.error("GlueWave was -1, cannot run pattern.")
            return

        
        ## (-1) Pick up APG name from glue_wave hardware definition.
        apg_name = glue_wave.hardware[1]
        
        if glue_wave.hardware[2] != "write":
            self._log.error(f"CaribouPatternRunner error: Attempted to write a GlueWave to APG {apg_name}, but GlueWave is configured to use the APG's '{glue_wave.hardware[2]}' interface (should be 'write')")
            return -1

        ## (0) Wait for idle, then clear the write buffer.
        self.apg_wait_for_idle(apg_name)
        self.car.set_memory(f"{apg_name}_clear",1)

        ## (1) SET NUMBER OF SAMPLES
        N = glue_wave.len

        self.car.set_memory(f"{apg_name}_n_samples", N)

        ## (2) WRITE PATTERN TO APG
        #read_only argument allows us to skip writes.
        if not read_only:
            for n in range(N):
                #Implement time scaling.
                for _ in range(tsf):
                    self.car.set_memory(f"{apg_name}_write_channel",glue_wave.vector[n])


        ## (3) RUN AND WAIT FOR IDLE
        self.car.set_memory(f"{apg_name}_run", 1)

        time.sleep(0.01)
        self.apg_wait_for_idle(apg_name)

        if return_mode is None:
            return_mode = self.default_return_mode

        ## (4) READ BACK SAMPLES
        if return_mode > 0:
            samples = []

            for n in range(N):
                samples.append(self.car.get_memory(f"{apg_name}_read_channel"))


            APG_CLOCK_FREQUENCY = 10e6
            strobe_ps = 1/APG_CLOCK_FREQUENCY * 1e12
            
            read_glue = GlueWave(samples,strobe_ps,f"Caribou/{apg_name}/read")

        else:
             self.car.set_memory(f"{apg_name}_clear",1)

        if return_mode == 0:
            return None
            
        elif return_mode == 1:
            return read_glue
            
        elif return_mode == 2:
            read_glue_file = f"Caribou_{apg_name}_read_samp.glue"
            self.gc.write_glue(read_glue,read_glue_file)

            return read_glue_file
        
        
    def update_io_defaults(self, apg_name):
        """Updates the field apg_write_defaults for the named APG to match self.gc.IO_Default"""
        
        io_default = 0
        #For each ASIC input I/O, set the corresponding io_dir bit.
        for io in self.gc.Input_IOs:
            pos = self.gc.IO_pos[io]
            default = self.gc.IO_default[io]
            if default > 0:
                io_default = io_default + (1 << pos)
                
        self.car.set_memory(f"{apg_name}_write_defaults",io_default)
        
        self._log.debug(f"Wrote {io_default} to {apg_name}_write_defaults")

    def set_io_default(self, io_name, value):
        """Set the io default value for one named io, and send that value to hardware."""

        if io_name not in self.gc.Input_IOs:
            self._log.error(f"{io_name} is not a defined ASIC input.")
            return -1

        # Get the middle part of the hw str representation, which should be the apg name.
        this_io_apg = self.gc.IO_hardware[io_name].split("/")[1]

        self.gc.IO_default[io_name] = value

        self.update_io_defaults(this_io_apg)
        
    def apg_wait_for_idle(self, apg_name):
        while True:
            status = self.car.get_memory(f"{apg_name}_status")

            if status == 0:
                break

            time.sleep(0.1)

#####################################################################
##                NI FPGA PATTERN RUNNER                           ##
#####################################################################
################## GlueFPGA Implementation Constants ################
# When you read back waveforms from the FPGA, you will read back this many zeros first.
#FPGA_READBACK_OFFSET = 3
#FPGA_CLOCK_HZ = 40e6

#Class to represent a Glue Bitfile with all its associated information. 
class GlueBitfile():

    def __init__(self,FPGA_SERIAL_NUM, IO_SERIAL_NUM, FPGA_READBACK_OFFSET, FPGA_CLOCK_HZ, FPGA_CONFIG_DICT, BITFILE):
        self.FPGA_SERIAL_NUM = FPGA_SERIAL_NUM
        self.IO_SERIAL_NUM = IO_SERIAL_NUM
        self.FPGA_READBACK_OFFSET = FPGA_READBACK_OFFSET
        self.FPGA_CLOCK_HZ = FPGA_CLOCK_HZ
        self.FPGA_CONFIG_DICT = FPGA_CONFIG_DICT
        self.BITFILE = BITFILE


GLUEFPGA_DEFAULT_CFG = { "Run_Test_Fifo_Loopback" : False,
                        "Run_Pattern"  : False,
                        "Buffer_In_Size": 1024,
                        "Buffer_Pass_Size":1024,
                        "FPGA_Loop_Dis": False,
                        "se_io_data_dir":0,
                        "lvds_data_dir":0,
                        "ddca_P0_WE":False,
                        "ddca_P1_WE":False,
                        "ddca_P2_WE":False,
                        "ddcb_P0_WE":False,
                        "ddcb_P1_WE":False,
                        "ddcb_P2_WE":False,
                        "lvds_clockout_en":False,
                        "SE_Data_Default":60,
                        "Set_Voltage_Family":True,
                        "Voltage_Family":4} 

SPACELY_BITFILE_FOLDER = os.path.dirname(os.path.realpath(__file__))+"\\..\\..\\Glue RTL2FPGA Source\\FPGA Bitfiles"



GLUEFPGA_BITFILES = {"NI7976_NI6583_40MHz":GlueBitfile("NI7976","NI6583",3,40e6,GLUEFPGA_DEFAULT_CFG,
                                                               SPACELY_BITFILE_FOLDER+"\\GlueDirectBitfile_6_27_b.lvbitx"),
                     "NI7972_NI6583_40MHz":GlueBitfile("NI7972","NI6583",3,40e6,GLUEFPGA_DEFAULT_CFG,
                                                               SPACELY_BITFILE_FOLDER+"\\GlueDirectBitfile_NI7972_NI6583_40M_9_8_2023_b.lvbitx"),
                     "NI7962_NI6581_40MHz":GlueBitfile("NI7972","NI6581",3,40e6,GLUEFPGA_DEFAULT_CFG,
                                                               SPACELY_BITFILE_FOLDER+"\\GlueDirectBitfile_NI7962_NI6581_40M_PROTO_12_6_2023.lvbitx")}

# This dictionary lists the valid FIFOs for each NI RIO I/O card to enable lint checking.
NI_IO_CARD_VALID_FIFOS = {"NI6583" : ["lvds", "se_io"],
                          "NI6581" : ["ddca_P0", "ddca_P1", "ddca_P2", "ddcb_P0", "ddcb_P1", "ddcb_P2"]}

         

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






class NIPatternRunner:
    _fpga: NiFpga = None

    # Initialize NIPatternRunner() Object
    # Args:
    #       logger = logger
    #       iospecfile = iospecfile
    #       fpga_bitfile_map = Dictionary specifying which of the possible bitfiles should be used for each slot.
    #                          Bitfile names should be chosen from GLUEFPGA_BITFILES.keys(), i.e. {"PXI1Slot5":"NI7976_NI6583_40MHz"}
    def __init__(self, logger: liblog.Logger, iospecfile, fpga_bitfile_map, pattern=None):
        self._log = logger
        self._interface = {}
        self._fpga_dict = {}
        
        self.iospecfile = iospecfile
        self.fpga_bitfile_map = fpga_bitfile_map

        #Init an instance of GlueConverter to handle GlueWave() operations.
        self.gc = GlueConverter(iospecfile)
        
        if not self.gc.loaded_iospec_file:
            self._log.error("NIPatternRunner could not be set up due to failure parsing iospec file.")
            return None

        if self.hardware_cfg_lint() == -1:
            return

        #Create an internal data structure with software handles to each FPGA we care about.
        #NOTE: This function sets up the self._fpga_dict and self._interface dictionaries.
        if self.initialize_hardware(self._log,fpga_bitfile_map) == -1:
            return

        #For each of these FPGAs, initialize a debugger, and configure them by using the right
        #config for their bitfile.
        #for hw in self._fpga_dict.keys():
        #    self._interface[hw] = NiFpgaDebugger(logger, self._fpga_dict[hw])
        #    self._interface[hw].configure(GLUEFPGA_DEFAULT_CFG)

        #    print("(DBG) Pulsing Set_Voltage_Family")
        #    #Pulse "Set_Voltage_Family" to ensure voltage family is actually set correctly.
        #    self._interface[hw].interact("w","Set_Voltage_Family",False)
        #    time.sleep(1)
        #    self._interface[hw].interact("w","Set_Voltage_Family",True)
        #    time.sleep(1)
        #    self._interface[hw].interact("w","Set_Voltage_Family",False)
        
        self._return_data = []
        
        if self._update_io_dir() == -1:
            return
            
        self.update_io_defaults()

        if pattern is not None:
            self.update_pattern(pattern)


    #This function performs a lint check on the hardware detected in the IOspec.
    def hardware_cfg_lint(self):
    
        #For each HW configuration present in the iospec...
        for hw in self.gc.IO_hardware.values():
            slot_name, io_module, fifo = hw.split("/")
            
            #Find the appropriate bitfile for that slot:
            try:
                bitfile_name = self.fpga_bitfile_map[slot_name]
            except KeyError:
                self._log.error(f"Your .iospec file references \"{slot_name}\" but \nyou did not provide a bitfile for that slot in your fpga_bitfile_map.")
                return -1
            
            #Check that the I/O module in .iospec and the bitfile match.
            bitfile_io = GLUEFPGA_BITFILES[bitfile_name].IO_SERIAL_NUM    
            if io_module != bitfile_io:
                self._log.error(f"The bitfile you have chosen for slot {slot_name} works for NI FlexRIO card {bitfile_io}, but your .iospec file contains pins mapped for {io_module}.")
                return -1
            
            #Check that the FIFO specified in your iospec is correct.
            valid_fifos = NI_IO_CARD_VALID_FIFOS[io_module]
            list_of_valid_fifos = ", ".join(valid_fifos)
            if fifo not in valid_fifos:
                self._log.error(f"Your iospec maps some pins to FIFO={fifo}, but your FPGA bitfile only supports the following FIFOs: {list_of_valid_fifos}")
                return -1
                
        
        return 0

    # initialize_hardware() - This function sets up a hardware dictionary and initializes
    #  all FPGAs required for the I/Os in iospec. 
    def initialize_hardware(self,log,fpga_bitfile_map):

        #For every hardware resource required by an I/O in the iospec...
        for hw in self.gc.IO_hardware.values():
            #Parse the resource/slot name.
            slot_name = hw.split("/")[0]
            
            #Find the appropriate bitfile for that slot:
            try:
                bitfile_name = fpga_bitfile_map[slot_name]
            except KeyError:
                self._log.error(f"Your .iospec file references \"{slot_name}\" but \nyou did not provide a bitfile for that slot in your fpga_bitfile_map.")
                return -1

            #The identifier we will use for this FPGA in THIS session is
            #it's slot name + the I/O name (ig because the I/O capabilities are
            #important and can be easily seen from the front of the chassis)
            fpga_name = "/".join(hw.split("/")[0:2])

            #If we haven't already set up this FPGA in _fpga_dict and _interface, do it.
            if fpga_name not in self._fpga_dict.keys():
                self._log.debug(f"Initializing FPGA Hardware:{fpga_name}...")
                
                try:
                    #Create NiFpga Object using Slot Name (and store the bitfile_name for later reference)
                    self._fpga_dict[fpga_name] = NiFpga(log, slot_name, bitfile_name=bitfile_name)
                    #Flash the correct bitfile
                    self._fpga_dict[fpga_name].start(GLUEFPGA_BITFILES[bitfile_name].BITFILE)
                except Exception as e:
                    print(e)
                    if "InvalidResourceName" in e.__str__():
                        self._log.error(f"FAILED to communicate with FPGA at slot {slot_name}. Please double-check that you can see the FPGA in NI MAX and that the slot name is correct. (Remember, it's not always PXI1Slot(N)).") 
                        return -1
                    else:
                        raise e
                    
                
                #Start an interface referencing the object we just created.
                self._interface[fpga_name] = NiFpgaDebugger(log, self._fpga_dict[fpga_name])
                #Configure as appropriate for the bitfile.
                self._interface[fpga_name].configure(GLUEFPGA_BITFILES[bitfile_name].FPGA_CONFIG_DICT)
                

    # update_io_defaults() - Sets all IOs to their default state from iospec.
    def update_io_defaults(self, hw_name=None):
        
        if hw_name is not None:
            self._log.error("Error -- feature not yet implemented: NI Pattern Runner update io defaults for only one hw object.")
        
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
                self._log.debug(f"Programming {hw} I/O Defaults as: {io_default[hw]}")
                print("WARNING!!! Need to implement I/O defaults for multi-hardware")
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
            io_dir[hw] = io_dir[hw] | (1 << pos)

        #Write all these updated I/O dirs to the right hardware.
        for hw in hw_list:
            fpga_name = "/".join(hw.split("/")[0:2])
            fifo = hw.split("/")[2]
            
            #Determine whether this FPGA sets data direction by bit, or by port.
            if fifo+"_data_dir" in GLUEFPGA_DEFAULT_CFG.keys():
                #Set direction by bit.
                self._log.debug(f"Programming {hw} I/O Direction as: {io_dir[hw]}")
                self._interface[fpga_name].interact("w",fifo+"_data_dir",io_dir[hw])
            else:
                #Set direction by port.
                this_port_contains_asic_inputs = False
                this_port_contains_asic_outputs = False
                
                #If there are any ASIC inputs which use this hw...
                for io in self.gc.Input_IOs:
                    if self.gc.IO_hardware[io] == hw:
                        this_port_contains_asic_inputs = True
                    
                for io in self.gc.Output_IOs:
                    if self.gc.IO_hardware[io] == hw:
                        this_port_contains_asic_outputs = True        
                
                
                if this_port_contains_asic_inputs and this_port_contains_asic_outputs:
                    self._log.error(f"{fpga_name} sets I/O direction by port. You cannot have both inputs & outputs in the same port!")
                    return -1
                
                
                self._log.debug(f"Programming {hw} I/O Direction as: {this_port_contains_asic_inputs}")
                self._interface[fpga_name].interact("w",fifo+"_WE",this_port_contains_asic_inputs)


    # setup_pattern() - Performs the following tasks to prepare for running a pattern:
    #   -- Configures the host buffer size to be sufficient
    #   -- Sets Buffer_Pass_Size on the FPGA
    #   -- Loads the pattern into host memory
    #   -- sets up (but doesn't run) a reader thread that will dump into a slot in self._return_data
    def setup_pattern(self,pattern):

        self._log.debug(f"Setting up pattern for hardware resource: {pattern.hardware_str}")

        #Get the fpga object which we will be sending this pattern to. 
        fpga = self._fpga_dict[pattern.fpga_name]

        #Extract some important parameters for this specific bitfile.
        FPGA_READBACK_OFFSET = GLUEFPGA_BITFILES[fpga._bitfile_name].FPGA_READBACK_OFFSET
        FPGA_CLOCK_HZ = GLUEFPGA_BITFILES[fpga._bitfile_name].FPGA_CLOCK_HZ

        #Identify the correct fifos and debugger based on the hardware specification of pattern.
        in_fifo_name = pattern.fifo_name+"_fifo_from_pc"
        in_fifo = fpga.get_fifo(in_fifo_name)
        out_fifo_name = pattern.fifo_name+"_fifo_to_pc"
        out_fifo = fpga.get_fifo(out_fifo_name)
        dbg = self._interface[pattern.fpga_name]
        
        #Ensure that there is enough memory on the host side for the pattern we want to run.
        
        try:
            in_fifo.ref.buffer_size
            READ_BUFFER_SIZE_SUPPORTED = True
        except Exception as e:
            if "FeatureNotSupported" in e.__str__():
                self._log.warning("Unable to get buffer sizes due to FeatureNotSupported")
                READ_BUFFER_SIZE_SUPPORTED = False
            else:
                raise(e)
        
        
        if not READ_BUFFER_SIZE_SUPPORTED or (in_fifo.ref.buffer_size < pattern.len+FPGA_READBACK_OFFSET):
            in_fifo.ref.configure(pattern.len+FPGA_READBACK_OFFSET)

        if not READ_BUFFER_SIZE_SUPPORTED or (out_fifo.ref.buffer_size < pattern.len+FPGA_READBACK_OFFSET):
            out_fifo.ref.configure(pattern.len+FPGA_READBACK_OFFSET)
        
            
        #Update Pattern Size in the FPGA
        #11/9/2023 NOTE: This "-1" is necessary to solve the Glue wave frame misalignment issue. 
        #Basically without it, frames that are read back will be offset by 1 bit / iteration from what you put in.
        dbg.interact("w","Buffer_Pass_Size",pattern.len+FPGA_READBACK_OFFSET-1)

        # (Allow host memory settings to sink in.)
        time.sleep(0.2)

        #Check Actual allocated buffer size
        if READ_BUFFER_SIZE_SUPPORTED:
            self._log.debug("out buffer size: "+str(out_fifo.ref.buffer_size))
            self._log.debug("in buffer size: "+str(in_fifo.ref.buffer_size))

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
    def run_pattern(self,patterns,time_scale_factor=1,outfile_tag=None):

        ## INPUT PROCESSING AND LINT CHECKING

        if type(time_scale_factor) is not int:
            self._log.error("run_pattern(): time_scale_factor must be an integer.")
            return -1
        
        if type(outfile_tag) is not str:
            if outfile_tag == None:
                self._log.warning("run_pattern(): No outfile_tag was specified, so no outfile will be printed.")
            else:
                self._log.error("run_pattern(): Could not parse the value specified for outfile_tag. No outfile will be printed.")
                outfile_tag = None

        #Make sure "patterns" is a list of GlueWaves, or string filenames.
        if type(patterns) is str or type(patterns) is GlueWave:
            patterns = [patterns]
            
        if type(patterns) is tuple:
            patterns = [i for i in patterns]
            
        if type(patterns) is not list:
            self._log.error(f"run_pattern could not parse patterns={patterns}")
            return

        #If patterns contains filenames, we use read_glue() to get the actual GlueWave() object.
        for i in range(len(patterns)):
            if type(patterns[i]) == str:
                patterns[i] = self.gc.read_glue(patterns[i])
                self._log.debug(f"Pattern Len from File:{len(patterns[i].vector)}")

            try:
                fpga = self._fpga_dict[patterns[i].fpga_name]
            except KeyError:
                print("(ERR) This pattern was generated for hardware",patterns[i].fpga_name)
                print("      But the only hardware that was initialized is:",[x for x in self._fpga_dict.keys()])
                print("      If you are SURE this is the right pattern, edit the Glue file to add a valid HARDWARE.")
                return -1

        ## TIME SCALE FACTOR

        #Built-in method to slow down the pattern by a factor of time_scale_factor
        if time_scale_factor != 1:
            for i in range(len(patterns)):
                patterns[i].vector = [x for x in patterns[i].vector for _ in range(0,time_scale_factor)]
                patterns[i].len = len(patterns[i].vector)

        ## SETUP 
                
        #Set up buffers and reader threads.
        reader_threads = []
        for pattern in patterns:
            reader_threads.append(self.setup_pattern(pattern))

        if len(self._interface.values()) > 1:
            print("ERROR: NOT YET IMPLEMENTED! If we have multiple distinct pieces of hardware, how to ensure they start simultaneously?")
            exit()
        else:
            dbg = list(self._interface.values())[0]
            #Get the fpga object which we will be sending this pattern to. 
            fpga = list(self._fpga_dict.values())[0]

            #Extract some important parameters for this specific bitfile.
            FPGA_READBACK_OFFSET = GLUEFPGA_BITFILES[fpga._bitfile_name].FPGA_READBACK_OFFSET
            FPGA_CLOCK_HZ = GLUEFPGA_BITFILES[fpga._bitfile_name].FPGA_CLOCK_HZ

        ## Critical Timing: Must be < timeout ##
        for t in reader_threads:
            t.start()
        dbg.interact("w","Run_Pattern",True)
        ## End Critical Timing ##

        for t in reader_threads:
            t.join()

        dbg.interact("w","Run_Pattern",False)


        output_filenames = []

        #Process the data returned by each thread.
        for i in range(len(self._return_data)):
            data = self._return_data[i][FPGA_READBACK_OFFSET:patterns[i].len+FPGA_READBACK_OFFSET]

            out_pattern = GlueWave(data,1e12/FPGA_CLOCK_HZ,patterns[i].hardware,{"GLUE_TIMESTEPS":str(len(data))})

            #Write a glue output file.
            if outfile_tag is not None:
                outfile_name = outfile_tag+"_"+patterns[i].hardware_str.replace("/","_")+".glue"
                self.gc.write_glue(out_pattern,outfile_name)
                output_filenames.append(outfile_name)

        #Clear self._return_data so it can be used next time.
        self._return_data = []
        
        return output_filenames

    # thread_read() - Function for reading back a fifo_to_pc output asynchronously using a thread;
    #                 requires the length to read, and a copy of the input GlueWave() so it can extract hardware info.
    def thread_read(self, read_len, in_pattern,return_data_idx):
        #y is a tuple, where y[0] is the returned glue waveform.

        dbg = self._interface[in_pattern.fpga_name]
        out_fifo_name = in_pattern.fifo_name+"_fifo_to_pc"
    
        y = dbg.interact("r",out_fifo_name,read_len)

        self._return_data[return_data_idx] = y[0]

    ### OBSOLETE! Use sg.gc.dict2Glue()
    #def genpattern_from_waves_dict(self, waves_dict, time_scale_factor=1):
    #
    #    #2) Writing to an ASCII file.
    #    with open("genpattern.txt",'w') as write_file:
    #        for w in waves_dict.keys():
    #            if time_scale_factor != 1:
    #                write_file.write(w+":"+"".join([str(x) for x in waves_dict[w] for _ in range(0,time_scale_factor)])+"\n")
    #            else:
    #                write_file.write(w+":"+"".join([str(x) for x in waves_dict[w]])+"\n")
    #            
    #    #3) Convert ASCII file to Glue
    #    return self.gc.ascii2Glue("genpattern.txt", 1, "genpattern")
        
        

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
                
            
