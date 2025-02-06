import pytest
import shutil
import os

from Spacely_Globals import *
from Spacely_Cocotb import *

import fnal_log_wizard as liblog

@pytest.fixture
def sg_log():
    sg.log = liblog.PlainLogger(liblog.HandleOutputStrategy())

@pytest.fixture
def xrun():
    if not shutil.which("xrun"):
        raise RuntimeError("In order to run Spacely-Cocotb tests, you need to have the Xcelium executable 'xrun' installed and on your path.")


@pytest.fixture
def twin_mode_0():
    sg.USE_COCOTB=True
    sg.SIMULATOR="xcelium"
    sg.HDL_TOP_MODULE="cadder"
    sg.COCOTB_BUILD_ARGS=[]
    sg.TWIN_MODE = 0
    calculate_global_filenames()
    

@pytest.fixture
def twin_mode_1():
    sg.USE_COCOTB=True
    sg.SIMULATOR="xcelium"
    sg.HDL_TOP_MODULE="cadder_twin_mode1"
    sg.COCOTB_BUILD_ARGS=[]
    sg.TWIN_MODE = 1
    calculate_global_filenames()

    
def test_cadder_mode0(xrun, sg_log, twin_mode_0):
    run_routine_cocotb("ROUTINE_test_cadder_mode0")


def test_cadder_mode1(xrun, sg_log, twin_mode_1):
    run_routine_cocotb("ROUTINE_test_cadder_mode1")
