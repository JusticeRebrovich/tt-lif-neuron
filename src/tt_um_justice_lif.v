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
//
// Built-in self-test (uio_in[3] = 1):
//   The first clock resets the neurons. Then, for BIST_LEN clocks, an LFSR
//   drives all four neurons directly, each with its own bit pattern and
//   amplitude, while a counter steps through every weight and both refractory
//   modes. A signature register (MISR) folds in all four voltages and spikes.
//   Afterwards DONE is set, and PASS is set if the signature equals
//   BIST_GOLDEN, the value the Python golden model produces. Switching the
//   self-test off resets the neurons again.
//
// uo_out pages (uio_in[4:3]):
//   00: {V0[7:1], spike0}                        normal operation
//   01: {signature[5:0], PASS, DONE}             self-test status
//   11: signature[15:8]                          self-test signature, high byte
//   10: 0                                        reserved
// ---------------------------------------------------------------------------
module tt_um_justice_lif #(
    parameter [7:0]  THRESHOLD   = 8'd200,    // firing threshold of every neuron
    parameter [15:0] BIST_GOLDEN = 16'h53DF   // self-test signature of a healthy chip (test/chip_model.py)
) (
    input  wire [7:0] ui_in,    // input current I to neuron 0
    output wire [7:0] uo_out,   // selected by uio_in[4:3], see the page table above
    input  wire [7:0] uio_in,   // [1:0] weight select, [2] refractory mode, [3] BIST, [4] page
    output wire [7:0] uio_out,  // [7:5] = spikes of neurons 3, 2, 1
    output wire [7:0] uio_oe,   // [7:5] outputs, the rest inputs
    input  wire       ena,      // high when this design is selected
    input  wire       clk,
    input  wire       rst_n     // active-low reset
);

    localparam [10:0] BIST_LEN = 11'd1024;    // clocks of stimulus

    wire bist_en  = uio_in[3];
    wire page_alt = uio_in[4];

    wire [7:0] v0, v1, v2, v3;
    wire       s0, s1, s2, s3;

    // ---- built-in self-test: stimulus generator, counter and signature ----
    reg [10:0] bist_cnt;   // 0 = neurons in reset, 1..BIST_LEN = running, BIST_LEN+1 = done
    reg [7:0]  lfsr;       // pseudo-random stimulus, x^8 + x^6 + x^5 + x^4 + 1
    reg [15:0] misr;       // signature, x^16 + x^12 + x^5 + 1

    wire bist_start = bist_en && (bist_cnt == 11'd0);
    wire bist_done  = (bist_cnt == BIST_LEN + 11'd1);
    wire bist_pass  = bist_done && (misr == BIST_GOLDEN);

    wire        lfsr_fb   = lfsr[7] ^ lfsr[5] ^ lfsr[4] ^ lfsr[3];
    // Every bit of every voltage reaches the signature, so a fault in any neuron shows up.
    wire [15:0] misr_in   = {v0 ^ {v2[3:0], v2[7:4]}, v1 ^ {v3[3:0], v3[7:4]}} ^ {12'h000, s3, s2, s1, s0};
    wire [15:0] misr_next = {misr[14:0], 1'b0} ^ (misr[15] ? 16'h1021 : 16'h0000) ^ misr_in;

    always @(posedge clk) begin
        if (!rst_n || !bist_en) begin
            bist_cnt <= 11'd0;
            lfsr     <= 8'h01;
            misr     <= 16'h0000;
        end else if (bist_cnt == 11'd0) begin
            bist_cnt <= 11'd1;                  // the neurons are reset on this clock
        end else if (!bist_done) begin
            lfsr     <= {lfsr[6:0], lfsr_fb};
            misr     <= misr_next;
            bist_cnt <= bist_cnt + 11'd1;
        end
    end

    // What the self-test feeds the ring. Each neuron sees a different view of
    // the LFSR, at one of four amplitude levels that changes every 32 clocks,
    // one step out of phase with its neighbours. The mode changes every 128
    // clocks and the weight every 256.
    //   level 0: quiet, so V decays (tests the leak down to rest)
    //   level 1: creep, 12..19, so V hovers near the threshold (tests the threshold exactly)
    //   level 2: small, 0..31
    //   level 3: full, 0..255 (tests saturation and the refractory period)
    function [7:0] bist_amp(input [7:0] pattern, input [1:0] level);
        case (level)
            2'd0: bist_amp = 8'd0;
            2'd1: bist_amp = 8'd12 + {5'b00000, pattern[2:0]};
            2'd2: bist_amp = {3'b000, pattern[4:0]};
            2'd3: bist_amp = pattern;
        endcase
    endfunction

    wire [7:0] pat0 = lfsr;
    wire [7:0] pat1 = {lfsr[3:0], lfsr[7:4]};
    wire [7:0] pat2 = {lfsr[0], lfsr[1], lfsr[2], lfsr[3], lfsr[4], lfsr[5], lfsr[6], lfsr[7]};
    wire [7:0] pat3 = ~lfsr;
    wire [1:0] seg  = bist_cnt[6:5];

    wire [7:0] bist_i0 = bist_amp(pat0, seg);
    wire [7:0] bist_i1 = bist_amp(pat1, seg + 2'd1);
    wire [7:0] bist_i2 = bist_amp(pat2, seg + 2'd2);
    wire [7:0] bist_i3 = bist_amp(pat3, seg + 2'd3);

    // ---- the ring's inputs come from the pins, or from the self-test ----
    wire [7:0] i_ext   = bist_en ? bist_i0       : ui_in;
    wire [7:0] d1      = bist_en ? bist_i1       : 8'd0;   // neurons 1..3 are driven
    wire [7:0] d2      = bist_en ? bist_i2       : 8'd0;   // directly only during
    wire [7:0] d3      = bist_en ? bist_i3       : 8'd0;   // the self-test
    wire [1:0] w_sel   = bist_en ? bist_cnt[9:8] : uio_in[1:0];
    wire       mode    = bist_en ? bist_cnt[7]   : uio_in[2];
    // The neurons are reset on the first clock of the self-test and on the
    // first clock after it is switched off, so both the test and normal
    // operation start from a known state.
    wire       bist_exit = !bist_en && (bist_cnt != 11'd0);
    wire       n_rst_n   = rst_n && !bist_start && !bist_exit;

    // ---- ring weight: how hard one spike kicks the next neuron ----
    wire [7:0] w     = (w_sel == 2'd0) ? 8'd0   :   // ring off
                       (w_sel == 2'd1) ? 8'd64  :
                       (w_sel == 2'd2) ? 8'd128 :
                                         8'd255;    // one kick is enough to fire

    // ---- refractory mode: 4 cycles (input-paced) or 3 (self-sustaining) ----
    wire [2:0] refrac = mode ? 3'd3 : 3'd4;

    // A spike is registered, so its kick lands one clock after the spike.
    wire [7:0] kick0 = s3 ? w : 8'd0;
    wire [7:0] kick1 = s0 ? w : 8'd0;
    wire [7:0] kick2 = s1 ? w : 8'd0;
    wire [7:0] kick3 = s2 ? w : 8'd0;

    // Neuron 0 gets the external input plus the kick that closes the ring.
    wire signed [9:0] i0 = $signed({2'b00, i_ext}) + $signed({2'b00, kick0});
    wire signed [9:0] i1 = $signed({2'b00, d1}) + $signed({2'b00, kick1});
    wire signed [9:0] i2 = $signed({2'b00, d2}) + $signed({2'b00, kick2});
    wire signed [9:0] i3 = $signed({2'b00, d3}) + $signed({2'b00, kick3});

    lif_neuron #(.THRESHOLD(THRESHOLD)) n0 (.clk(clk), .rst_n(n_rst_n), .refrac(refrac), .i_in(i0), .v(v0), .spike(s0));
    lif_neuron #(.THRESHOLD(THRESHOLD)) n1 (.clk(clk), .rst_n(n_rst_n), .refrac(refrac), .i_in(i1), .v(v1), .spike(s1));
    lif_neuron #(.THRESHOLD(THRESHOLD)) n2 (.clk(clk), .rst_n(n_rst_n), .refrac(refrac), .i_in(i2), .v(v2), .spike(s2));
    lif_neuron #(.THRESHOLD(THRESHOLD)) n3 (.clk(clk), .rst_n(n_rst_n), .refrac(refrac), .i_in(i3), .v(v3), .spike(s3));

    // Neuron 0's voltage under its original name, so the testbench can read dut.v
    wire [7:0] v = v0;

    // ---- output page select ----
    assign uo_out  = (bist_en && page_alt) ? misr[15:8]                       :
                     bist_en               ? {misr[5:0], bist_pass, bist_done} :
                     page_alt              ? 8'h00                             :
                                             {v[7:1], s0};
    assign uio_out = {s3, s2, s1, 5'b00000};
    assign uio_oe  = 8'b1110_0000;

    // tie off unused signals so synthesis doesn't warn
    wire _unused = &{ena, uio_in[7:5], 1'b0};

endmodule
