// Spiking pattern generator for Tiny Tapeout (SKY130)
// Author: Justice Rebrovich
//
// Four leaky integrate-and-fire neurons in a ring. Neuron 0 is driven by the
// external input; each spike adds a "kick" of weight W to the next neuron,
// so a spike travels 0 -> 1 -> 2 -> 3 -> 0.
//
// Each neuron, each clock:  V_next = V - (V >> LEAK_SHIFT) + I
//   - leak is a right shift, so no multiplier is needed
//   - the result is clamped to 0..255 instead of wrapping
//   - if V_next >= THRESHOLD: fire a spike, reset V to 0,
//     and ignore input for 3 or 4 cycles (refractory period)

`default_nettype none
`timescale 1ns / 1ps

// ---------------------------------------------------------------------------
// One LIF neuron. The input current is signed so that later stages can add
// inhibition (negative current); V floors at 0 as well as saturating at 255.
// ---------------------------------------------------------------------------
module lif_neuron #(
    parameter [7:0] THRESHOLD  = 8'd200,
    parameter       LEAK_SHIFT = 4       // leak = V/16 per cycle
) (
    input  wire              clk,
    input  wire              rst_n,     // active-low synchronous reset
    input  wire        [2:0] refrac,    // refractory cycles, latched when the neuron fires
    input  wire signed [9:0] i_in,      // summed input current, -512..511
    output reg         [7:0] v,         // membrane voltage
    output reg               spike      // registered spike output
);

    reg [2:0] refr_cnt;   // refractory countdown

    // ---- next-state math (combinational) ----
    // Leak = V/16, but at least 1 whenever V > 0. Without the minimum,
    // V >> 4 is 0 once V < 16 and the neuron gets stuck at 15 instead of
    // decaying to rest (bug caught by test_decay_to_rest).
    wire [7:0] leak_raw = v >> LEAK_SHIFT;
    wire [7:0] leak     = (leak_raw == 8'd0 && v != 8'd0) ? 8'd1 : leak_raw;
    wire [7:0] v_leaked = v - leak;                 // can't underflow, leak <= v

    // 11-bit signed sum covers -512..766, so neither end can wrap
    wire signed [10:0] sum = $signed({3'b000, v_leaked}) + $signed({i_in[9], i_in});
    wire        [7:0]  v_sat = sum[10]      ? 8'd0  :     // negative: floor at 0
                               (|sum[9:8])  ? 8'hFF :     // above 255: saturate
                                              sum[7:0];

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
            refr_cnt <= refrac;
        end else begin
            // integrate and leak
            v        <= v_sat;
            spike    <= 1'b0;
        end
    end

endmodule

// ---------------------------------------------------------------------------
// Top level: four neurons in a ring.
// With uio_in[2:0] = 0 the ring weight is 0 and the refractory period is 4, so
// neuron 0 behaves exactly like the original single-neuron design (the
// original tests run in this mode).
//
// Refractory mode (uio_in[2]):
//   0: 4 cycles. The kick from neuron 3 reaches neuron 0 while it is still
//      refractory, so each wave makes one pass and the input sets the rhythm.
//   1: 3 cycles. The kick arrives just after neuron 0 recovers, so at weight
//      255 a single spike keeps circulating: a self-sustaining oscillator.
// ---------------------------------------------------------------------------
module tt_um_justice_lif (
    input  wire [7:0] ui_in,    // input current I to neuron 0
    output wire [7:0] uo_out,   // [0] = neuron 0 spike, [7:1] = top 7 bits of its V
    input  wire [7:0] uio_in,   // [1:0] = ring weight select, [2] = refractory mode
    output wire [7:0] uio_out,  // [7:5] = spikes of neurons 3, 2, 1
    output wire [7:0] uio_oe,   // [7:5] outputs, the rest inputs
    input  wire       ena,      // high when this design is selected
    input  wire       clk,
    input  wire       rst_n     // active-low reset
);

    // ---- ring weight: how hard one spike kicks the next neuron ----
    wire [1:0] w_sel = uio_in[1:0];
    wire [7:0] w     = (w_sel == 2'd0) ? 8'd0   :   // ring off
                       (w_sel == 2'd1) ? 8'd64  :
                       (w_sel == 2'd2) ? 8'd128 :
                                         8'd255;    // one kick is enough to fire

    // ---- refractory mode: 4 cycles (input-paced) or 3 (self-sustaining) ----
    wire [2:0] refrac = uio_in[2] ? 3'd3 : 3'd4;

    wire [7:0] v0, v1, v2, v3;
    wire       s0, s1, s2, s3;

    // A spike is registered, so its kick lands one clock after the spike.
    wire [7:0] kick0 = s3 ? w : 8'd0;
    wire [7:0] kick1 = s0 ? w : 8'd0;
    wire [7:0] kick2 = s1 ? w : 8'd0;
    wire [7:0] kick3 = s2 ? w : 8'd0;

    // Neuron 0 gets the external input plus the kick that closes the ring.
    wire signed [9:0] i0 = $signed({2'b00, ui_in}) + $signed({2'b00, kick0});
    wire signed [9:0] i1 = $signed({2'b00, kick1});
    wire signed [9:0] i2 = $signed({2'b00, kick2});
    wire signed [9:0] i3 = $signed({2'b00, kick3});

    lif_neuron n0 (.clk(clk), .rst_n(rst_n), .refrac(refrac), .i_in(i0), .v(v0), .spike(s0));
    lif_neuron n1 (.clk(clk), .rst_n(rst_n), .refrac(refrac), .i_in(i1), .v(v1), .spike(s1));
    lif_neuron n2 (.clk(clk), .rst_n(rst_n), .refrac(refrac), .i_in(i2), .v(v2), .spike(s2));
    lif_neuron n3 (.clk(clk), .rst_n(rst_n), .refrac(refrac), .i_in(i3), .v(v3), .spike(s3));

    // Neuron 0's voltage under its original name, so the testbench can read dut.v
    wire [7:0] v = v0;

    assign uo_out  = {v[7:1], s0};
    assign uio_out = {s3, s2, s1, 5'b00000};
    assign uio_oe  = 8'b1110_0000;

    // tie off unused signals so synthesis doesn't warn
    wire _unused = &{ena, uio_in[7:3], v[0], v1, v2, v3, 1'b0};

endmodule
