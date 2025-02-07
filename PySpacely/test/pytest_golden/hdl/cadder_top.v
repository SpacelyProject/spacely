//
//    cadder_top.v
//    Adam Quinn -- 2/6/2025
//
// A verilog wrapper for the cadder block to enable instantiation in Vivado.

module cadder_top #(CARRY_ERROR=0) (
				input wire [3:0]  A,
				input wire [3:0]  B,
				input wire 	   clk,
				output wire [4:0] Z);


   cadder #(.CARRY_ERROR(CARRY_ERROR)) cadder_int (.A(A),
						   .B(B),
						   .clk(clk),
						   .Z(Z));
   
   
   

endmodule // cadder
