import pytest
import shutil
import filecmp
import os

from Spacely_Globals import *
from Spacely_Cocotb import *

import fnal_log_wizard as liblog


class TestInitializationError(RuntimeError):
    pass

XRUN_ERROR = TestInitializationError("""** USER CUSTOMIZATION NEEDED ** 
In order to run Spacely-Cocotb tests, you need to have the Xcelium executable 'xrun' installed an on your path.
To check whether you have the executable, type "which xrun"
To add the executable to your path, type "PATH=$PATH:/path/to/xrun/directory""")
                                        
UNISIM_ERROR = TestInitializationError("""** USER CUSTOMIZATION NEEDED **
In order to run Spacely-Cocotb test with TWIN_MODE=2, you need to provide Spacely with paths to the Xilinx Unisim HDL repo
by defining a macro in the file spacely/PySpacely/spacely-asic-config/pytest_golden/hdl/hdl_sources_unisim.txt
Please open this file and update those macros to the appropriate path.
""")

COMMON_BLOCKS_ERROR = TestInitializationError("""** USER CUSTOMIZATION NEEDED **
In order to run Spacely-Cocotb test with TWIN_MODE=1, you need to provide Spacely with paths to the spacely-caribou-common-blocks HDL repo
by defining a macro in the file spacely/PySpacely/spacely-asic-config/pytest_golden/hdl/hdl_sources_common_blocks.txt
Please open this file and update those macros to the appropriate path.
""")

PYTEST_ASIC_SRC = os.path.join("test","pytest_golden")
PYTEST_ASIC_DEST = os.path.join("spacely-asic-config")

def sync_folders_and_check_differences(source: str, destination: str):
    """Copies source to a new folder under destination. If the destination folder already exists,
       it recursively walks that folder, creating files that don't already exist and returning which 
       ones exist but are different."""
    dest_folder = os.path.join(destination, os.path.basename(source))
    differing_files = []
    
    # If destination folder does not exist, copy the entire source folder
    if not os.path.exists(dest_folder):
        shutil.copytree(source, dest_folder)
        print(f"Copied {source} to {dest_folder}")
        return differing_files  # No files to compare yet
    
    # Recursively walk through all subdirectories of source
    for root, dirs, files in os.walk(source):
        relative_root = os.path.relpath(root, source)
        dest_root = os.path.join(dest_folder, relative_root)
        
        if not os.path.exists(dest_root):
            os.makedirs(dest_root)  # Ensure subdirectories exist
        
        for myfile in files:
            if myfile.endswith("~"):
                continue #Skip temporary files.
            
            source_file = os.path.join(root, myfile)
            dest_file = os.path.join(dest_root, myfile)
            
            if not os.path.exists(dest_file):
                shutil.copy2(source_file, dest_file)
                print(f"Created missing file: {dest_file}")
            else:
                # Compare file contents
                if not filecmp.cmp(source_file, dest_file, shallow=False):
                    differing_files.append(dest_file)
    
    return differing_files


@pytest.fixture
def setup_pytest_golden(sg_log):
    differing_files = sync_folders_and_check_differences(PYTEST_ASIC_SRC, PYTEST_ASIC_DEST)

    differing_files = [x for x in differing_files if ("hdl_sources_unisim" not in x and "hdl_sources_common_blocks" not in x)]
    
    if len(differing_files) > 0:
        sg.log.warning(f"The following files have been MODIFIED from their golden reference versions. The pytest suite may not return the correct results: {differing_files}")
    
@pytest.fixture
def sg_log():
    sg.log = liblog.PlainLogger(liblog.HandleOutputStrategy())

@pytest.fixture
def xrun():
    if not shutil.which("xrun"):
        raise XRUN_ERROR


@pytest.fixture
def cocotb_basics(xrun, sg_log, setup_pytest_golden):
    return


@pytest.fixture
def check_unisim_macro(setup_pytest_golden):
    with open(os.path.join("spacely-asic-config","pytest_golden","hdl","hdl_sources_unisim.txt")) as read_file:
        read_file_txt = read_file.read()

    if "DEF UNISIM ???" in read_file_txt:
        raise UNISIM_ERROR

@pytest.fixture
def check_common_blocks_macro(setup_pytest_golden):
    with open(os.path.join("spacely-asic-config","pytest_golden","hdl","hdl_sources_common_blocks.txt")) as read_file:
        read_file_txt = read_file.read()

    if  "DEF COMMON_BLOCKS ???" in read_file_txt:
        raise COMMON_BLOCKS_ERROR
    
@pytest.fixture
def twin_mode_0(cocotb_basics):
    sg.USE_COCOTB=True
    sg.SIMULATOR="xcelium"
    sg.HDL_TOP_MODULE="cadder"
    sg.HDL_SOURCES="hdl_sources_mode_0.txt"
    sg.COCOTB_BUILD_ARGS=[]
    sg.TWIN_MODE = 0
    calculate_global_filenames()
    

@pytest.fixture
def twin_mode_1(cocotb_basics, check_common_blocks_macro):
    sg.USE_COCOTB=True
    sg.SIMULATOR="xcelium"
    sg.HDL_TOP_MODULE="cadder_twin_mode1"
    sg.HDL_SOURCES="hdl_sources_mode_1.txt"
    sg.COCOTB_BUILD_ARGS=[]
    sg.TWIN_MODE = 1
    calculate_global_filenames()

@pytest.fixture
def twin_mode_2(cocotb_basics, check_unisim_macro):
    sg.USE_COCOTB=True
    sg.SIMULATOR="xcelium"
    sg.HDL_TOP_MODULE="cadder_twin_mode2"
    sg.HDL_SOURCES="hdl_sources_mode_2.txt"
    sg.FW_TOP_MODULE="pytest_golden_fw_bd"
    sg.COCOTB_BUILD_ARGS=["-top glbl"]
    sg.TWIN_MODE=2
    calculate_global_filenames()

    
def test_cadder_mode0(twin_mode_0):
    run_routine_cocotb("ROUTINE_test_cadder_mode0")

def test_cadder_mode1(twin_mode_1):
    run_routine_cocotb("ROUTINE_test_cadder_mode1_2")

def test_cadder_mode2(twin_mode_2):
    run_routine_cocotb("ROUTINE_test_cadder_mode1_2")
