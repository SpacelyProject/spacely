
USE_ARDUINO = False
USE_NI = True
USE_AWG = True
USE_SCOPE = False


DEFAULT_OSCILLOSCOPE_RESOURCE = "USB0::0x0699::0x0503::B050103::INSTR"

DEFAULT_FPGA_BITFILE_MAP = {"PXI1Slot4":"NI7972_NI6583_40MHz"}
DEFAULT_IOSPEC = ".\\asic_config\\SPROCKET2\\sprocket2_iospec.txt"

# AWG (Arbitrary Waverform Generator)
# 
# The AWG is controlled using an IP<>GPIB proxy (Prologix). It has an
# IP address (DEFAULT_PROLOGIX_IPADDR). The AWG has an address on the 
# GPIB bus itself (DEFAULT_AWG_GPIBADDR).
# When using Agilent gear, upon restarting, you should see an alert 
# saying "GPIB Interface Selected (Address 10)" - this is the GPIB
# address 
DEFAULT_PROLOGIX_IPADDR = "192.168.1.15"
DEFAULT_AWG_GPIBADDR = 10

#Emulation
EMULATE_ASIC = False

#CDAC Trimming
DEFAULT_CDAC_TRIMSTRING = "100000"

#Voltage Channels
#SMU A and B designations are from Scott's PCB.
SMU_A = "PXI1Slot2"
SMU_B = "PXI1Slot3"
PSU_A = "PXI1Slot7" # PXI-4110 or 4111; CH0=0-6VDC, CH1=0-20V, CH2=-20V-0V
PSU_B = "PXI1Slot8" # PXI-4110 or 4111; CH0=0-6VDC, CH1=0-20V, CH2=-20V-0V

INSTR_INIT_SEQUENCE = [SMU_A, SMU_B, PSU_A, PSU_B]
INSTR = {SMU_A:None,
         SMU_B:None,
         PSU_A:None,
         PSU_B:None}



#TO-DO:
# - Vref is supplied from an AWG, not an SMU.
# - Double-check whether currents should be positive or negative.


# Power distribtion
# //Note: names here are 1:1 as on the board (including upper/lowercase)
#   PSU-A => slot 7 as in cfg above; supplied level translators (VDDIO_LT@ch0, VCC_LT@ch1); P1 on flange
#   PSU-B => slot 8 as in cfg above; supplies ASIC (VDD_ASIC@ch0, VCC_ASIC@ch1); P2 on flange
#   SMU-A => slot 13 as in cfg above; provides vdda, vref, vdd12, ib2; J6 on flange
#   SMU-B => slot 14 as in cfg above; provides iterm_ts, ife, icharge, icomp; J7 on flange



#UPDATES FROM SPROCKET1:
# Vref_adc is taking the place of Vref (J3-10 to J6-5/J6-17), which corresponds to SMU_A, chan 1
# Vref_fe and Ibdig are supplied using an external power supply (so not on this list)
V_SEQUENCE = [ "VCC_LT", "VDDIO_LT", "Vref_adc", "Vdd12", "VDD_ASIC",        "Ib2", "vdda", "VCC_ASIC"]
V_INSTR= {"vdda":   SMU_A,
          "Vref_adc":   SMU_A,
          "Vdd12":  SMU_A,
          "Ib2":     SMU_A,
          "VDDIO_LT": PSU_A,          
          "VCC_LT":   PSU_A,
          "VCC_ASIC": PSU_B,            
          "VDD_ASIC": PSU_B}
V_CHAN = {# SMU_A
            "vdda": 0,            
            "Vref_adc":  1,
            "Vdd12": 2,
            "Ib2": 3,
          # SMU_B => not used here; configured as current channels
          # PSU_A
            "VDDIO_LT": 0,
            "VCC_LT":   1,
          # PSU_B
            "VDD_ASIC": 0,
            "VCC_ASIC": 1
         }

V_LEVEL = {# SMU_A
             "vdda": 2.5,
             "Vref_adc":  1.0,
             "Vdd12": 1.2,
             "Ib2": 1.35,
             # PSU_A
             "VDDIO_LT": 1.2,                  
             "VCC_LT":   3.3,
             # PSU_B
             "VDD_ASIC": 1.35, #Boosted from 1.2V to account for PCB drop.
             "VCC_ASIC": 3.3             
           }
           

# Rough current guidelines
# TODO: TEST IF THESE VALUES IN DOCS BELOW ARE CORRECT OR WE'RE OFF IN UNITS IN THE DICT BELOW
#  - 100mA for vdda 
#  - 1mA for all other ASIC power rails
#  - 100mA for level translators (LT) power rails
#  - 10uA for others     
V_CURR_LIMIT = {# SMU_A
                  "vdda": 0.1,
                  "Vref_adc":  0.00001,
                  "Vdd12": 0.00001,
                  "Ib2": 0.00001,
                # PSU_A
                  "VDDIO_LT": 0.1,                  
                  "VCC_LT":   0.3, #Changed from 0.1
                # PSU_B
                  "VCC_ASIC": 0.02, #Edit 11/15: Double currents to 20mA and 200mA for cryo.
                  "VDD_ASIC": 0.20 # this is correct: fixes latchup by giving the ASIC 100mA
                  }

#Global dict to hold the port objects created for each of these.
V_PORT = {"vdda": None, # SMU_A
          "Vref_adc":  None, # SMU_A
          "Vdd12": None, # SMU_A
          "Ib2": None,
          "VDDIO_LT": None, # PSU_A                  
          "VCC_LT":   None, # PSU_A
          "VCC_ASIC": None, # PSU_B
          "VDD_ASIC": None  # PSU_B      
         }


#Current Channels
I_SEQUENCE = ["Icomp", "Ib1", "Ibuf", "Iterm"]
I_INSTR = {
          "Iterm":   SMU_B,
          "Ib1":     SMU_B,
          "Ibuf": SMU_B,
          "Icomp":   SMU_B
          }
I_CHAN  = {
          "Iterm":   0,
          "Ib1":     1,
          "Ibuf": 2,
          "Icomp":   3
          }

I_LEVEL  = {
            "Iterm":     80e-6,
            "Ib1":      -50e-6,
            "Ibuf":  -60e-6,
            "Icomp":    -20e-6
           }
            
I_PORT  = {
           "Iterm":   None,
           "Ib1":     None,
           "Ibuf": None,
           "Icomp":   None
          }

I_VOLT_LIMIT = 2.5

