import os
import shutil

MASTER_CONFIG_TXT = "Master_Config.txt"
MASTER_CONFIG_BAK_TXT = "Master_Config.bak.txt"
MASTER_CONFIG_PYTEST = os.path.join("test","Master_Config.pytest.txt")




def pytest_configure(config):
    print("**PYTEST CONFIGURE: Setting up Master_Config **")
    shutil.move(MASTER_CONFIG_TXT,MASTER_CONFIG_BAK_TXT)
    shutil.copy(MASTER_CONFIG_PYTEST, MASTER_CONFIG_TXT)


def pytest_unconfigure(config):
    print("**PYTEST UNCONFIGURE: Restoring Master_Config**")
    shutil.move(MASTER_CONFIG_BAK_TXT,MASTER_CONFIG_TXT)
