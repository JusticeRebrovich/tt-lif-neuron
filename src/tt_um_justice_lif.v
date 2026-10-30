// Leaky integrate-and-fire neuron for Tiny Tapeout (SKY130)
// Author: Justice Rebrovich
//
// Each clock:  V_next = V - (V >> LEAK_SHIFT) + I
//   - leak is a right shift, so no multiplier is needed
//   - the add saturates at 255 instead of wrapping
//   - if V_next >= THRESHOLD: fire a spike, reset V to 0,
//     and ignore input for REFRAC cycles (refractory period)

`default_nettype none
`timescale 1ns / 1ps

module tt_um_justice_lif #(
    parameter [7:0] THRESHOLD  = 8'd200,
    parameter       LEAK_SHIFT = 4,      // leak = V/16 per cycle
    parameter [2:0] REFRAC     = 3'd4    // refractory cycles after a spike
) (
    input  wire [7:0] ui_in,    // input current I
    output wire [7:0] uo_out,   // [0] = spike, [7:1] = top 7 bits of V
    input  wire [7:0] uio_in,   // unused
    output wire [7:0] uio_out,  // unused
    output wire [7:0] uio_oe,   // unused (all inputs)
    input  wire       ena,      // high when this design is selected
    input  wire       clk,
    input  wire       rst_n     // active-low reset
);

    reg [7:0] v;          // membrane voltage
    reg       spike;      // registered spike output
    reg [2:0] refr_cnt;   // refractory countdown

    // ---- next-state math (combinational) ----
    // Leak = V/16, but at least 1 whenever V > 0. Without the minimum,
    // V >> 4 is 0 once V < 16 and the neuron gets stuck at 15 instead of
    // decaying to rest (bug caught by test_decay_to_rest).
    wire [7:0] leak_raw = v >> LEAK_SHIFT;
    wire [7:0] leak     = (leak_raw == 8'd0 && v != 8'd0) ? 8'd1 : leak_raw;
    wire [7:0] v_leaked = v - leak;                 // can't underflow, leak <= v
    wire [8:0] sum      = {1'b0, v_leaked} + {1'b0, ui_in};  // 9 bits holds the carry
    wire [7:0] v_sat    = sum[8] ? 8'hFF : sum[7:0];         // saturate, don't wrap

    // ---- state update (sequential) ----
    always @(posedge clk) begin
        if (!rst_n) begin
            v        <= 8'd0;
            spike    <= 1'b0;
            refr_cnt <= 3'd0;
        end else if (refr_cnt != 0) begin
            // refractory: ignore input, hold V at 0, count down
            v        <= 8'd0;
            spike    <= 1'b0;
            refr_cnt <= refr_cnt - 3'd1;
        end else if (v_sat >= THRESHOLD) begin
            // fire
            v        <= 8'd0;
            spike    <= 1'b1;
            refr_cnt <= REFRAC;
        end else begin
            // integrate and leak
            v        <= v_sat;
            spike    <= 1'b0;
        end
    end

    assign uo_out  = {v[7:1], spike};
    assign uio_out = 8'd0;
    assign uio_oe  = 8'd0;

    // tie off unused inputs so synthesis doesn't warn
    wire _unused = &{ena, uio_in, v[0], 1'b0};

endmodule
