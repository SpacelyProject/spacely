from fnal_ni_toolbox import *
import fnal_log_wizard as liblog
from abc import ABC
import os
import time

################## GlueFPGA Implementation Constants ################
# When you read back waveforms from the FPGA, you will read back this many zeros first.
FPGA_READBACK_OFFSET = 3

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

        #Load the pattern into FIFO memory.
        self._interface.interact("w","io_fifo_from_pc",pattern)


        #Run Pattern!
        self._interface.interact("w","Run_Pattern",True)

        self._interface.interact("w","Run_Pattern",False)


        #y is a tuple, where y[0] is the returned glue waveform.
    
        y = self._interface.interact("r","io_fifo_to_pc",len(pattern)+FPGA_READBACK_OFFSET)
   
        if outfile is None:
            return y[0][FPGA_READBACK_OFFSET:len(pattern)+FPGA_READBACK_OFFSET]
        else:
            with open(outfile,"w") as write_file:
                write_file.write([str(x) for x in y[0]].join(", "))

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
