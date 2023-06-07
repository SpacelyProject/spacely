# Spacely

### What is Spacely?
Spacely is a toolchain used to build automatic chip testsuites. It consists of the main [PySpacely](pyspacely/) 
interactive interface, an embedded [Arudino HAL](ArduinoHAL/) controller, and various [common libraries](https://github.com/Fermilab-Microelectronics/py-libs-common)
used to control external test equipment.

### What's in this repository?
This is a [monorepo](https://en.wikipedia.org/wiki/Monorepo) containing both the PySpacely and ArudinoHAL, written in 
Python3 and C++ respectively. These two parts are rather tightly coupled with a bespoke communication protocol, thus 
should be updated together.

Each of the components has its own documentation, kept alongside the code. A good place to start are [PySpacely README](PySpacely/README.md)
and [ArudinoHAL README](ArduinoHAL/README.md).

### How do I collaborate?
This project utilizes a free [Git distributed source control system](https://git-scm.com). If you have no experience
using it, make sure you start from our [Git Basics](https://github.com/Fermilab-Microelectronics/general-docs/tree/main/git#faq---git-basics)
section of the documentation.

You should `git clone` this repository to get started. **DO NOT** download a zip file or any other way directly from
`github.com` website, as this will provide you with more-or-less read-only copy of the code.

After you clone the code make sure you check the README files in PySpacely and ArudinoHAL directories. When in doubt, 
don't hesitate to reach to [any of the contributors](https://github.com/Fermilab-Microelectronics/spacely/commits/main).


