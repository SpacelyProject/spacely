#ExampleASIC Routines File
#
# This file contains any custom code that you want to write for your ASIC,
# for example routines to read or write to registers, or to run tests.




def ROUTINE_Write_to_Scan_Chain():
    """This routine lets the user write a fixed pattern to the chip scan chain."""
    
    # Get the bitstream that the user wants to enter into the scan chain.  
    user_text = input("?")
    
    user_bitstream = []
    
    for c in user_text:
        if c == "0":
            user_bitstream.append(0)
        elif c == "1":
            user_bitstream.append(1)
        else:
            sg.log.error(f"'{c}' is not a 0 or a 1. Honestly, what are you even doing?")
            return
            
    #Generate a Glue pattern that will write this SC data to the chip.
    sc_pattern = genpatter_scan_chain_write(user_bitstream)
    
    #Run that pattern.
    sg.pr.run_pattern(sc_pattern)



def ROUTINE_Run_Glue_Wave():
    """Run a Glue Wave on the FPGA (defined in src code) and save the result to file."""

    glue_wave = "xyz.glue"
    
    sg.pr.run_pattern(glue_wave,outfile_tag="result")


#EWISOTT
def genpattern_scan_chain_write(sc_data, time_scale_factor):

    waves = {}
        
    waves["S_CLK"] = []
    waves["S_DIN"] = []

    for i in sc_data:
        waves["S_DIN"] = waves["S_DIN"] + [i]*2
        waves["S_CLK"] = waves["S_CLK"] + [0,1]
        
    #Use the Spacely built-in routine genpattern_from_waves_dict()
    #to turn your dictionary into a Glue wave
    return genpattern_from_waves_dict(waves)