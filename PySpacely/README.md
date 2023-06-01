# PySpacely

### What is PySpacely?
PySpacely is an interactive control panel for the [Spacely toolchain](https://github.com/Fermilab-Microelectronics/spacely). 
It is meant to be run on a computer and control the chip testing.


### Hardware Requirements
Since the software is intended to control physical processes, it is intended to run on a [NI PXIe](https://www.ni.com/en-us/shop/pxi.html)
system. While some parts of the program will work without a problem on any system, the real testing must be 
performed using the NI system. The software will interact directly with the modules via the [official NI drivers](https://github.com/ni/nimi-python).

The software, as of now, utilizes the following equipment:
 - Arduino Portenta H7, running [ArudinoHAL](../ArduinoHAL)
 - 2x NI PXI-4110 DC power supplies
 - 2x NI-PXIe-4141 4-CH Precision SMUs
 - Agilent 33250A Arbitrary Waveform Generator
 - Prologix GPIB-ETHERNET Controller


### Software Requirements
Dictated by the hardware requirements, PySpacely should be run under native 64-bit Windows environment (***not*** via [WSL](https://learn.microsoft.com/en-us/windows/wsl/about)).
The code requires:
 - **Python 3.11**
   - It *must* be installed from [the official packages](https://www.python.org/downloads/windows/).
   - You *cannot* use Microsoft Store Python, as suggested by Windows. It is due to [major issues related to addressing hardware](https://github.com/ni/nimi-python/issues/1904), 
     present in the customized edition from MS Store. 
   - Newer versions are a hit-or-miss and usually depend on official NI drivers [support matrix](https://app.travis-ci.com/github/ni/nimi-python).
 - **ANSI-complaint terminal**
   - The code utilizes [ANSI escape sequences](https://en.wikipedia.org/wiki/ANSI_escape_code). Thus, a terminal that 
     supports them is required.
   - Official [Microsoft Windows Terminal](https://apps.microsoft.com/store/detail/windows-terminal/9N0DX20HK701) is a
     very good modern choice.
   - Neither Windows Command Prompt (aka. `cmd`) nor Python IDLE Shell are ANSI-complaint.


### How do I run it?
1. [Clone the repository](https://docs.github.com/en/repositories/creating-and-managing-repositories/cloning-a-repository?platform=windows&tool=cli#cloning-a-repository)
2. Open the terminal
3. Spacely utilizes [Python virtual environments](https://docs.python.org/3/library/venv.html). Thus, you need to activate
   it using `.\venv\Scripts\activate`
4. When updating, ensure your dependencies are up-to-date:`python -m pip install -r requirements.txt`
5. Run `python .\Spacely.py --help` to get started

The repository contains a PowerShell `.\Spacely.ps1` script that will activate venv on demand.

### How do I collaborate?
First look at the [basics of Git](../README.md#how-do-i-collaborate). Beyond that, it's encouraged to work on features
using separate branches, according to the [standard gitflow rules](https://www.atlassian.com/git/tutorials/comparing-workflows/gitflow-workflow).

### Documentation
See [`docs` folder](docs). The code itself contains a built-in help. You can either use `?` in the interactive shell, or
run the code with `--help` option to see it.