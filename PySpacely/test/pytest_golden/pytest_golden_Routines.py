import cocotb
from cocotb.triggers import RisingEdge, Timer
import cocotb_coverage
from cocotb_coverage.coverage import *
import random


#Relation defines what it means for a value to fall inside a bin (low,high)
range_relation = lambda val_, bin_ : bin_[0] <= val_ <= bin_[1]

#Define a set of CoverPoints that cover combinations of high and low values in the adder.
Adder_Coverage = coverage_section (
    CoverPoint("dut.A",
               vname="A",
               rel = range_relation,
               bins = [(0,3),(4,7),(8,11),(12,15)]),
    CoverPoint("dut.B",
               vname="B",
               rel = range_relation,
               bins = [(0,3),(4,7),(8,11),(12,15)]),
    CoverCross("dut.A_vs_B",
        items=["dut.A","dut.B"]))


#Calling this function samples coverage and also checks correctness of outputs.
@Adder_Coverage
def sample_coverage(A,B,Z):
    assert A+B == Z

    
async def ROUTINE_test_cadder_mode0(dut):
    """Test cadder block at block-level (twin mode 0)"""

    cocotb.fork(Clock(dut.clk, 1000).start())

    await RisingEdge(dut.clk)
    await Timer(1, units="ns")

    for _ in range(100):
        A_val = random.randint(0,15)
        B_val = random.randint(0,15)

        dut.A.value = A_val
        dut.B.value = B_val

        await RisingEdge(dut.clk)
        await Timer(1, units="ns")
        sample_coverage(A_val,B_val, dut.Z.value.integer)

    cover_percentage = coverage_db["dut"].cover_percentage
    sg.log.info(f"Coverage Percentage acheived in this test: {cover_percentage} %")

    #With 16 cover bins and 100 samples, there's roughly a 1 in a million chance of
    #this assertion failing by random chance.
    assert cover_percentage > 0.9



def ROUTINE_test_cadder_mode1_2():
    """Test cadder block include a digital twin of test firmware (twin mode 1 or 2)"""

    sg.INSTR["car"].debug_memory = True
    
    # We expect the output to be offset by 2 cycles from the input: one cycle for the AWG to
    # assert the input value, and one cycle for the cadder to clock that value. 
    LOOPBACK_OFFSET_CYC = 2
    
    sg.INSTR["car"].set_memory("divider_cycles",5)
    sg.INSTR["car"].set_memory("divider_rstn",0)
    sg.INSTR["car"].set_memory("divider_rstn",1)

    sg.INSTR["car"].set_memory("clear",1)

    #Try all possible combinations of the 4-bit (A) + 4-bit (B) inputs.
    input_vector = [n for n in range(256)]
    
    for vec in input_vector:
        sg.INSTR["car"].set_memory("write_channel", vec)

    sg.INSTR["car"].set_memory("n_samples",256 + LOOPBACK_OFFSET_CYC)

    sg.INSTR["car"].set_memory("run",1)

    while True:
        status = sg.INSTR["car"].get_memory("status")
        if status == 0:
            break
        else:
            sg.log.debug("<test> Waiting for APG idle")
            sg.INSTR["car"].dly_min_axi_clk(50)


    result_vector = []
    sg.log.debug("<test> Starting to read back results.")
    for n in range(256 + LOOPBACK_OFFSET_CYC):
        result_vector.append(sg.INSTR["car"].get_memory("read_channel"))

    sg.log.debug("<test> Finished reading back results.")
    for i in range(256):
        input_A = input_vector[i] & 0xf
        input_B = input_vector[i] >> 4
        output  = result_vector[i+LOOPBACK_OFFSET_CYC]

        print(f"{input_A:2} + {input_B:2} = {output:2}   ",end='')

        assert input_A + input_B == output
        
        if i%8 == 0:
            print("") #Newline after every 8 
        
