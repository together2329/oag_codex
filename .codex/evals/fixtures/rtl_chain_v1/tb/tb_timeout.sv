module tb_timeout;
    localparam int unsigned TIMEOUT_CYCLES = 4;

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

    mctp_rx_context_tracker #(.TIMEOUT_CYCLES(TIMEOUT_CYCLES)) dut (.*);
    always #5 clk = ~clk;

    task automatic tick;
        @(negedge clk);
        start = 1'b0;
        cont = 1'b0;
        abort = 1'b0;
        @(posedge clk);
        #1;
    endtask

    initial begin
        repeat (2) @(posedge clk);
        rst_n = 1'b1;
        @(negedge clk);
        start = 1'b1;
        seq_i = 2'd0;
        @(posedge clk);
        #1;
        start = 1'b0;

        repeat (TIMEOUT_CYCLES - 1) begin
            tick();
            if (!active || timeout_abort) $fatal(1, "timeout asserted early");
        end
        tick();
        if (active || !timeout_abort) $fatal(1, "timeout did not abort at the contract boundary");

        tick();
        if (timeout_abort) $fatal(1, "timeout_abort must be a pulse");
        $display("PASS timeout");
        $finish;
    end
endmodule
