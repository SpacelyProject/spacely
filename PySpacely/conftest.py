import os
import shutil

MASTER_CONFIG_TXT = "Master_Config.txt"
MASTER_CONFIG_BAK_TXT = "Master_Config.bak.txt"
MASTER_CONFIG_PYTEST = os.path.join("test","Master_Config.pytest.txt")

PYTEST_ASIC_SRC = os.path.join("test","pytest_golden")
PYTEST_ASIC_DEST = os.path.join("spacely-asic-config","pytest_golden")


def pytest_configure(config):
    print("**PYTEST CONFIGURE: Setting up Master_Config and pytest_golden ASIC**")
    shutil.move(MASTER_CONFIG_TXT,MASTER_CONFIG_BAK_TXT)
    shutil.copy(MASTER_CONFIG_PYTEST, MASTER_CONFIG_TXT)
    shutil.copytree(PYTEST_ASIC_SRC,PYTEST_ASIC_DEST, dirs_exist_ok=True)


def pytest_unconfigure(config):
    print("**PYTEST UNCONFIGURE: Restoring Master_Config**")
    shutil.move(MASTER_CONFIG_BAK_TXT,MASTER_CONFIG_TXT)
