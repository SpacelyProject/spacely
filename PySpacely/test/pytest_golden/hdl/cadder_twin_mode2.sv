`timescale 1ns/1ps
module cadder_twin_mode2();

   logic [3:0] A, B;
   logic [4:0] Z, Z_b;
   logic       dut_clk;
   

   //cadder (Device Under Test)
   cadder  #(.CARRY_ERROR(0)
	     ) uDUT (.clk(dut_clk),
		     .A(A),
		     .B(B),
		     .Z(Z));

   assign Z_b = ~Z;

   //Test Firmware
   pytest_golden_fw_bd uFW (/*AXI_PASSTHROUGH(2)*/
			    .A_0_clk_n(),.A_0_clk_p(A[0]),
			    .A_1_clk_n(),.A_1_clk_p(A[1]),
			    .A_2_clk_n(),.A_2_clk_p(A[2]),
			    .A_3_clk_n(),.A_3_clk_p(A[3]),
			    .B_0_clk_n(),.B_0_clk_p(B[0]),
		            .B_1_clk_n(),.B_1_clk_p(B[1]),
			    .B_2_clk_n(),.B_2_clk_p(B[2]),
			    .B_3_clk_n(),.B_3_clk_p(B[3]),
			    .Z_0_clk_n(Z_b[0]),.Z_0_clk_p(Z[0]),
			    .Z_1_clk_n(Z_b[1]),.Z_1_clk_p(Z[1]),
			    .Z_2_clk_n(Z_b[2]),.Z_2_clk_p(Z[2]),
			    .Z_3_clk_n(Z_b[3]),.Z_3_clk_p(Z[3]),
			    .Z_4_clk_n(Z_b[4]),.Z_4_clk_p(Z[4]),
			    .dut_clk_clk_n(),.dut_clk_clk_p(dut_clk));
   

endmodule // cadder_twin_mode2
