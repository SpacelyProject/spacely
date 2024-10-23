#
# Virtual Caribou 
# aquinn@fnal.gov -- 10/16/2024
#
# The Virtual Caribou is a software emulation of a Caribou system. Its purpose is to allow
# for testing & debug of Spacely-Caribou software without actually running on hardware.
# VirtualCaribouClient mimics the interface of the PearyClient class which actually connects to hardware.

from PearyClient import Device

class VirtualCaribouException(Exception):
    pass


class VirtualCaribouClient:
    
    def __init__(self, host, port, verbosity = 1, logger=None):
        self.host = host
        self.port = port
        self.verbosity = verbosity
        self.vc = VirtualCaribou(logger)
        self._log = logger
    
    def load_firmware(self,regmap):
        self.vc.load_firmware(regmap)
    
    def _request(self,cmd,*args):
        
        req_payload = [cmd,]
        req_payload.extend(str(_) for _ in args)
        req_payload = ' '.join(req_payload).encode('utf-8')

        if self.verbosity > 0:
            self._log.debug(f"peary_emu sending cmd: {req_payload}")
        
        return self.vc.peary_cmd(req_payload)
        
        
    def keep_alive(self):
        """
        Send a keep-alive message to test the connection.
        """
        if self.verbosity > 0:
            self._log.debug(f"peary_emu: Sent a keep-alive message")
        
    def ensure_device(self, device_type):
        if self.verbosity > 0:
            self._log.debug(f"peary_emu: Added device of type {device_type}")
        return Device(self,0)
        
        
        
class VirtualCaribou:
    
    def __init__(self, logger):
        #Dictionary containing the value of registers.
        self.reg = {}
        self._log = logger
        
        #Dictionary containing a reference to the virtual FW block
        #which is associated with each register, so we know who to 
        #call when the reg is read/written. 
        self.reg_block = {}
        
        NUM_PWR_OUT = 6
        NUM_BIAS = 6
        NUM_VOL_IN = 8
        
        self.vout = {}
        for i in range(1,NUM_PWR_OUT+1):
            self.vout[f"PWR_OUT_{i}"] = 0
        for i in range(1,NUM_BIAS+1):
            self.vout[f"BIAS{i}"] = 0
                      
        self.vin  = {}
                      
                     
    
    def load_firmware(self, regmap):
        """Load firmware onto the VirtualCaribou Device"""

        if type(regmap) == list:
        
            for item in regmap:
                #Strings represent top-level registers
                if type(item) == str:
                    self.reg[item] = 0
                    self.reg_block[item] = None

        elif type(regmap) == dict:
            for reglist in regmap.values():
                for r in reglist:
                    if type(r) == str:
                        self.reg[r] = 0
                        self.reg_block[r] = None
        
    def peary_cmd(self, payload):
        payload_fields = payload.decode().split()
        
        if len(payload_fields) < 2:
            raise VirtualCaribouException(f"Command '{payload}' has < 2 fields.")
        
        command = payload_fields[0]
        
        device_num = payload_fields[1]

        if len(payload_fields) > 2:
            args = payload_fields[2:]
        else:
            args = []
            
        return str(self.handle_command(command, args)).encode('utf-8')
            
    def handle_command(self, command, args):
        
        if command == "device.set_voltage":
            return self.device_set_voltage(args)
        elif command == "device.get_voltage":
            return self.device_get_voltage(args)
        elif command == "device.set_memory":
            return self.device_set_memory(args)
        elif command == "device.get_memory":
            return self.device_get_memory(args)
        else:
            self._log.warning(f"VirtualCaribou: Ignoring unrecognized Command \"{command}\"")
    
    
    def device_set_memory(self,args):
        if len(args) < 2:
            raise VirtualCaribouException(f"device.set_memory has fewer than two args ('{args}')")
        
        if args[0] in self.reg.keys():
            self.reg[args[0]] = int(args[1])
        else:
            raise VirtualCaribouException(f"{args[0]} is not a valid register!")
        
    
    def device_get_memory(self,args):
        
        if args[0] in self.reg.keys():
            return self.reg[args[0]]
        else:
            raise VirtualCaribouException(f"{args[0]} is not a valid register!")
    
    def device_get_voltage(self, args):
        if args[0] in self.vout.keys():
            return self.vout[args[0]]
        elif args[0] in self.vin.keys():
            return self.vin[args[0]]
        else:
            raise VirtualCaribouException(f"device.get_voltage: Rail {args[0]} not found.")
    
    def device_set_voltage(self, args):
        if len(args) < 2:
            raise VirtualCaribouException(f"device.set_voltage has fewer than two args ('{args}')")
        else:
            try:
                self.vout[args[0]] = float(args[1])
            except (KeyError, TypeError):
                raise VirtualCaribouException(f"Exception triggered by device.set_voltage with args ('{args}')")
                   
            
        
        
        
# Virtual Firmware Blocks 
# There are two ways to compose your firmware, you can add registers directly at the top level,
# or you can add blocks which add registers (maybe with a prefix to their name).
# -- Virtual Firmware blocks are still under development.        
        
        
class Virtual_Firmware_Block:
    
    def __init__(reg_prefix, vc):
        self.reg_prefix = reg_prefix
        self.vc = vc
    
    
    
