module mctp_rx_context_tracker #(
    parameter int unsigned SEQ_W = 2,
    parameter int unsigned TIMEOUT_CYCLES = 4
) (
    input  logic                 clk,
    input  logic                 rst_n,
    input  logic                 start,
    input  logic                 cont,
    input  logic                 abort,
    input  logic [SEQ_W-1:0]     seq_i,
    output logic                 active,
    output logic [SEQ_W-1:0]     expected_seq,
    output logic                 accept,
    output logic                 seq_error,
    output logic                 timeout_abort
);
    localparam int unsigned AGE_W = (TIMEOUT_CYCLES <= 1) ? 1 : $clog2(TIMEOUT_CYCLES + 1);

    logic [AGE_W-1:0] age_q;

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            active        <= 1'b0;
            expected_seq  <= '0;
            accept        <= 1'b0;
            seq_error     <= 1'b0;
            timeout_abort <= 1'b0;
            age_q         <= '0;
        end else begin
            accept        <= 1'b0;
            seq_error     <= 1'b0;
            timeout_abort <= 1'b0;

            if (!active) begin
                age_q <= '0;
                if (start) begin
                    active       <= 1'b1;
                    expected_seq <= seq_i;
                    accept       <= 1'b1;
                end
            end else if (cont) begin
                if (seq_i == expected_seq) begin
                    expected_seq <= expected_seq + 1'b1;
                    accept       <= 1'b1;
                    age_q        <= '0;
                end else begin
                    seq_error <= 1'b1;
                end
            end else if (abort) begin
                active <= 1'b0;
                age_q  <= '0;
            end else begin
                age_q <= age_q;
            end
        end
    end
endmodule
