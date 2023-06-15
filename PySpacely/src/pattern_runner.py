from fnal_ni_toolbox import NiFpga as FnalNiFpga
import fnal_log_wizard as liblog
from abc import ABC
import os


class PatternRunner(ABC):
    _fpga: FnalNiFpga = None

    def __init__(self, logger: liblog.Logger, fpga_resource: str, fpga_bitfile: str):
        self._log = logger
        self.fpga_res = fpga_resource
        self.fpga_code = fpga_bitfile

    def initialize(self) -> None:
        self._log.debug(f"Initializing FPGA at {self.fpga_res}")
        self._fpga = FnalNiFpga(self._log, self.fpga_res)

        self._log.blocking(f"Starting FPGA at {self.fpga_res} with bitfile {self.fpga_code}")
        try:
            self._fpga.start(self.fpga_code)
            self._log.block_res(True)
        except Exception as e:
            self._log.block_res(False)
            self._fpga = None
            raise e

    def init_pattern(self, pattern: list[int]) -> None:
        pass

    def start_pattern(self) -> None:
        pass

    def stop_pattern(self) -> None:
        pass

    def read_output(self) -> list[int]:
        pass


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
