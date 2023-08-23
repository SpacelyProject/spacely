# Spacely Globals #
#
# Dynamic global variables and data structures that can be accessed from
# any part of Spacely. 


#Arduino port. Making this a global variable allows for
#commands that would affect the NI System or analog to send
#emulation commands to the Arduino instead.
port = None
AWG = None

ARDUINO_CONNECTED = False
NI_CONNECTED = False
AWG_CONNECTED = False
log = None
