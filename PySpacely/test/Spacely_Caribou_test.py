import pytest
import sys
import os
import random 

sys.path.append(os.path.abspath("."))
sys.path.append(os.path.abspath("./src"))
from Spacely_Caribou import *
from VirtualCaribou import *

import fnal_log_wizard as liblog

TEST_FIRMWARE = ["reg1", "reg2", "reg3"]

@pytest.fixture
def dbg_log():
    return liblog.PlainLogger(liblog.HandleOutputStrategy())

@pytest.fixture
def car(dbg_log):
    return Caribou("EMULATE",12345,"SpacelyCaribouBasic", dbg_log)



def test_car_init(car):
    assert car.client_connected == True


def test_set_voltage(car):
    test_voltage = random.random()
    car.set_voltage("PWR_OUT_1",test_voltage)
    voltage_read = car.get_voltage("PWR_OUT_1")
    voltage_actual = car._client.vc.vout["PWR_OUT_1"]
    assert voltage_read == test_voltage
    assert voltage_actual == test_voltage
    
def test_get_voltage(car):
    test_voltage = random.random()
    car._client.vc.vin["VOL_IN_1"] = test_voltage
    voltage_read = car.get_voltage("VOL_IN_1")
    assert voltage_read == test_voltage
    
def test_firmware_readback(car):
    test_val = random.randint(1,100)
    car.set_axi_registers(TEST_FIRMWARE)
    car.set_memory("reg1", test_val)
    readback_val = car.get_memory("reg1")
    assert readback_val == test_val
    
