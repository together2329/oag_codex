IVERILOG ?= iverilog
VVP ?= vvp
RTL := rtl/mctp_rx_context_tracker.sv
BUILD := build

.PHONY: test test_basic test_timeout test_precedence test_parameters clean

test: test_basic test_timeout test_precedence test_parameters

test_basic:
	mkdir -p $(BUILD)
	$(IVERILOG) -g2012 -s tb_basic -o $(BUILD)/tb_basic $(RTL) tb/tb_basic.sv
	$(VVP) $(BUILD)/tb_basic

test_timeout:
	mkdir -p $(BUILD)
	$(IVERILOG) -g2012 -s tb_timeout -o $(BUILD)/tb_timeout $(RTL) tb/tb_timeout.sv
	$(VVP) $(BUILD)/tb_timeout

test_precedence:
	mkdir -p $(BUILD)
	$(IVERILOG) -g2012 -s tb_precedence -o $(BUILD)/tb_precedence $(RTL) tb/tb_precedence.sv
	$(VVP) $(BUILD)/tb_precedence

test_parameters:
	mkdir -p $(BUILD)
	$(IVERILOG) -g2012 -s tb_parameters -o $(BUILD)/tb_parameters $(RTL) tb/tb_parameters.sv
	$(VVP) $(BUILD)/tb_parameters

clean:
	rm -rf $(BUILD)
