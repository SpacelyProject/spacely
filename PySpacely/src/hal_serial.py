# @todo this needs to be a class

import serial
import time
from si_prefix import si_format

### FUNCTIONS ###

class ArudinoHal():
    def __init__(self, log, serial_port: str, baud: int):
        self.log = log
        self.serial_port = serial_port
        self.baud = baud
    
    def connect() -> bool:
        self.log.debug(f"Connecting to Arudino HAL at {self.serial_port}@{self.baud}")
           
#    def _setup_serial() -> bool:
        

def open_port(serial_port, baud):

    try:
        #Port is automatically opened when calling serial.Serial(),
        #so ~~port.open() is unnecessary.~~
        #GZ 2023/05/23: actually it is needed sometimes as buffer sizes changes will NOT apply (race condition?)
        #               see https://github.com/pyserial/pyserial/blob/0e7634747568547b8a7f9fd0c48ed74f16af4b23/serial/serialwin32.py#L418
        port = serial.Serial(serial_port, baud, timeout=1)
        time.sleep(0.1)
        if not port.is_open:
            port.open()
        port.set_buffer_size(rx_size = 16 * 1024 * 1024, tx_size = 2 * 1024 * 1024)
        return port
        
    except serial.serialutil.SerialException as e:
        if "PermissionError" in str(e):
            print("Permission error trying to access that port!")
            print("If Arduino IDE is open, please close it :)")
        else:
            print("Unknown Exception:")
            print(e)

        return -1


def command_ng(log, port, cmd_txt, data_timeout=0.2) -> str:
    log.debug(f"TX HAL command: {cmd_txt}")
    if not port.is_open:
        raise IOError("Port is closed")
    
    if "*" in cmd_txt:
       raise Exception("Streaming mode not supported (yet)")
    
    while port.out_waiting > 0: # on Windows, the OS may double-buffer data; we need to wait for it!
        pass
    
    port.timeout = data_timeout
    port.write(cmd_txt.encode('ascii'))
    
    # Sadly Windows doesn't support non-blocking/async IO for serial ports so we need to use 
    # the next best thing: busywait with break buffering
    # See: https://pyserial.readthedocs.io/en/latest/pyserial_api.html#serial.Serial.nonblocking
    lines = []
    rcv_len = 0 # total bytes received
    taper_len = 0 # bytes received since last tappered RX log
    try:
        while True:
            # this will busy-wait for at most data_timeout; it will do triple-buffering for us
            # this is to avoid buffer overflow when you go too fast on HAL
            line = port.readline().decode('ascii')
            line_len = len(line)
            rcv_len += line_len
            
            # inteligently taper-off logging
            if rcv_len < 100:
                log.debug(f"HAL RX line: >>{repr(line)[1:-1]}<< (line_len={line_len}B rcv_len={rcv_len}B)")
            else:
                taper_len += line_len
                taper = 1000 if rcv_len < 10000 else 10000 # when we're <10kB we print every 1kB; otherwise every 10kB
                if taper_len >= taper:
                    taper_len = 0
                    log.debug(f"HAL RX ~{si_format(rcv_len, 2)}B so far (taper={taper}, in_waiting={port.in_waiting}B)")
            
            lines.append(line)
            if line == '':
                log.debug(f"Serial has no more lines (got {rcv_len} bytes total)")
                break            
            
    except serial.SerialTimeoutException:
        log.warning(f"Serial read timeout - no more data (got {rcv_len} bytes)")
        pass
    
    # remove HAL protocol markers while joinng the list in *new memory* space
    return ''.join(lines).strip('\r\n?')

def command(port, cmd_txt, printresponse=True, timeout_s=0.2):

    print(f"Sending cmd: {cmd_txt}")
    # "*" denotes a streaming command.
    if "*" in cmd_txt:
        stream_data = 1
    else:
        stream_data = 0

    response_str=""
    last_newline = 0

    port.write(bytes(cmd_txt+"\n",'utf-8'))
    write_time = time.perf_counter()
    
    receiving_comment = False
    comment_contents = ''

    #Every time we get a command, we will give it 200 ms to come up
    #with additional output before bailing.
    while stream_data or (time.perf_counter()-write_time < timeout_s): 
        try:
            #If there's nothing new for us after 100 ms, we break.
            #if not (port.in_waiting or stream_data) \
            #   and :
            #    break
            #If there is, we read it and then wait for more.
            if response_str[-2:]=='\n?':
                break
            while port.in_waiting or stream_data:
                print(f"READING SERIAL... piw={port.in_waiting} sd={stream_data}")
                new_char = str(port.read(),'UTF-8')
                print(f"GOT CHAR >>{new_char}<< incmt:{receiving_comment} buf_size:{len(response_str)}")
                
                if receiving_comment:
                    if new_char == "\n":
                        print("HAL NO LONGER IN COMMENT MODE")
                        print(f"GOT HAL COMMENT >>{comment_contents}<<")
                        comment_contents = ''
                        receiving_comment = False
                    else:
                        comment_contents = f"{comment_contents}{new_char}"
                    continue
                    
                if (response_str == '?' or response_str[-2:] == '\n?') and new_char == '#':
                    print("HAL IN COMMENT MODE")
                    receiving_comment = True
                    continue
                    
                
                response_str = response_str + new_char
                
                has_new_line = ("\n" in new_char or "?" in new_char)

                #Batch printing by newlines.
                if printresponse and has_new_line:   
                    print(response_str[last_newline:],end='')
                    last_newline = len(response_str)
                    

        except KeyboardInterrupt:
            print("Ctrl-C detected! Sending a return to pause streaming data.")
            port.write(bytes("\n",'utf-8'))
            break
    
#    print(f"Got response >>{response_str}<<")
    return response_str

def handshake_with_arduino_ng(log, port) -> bool:
    handshake_in = "PING"
    handshake_out = "PONG"
    while True:
        cret = command_ng(log, port, handshake_in)
        if cret == handshake_out:
            log.info("HAL handshake completed")
            return True
        
        if cret == '':
            log.error(f"HAL handshake \"{handshake_in}\" did not return anything (expected {cret(handshake_out)})")
        else:
            # if the OS had some previous buffer and we crashed mid-read this can potentially read
            # that stale data, so we should just dump the OS buffer
            port.reset_input_buffer()
            log.error(f"HAL \"{handshake_in}\" handshake returned wrong data: >>{repr(cret)}<< (expected {repr(handshake_out)})")
        
        input("Handshake failed. Press enter to retry.")
        
        
# deprecated
def handshake_with_arduino(port):
    while True:
        #Arduino should always echo back what we write to it. "ACK" is just an arbitrary string.
        port.write(b'ACK\n')

        handshake_time = time.time()

        #Allow up to 5 seconds for the Arduino to respond.
        while not port.in_waiting and time.time()-handshake_time < 5:
            time.sleep(0.1)

        #If we get a message back from the arduino that might be a docstring,
        #try to parse it. If the message is bad, try again.
        if port.in_waiting > 1:
            docstring = str(port.readline(),'UTF-8')
            print(docstring)
            if "ACK" in docstring:
                print("Handshake successful! You can now enter commands.")
                break
        #Otherwise...
        else:
            #If we got a shorter message, try again.
            if port.in_waiting > 0:
                while port.in_waiting:
                    port.read()
            #If we got nothing at all after 5 seconds, handshake failed.
            else:
                input("Handshake failed. Press enter to retry.")


    
