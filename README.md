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
working with Git, make sure to check [official Git SCM videos](https://git-scm.com/videos) and/or excellent [tutorial on Git basics](https://www.freecodecamp.org/news/learn-the-basics-of-git-in-under-10-minutes-da548267cc91/).

When in doubt, don't hesitate to reach to [any of the contributors](https://github.com/Fermilab-Microelectronics/spacely/commits/main).


