module tb_precedence;
    logic clk = 1'b0;
    logic rst_n = 1'b0;
    logic start = 1'b0;
    logic cont = 1'b0;
    logic abort = 1'b0;
    logic [1:0] seq_i = '0;
    logic active;
    logic [1:0] expected_seq;
    logic accept;
    logic seq_error;
    logic timeout_abort;

    mctp_rx_context_tracker dut (.*);
    always #5 clk = ~clk;

    task automatic drive(input logic s, input logic c, input logic a, input logic [1:0] seq);
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
        drive(1'b1, 1'b0, 1'b0, 2'd1);
        if (!active) $fatal(1, "context did not start");

        drive(1'b1, 1'b0, 1'b0, 2'd3);
        if (!active || accept || expected_seq != 2'd2) $fatal(1, "start was not ignored while active");

        drive(1'b0, 1'b1, 1'b1, 2'd2);
        if (active || accept || seq_error) $fatal(1, "abort did not win simultaneous precedence");

        $display("PASS precedence");
        $finish;
    end
endmodule
