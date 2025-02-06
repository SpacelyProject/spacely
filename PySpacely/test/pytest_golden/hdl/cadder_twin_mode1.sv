
module cadder_twin_mode1();


   logic dut_clk;
   logic [3:0] A, B;
   logic [4:0] Z;
   
   
   
   
   //cadder (Device Under Test)
   cadder  #(.CARRY_ERROR(0)
	     ) uDUT (.clk(dut_clk),
		     .A(A),
		     .B(B),
		     .Z(Z));
   

   //Test Firmware
   logic_clk_div_top logic_clk_div_top_0 (/*AXI_INTERFACE(0x400000000)*/
				  .master_clk(AXI_ACLK),
				  .output_clk(dut_clk),
				  .axi_resetn(AXI_ARESETN),
				  .axi_clk(AXI_ACLK));

   
   Arbitrary_Pattern_Generator_top #(.NUM_SIG(8), 
				     .NUM_SAMP(300)
				     ) test_apg(/*AXI_INTERFACE(0x400001000)*/
						.axi_clk(AXI_ACLK),
						.axi_resetn(AXI_ARESETN),
						.wave_clk(dut_clk),
						.input_signals({3'b0,Z}),
						.output_signals({A,B}));
   
						



endmodule // cadder_fw_mode1
