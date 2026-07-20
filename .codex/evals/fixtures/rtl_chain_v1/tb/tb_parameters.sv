module tb_parameters;
    localparam int unsigned SEQ_W = 3;
    localparam int unsigned TIMEOUT_CYCLES = 2;

    logic clk = 1'b0;
    logic rst_n = 1'b0;
    logic start = 1'b0;
    logic cont = 1'b0;
    logic abort = 1'b0;
    logic [SEQ_W-1:0] seq_i = '0;
    logic active;
    logic [SEQ_W-1:0] expected_seq;
    logic accept;
    logic seq_error;
    logic timeout_abort;

    mctp_rx_context_tracker #(.SEQ_W(SEQ_W), .TIMEOUT_CYCLES(TIMEOUT_CYCLES)) dut (.*);
    always #5 clk = ~clk;

    task automatic drive(input logic s, input logic c, input logic a, input logic [SEQ_W-1:0] seq);
        @(negedge clk);
        start = s;
        cont = c;
        abort = a;
        seq_i = seq;
        @(posedge clk);
        #1;
    endtask

    initial begin
        repeat (2) @(posedge clk);
        rst_n = 1'b1;
        drive(1'b1, 1'b0, 1'b0, 3'd7);
        if (!accept || expected_seq != 3'd0) $fatal(1, "parameterized sequence wrap failed");
        drive(1'b0, 1'b1, 1'b0, 3'd0);
        if (!accept || expected_seq != 3'd1) $fatal(1, "parameterized continuation failed");
        drive(1'b0, 1'b0, 1'b0, '0);
        if (!active || timeout_abort) $fatal(1, "short timeout asserted early");
        drive(1'b0, 1'b0, 1'b0, '0);
        if (active || !timeout_abort) $fatal(1, "short timeout boundary failed");
        $display("PASS parameters");
        $finish;
    end
endmodule
