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

#####################################################################


#PatternRunner usage model:
#
# At the top level of Spacely, we will initialize an FPGA resource with a given bitfile.
# This is similar to how we initialize other instruments, and it makes sense because
# the Glue bitfile should be relatively universal, not changing per pattern.
#
# Each PatternRunner will be used to run a specific pattern, for example programming
# a config register, or communicating over SPI. The PatternRunner class requires
# (1) the fpga object it is supposed to use for communication, (2) the iospec for this
# specific pattern, which tells it which IOs to set as Write vs Read, and (3)
# (optionally) the pattern it is supposed to run, which we can also update later.
#
# For basic example, see ROUTINE3


class PatternRunner(ABC):
    _fpga: NiFpga = None

    def __init__(self, logger: liblog.Logger, fpga, iospecfile, pattern=None):
        self._log = logger
        self._fpga = fpga
        self._interface = NiFpgaDebugger(logger, fpga)
        self._iospec = {}
        self._return_data = []

        #Read iospec file and parse it into a dictionary.
        with open(iospecfile,"r") as read_file:
            iospec_lines = read_file.readlines()
            
        #Lines in the iospec file have the format:
        #{signal name},{I/O},{port number}
        for line in iospec_lines:
            if len(line) > 1 and not line.startswith("//"):
                a = line.split(",")
                self._iospec[a[0]] = [a[1],int(a[2])]


        self._update_io_dir()

        if pattern is not None:
            self.update_pattern(pattern)


    # _update_io_dir - Updates the direction of FPGA IOs to conform to the iospec.
    def _update_io_dir(self) -> None:
        io_dir = 0
        for io in self._iospec.values():
            if "O" in io[0]:
                io_dir = io_dir + (1 << io[1])

        print("<DBG> Programming I/O Direction as:",io_dir)
        self._interface.interact("w","SE_Data_Dir",io_dir)


    def run_pattern(self,pattern,outfile=None):

        #Support patterns from file, or from a list.
        if type(pattern) == str:
            with open(pattern, "r") as read_file:
                pattern_file_text = read_file.read()

            pattern = [int(x) for x in pattern_file_text.split(",")]

        #Ensure that there is enough memory on the host side for the pattern we want to run.
        if self._fpga.get_fifo("io_fifo_from_pc").ref.buffer_size < len(pattern)+FPGA_READBACK_OFFSET:
            self._fpga.get_fifo("io_fifo_from_pc").ref.configure(len(pattern)+FPGA_READBACK_OFFSET)

        if self._fpga.get_fifo("io_fifo_to_pc").ref.buffer_size < len(pattern)+FPGA_READBACK_OFFSET:
            self._fpga.get_fifo("io_fifo_to_pc").ref.configure(len(pattern)+FPGA_READBACK_OFFSET)

        #self._fpga.get_fifo("io_fifo_from_pc").ref.configure(10000)
        #self._fpga.get_fifo("io_fifo_to_pc").ref.configure(30000)
            
        #Update Pattern Size in the FPGA
        self._interface.interact("w","Buffer_Pass_Size",len(pattern)+FPGA_READBACK_OFFSET)

        # (Allow host memory settings to sink in.)
        time.sleep(1)

        #Check Actual allocated buffer size
        print(self._fpga.get_fifo("io_fifo_to_pc").ref.buffer_size)
        print(self._fpga.get_fifo("io_fifo_from_pc").ref.buffer_size)

        #Load the pattern into FIFO memory.
        self._interface.interact("w","io_fifo_from_pc",pattern)

        # Create a thread to read back the io fifo in parallel.
        reader = Thread(target=self.thread_read, args=(len(pattern)+FPGA_READBACK_OFFSET,))

        ## Critical Timing: Must be < timeout ##
        reader.start()
        self._interface.interact("w","Run_Pattern",True)
        ## End Critical Timing ##

        reader.join()

        self._interface.interact("w","Run_Pattern",False)
        
        data = self._return_data
        
        if outfile is not None:
            with open(outfile,"w") as write_file:
                write_file.write(", ".join([str(x) for x in data]))

        return data[FPGA_READBACK_OFFSET:len(pattern)+FPGA_READBACK_OFFSET]


    def thread_read(self, read_len):
        #y is a tuple, where y[0] is the returned glue waveform.
    
        y = self._interface.interact("r","io_fifo_to_pc",read_len)

        self._return_data = y[0]

    ### MEM Functions work on a version of Glue that uses on-fpga memory. ###
    
    # update_pattern - Given a Glue pattern as an integer list OR a filename,
    #                   place that pattern in FPGA memory.
    def MEM_update_pattern(self, pattern) -> None:

        if type(pattern) == str:
            with open(pattern, "r") as read_file:
                pattern_file_text = read_file.read()

            pattern = [int(x) for x in pattern_file_text.split(",")]
        
        self._interface.interact("w","io_fifo_from_pc", pattern)
        self._interface.interact("w","Write_to_Mem",True)
        self._interface.interact("w","Write_to_Mem",False)


        
    def MEM_run_pattern_once(self) -> None:
        self._interface.interact("w","Run_Pattern",True)
        self._interface.interact("w","Run_Pattern",False)


    def MEM_read_output(self) -> list[int]:
        self._interface.interact("w","Read_from_Mem",True)
        self._interface.interact("w","Read_from_Mem",False)
        y = self._interface.interact("r","io_fifo_to_pc",1024)
        #y is a tuple, where y[0] is the returned glue waveform.
        return y[0]
        pass

    def MEM_read_output_file(self, outfile) -> None:
        out = self.MEM_read_output()

        with open(outfile,"w") as write_file:
            write_file.write([str(x) for x in out].join(", "))



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
                
                







class GenericPatternRunner(PatternRunner):
    _default_regs_config = {
        "Write_to_Mem": False,
        "Read_from_Mem": False,
        "Run_Pattern": False,
        "Buffer_In_Size": 1024,
        "Buffer_Out_Size": 512,
        "Buffer_Pass_Size": 512,
        "FPGA_Loop_Dis": False
    }

    def __init__(self, logger: liblog.Logger, fpga_resource: str, fpga_bitfile: str = None):
        if fpga_bitfile is None:
            src_path = os.path.dirname(os.path.realpath(__file__))
            fpga_bitfile = f"{src_path}/../resources/generic_pattern_runner.lvbitx"
        super().__init__(logger, fpga_resource, fpga_bitfile)

    def initialize(self) -> None:
        super().initialize()

        for name, val in self._default_regs_config:
            self._log.debug(f"Setting \"{name}\" register to default value of \"{val}\"")
            self._fpga.get_register(name).value = val
