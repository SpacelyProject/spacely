//
//    cadder.v
//    Adam Quinn -- 2/4/2025
//
// This is a clocked 4-bit adder. It serves as a demo block for Spacely-Caribou
// tests with Cocotb. The CARRY_ERROR parameter can be used to force a logical
// error in which the carry bit is always set to zero.

module cadder #(CARRY_ERROR=0) (
				input logic [3:0]  A,
				input logic [3:0]  B,
				input logic 	   clk,
				output logic [4:0] Z);

   logic [3:0] 					   Z_4b;

   assign Z_4b = A + B;
   

   always @(posedge clk) begin
      if(CARRY_ERROR)
	Z <= Z_4b;
      else
	Z <= A + B;
   end
   

endmodule // cadder
