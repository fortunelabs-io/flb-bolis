# The receiving loop of a pass

Date: 2026-11-13
Status: Accepted

## Context

The sending loop record settled what a pass sends, and it left the bins of `loss_run_length_histogram` to the record of the receiver task. That task was the next module of the firmware.

Thinkbook section 7 stated what the task does. The receive callback runs in the WiFi task, so it copies the packet header, the length, and the RSSI to a queue and returns. A lower-priority task checks the header and the fill, tracks sequence numbers per cell and pass, and updates the counters.

Four values that the task needs appeared in no source.

The command fields record fixed every histogram at 16 bins and stated no edge. A run length counts consecutive lost packets, and thinkbook section 3.6 keeps that histogram so that a later fit of a two-state burst model can read it.

A queue sits between the callback and the task, and no source stated its depth. A queue has a depth, and a packet that arrives when the queue is full reaches no counter.

That last point reaches further than a depth. The receiver counters of the command fields record are `packets_received`, `duplicates`, `foreign_packets`, `messages_complete`, `messages_incomplete`, `corrupt_packets`, `loss_run_length_histogram`, `rssi_min_dbm`, `rssi_mean_dbm`, and `rssi_max_dbm`. None of them states a packet that reached the node and that the node then dropped. Such a packet is absent from `packets_received`, so the host counts it as a frame that the link lost. A node that cannot keep up therefore reports a loss that the link did not cause, and no counter separates the two.

The receiver drops a duplicate and finds a gap by tracking sequence numbers, and it holds no heap (MISRA Dir 4.12), so the span of sequence numbers that it remembers is bounded and no source stated that bound.

A message completes when every fragment of it arrives. The receiver holds no heap, so the messages that it tracks at once are bounded, and no source stated that bound either.

If nothing was decided, the receiver task would fix the bins of a corpus artifact, the depth of its queue, and the span of its memory by accident, and a packet that the node dropped would enter every record as a loss of the link.

## Alternatives considered

- A doubling scale for the run-length histogram, which spends bins above 2000 that no pass of that budget can reach.
- A run length counted in messages rather than packets, which mixes the unit of the histogram with the unit of the pass.
- A packet dropped at a full queue counted as a lost frame, which reports the speed of the node as a property of the link.
- A packet dropped at a full queue counted in `corrupt_packets`, which states that the link damaged a frame that it delivered whole.
- A queue deep enough for a whole pass, which holds 2000 entries of header and RSSI in memory that the node does not have.
- A receiver that remembers every sequence number of a pass, which needs a bitmap of the frame budget and grows with it.
- A receiver that remembers one packet, which reads any reordered pair as two losses and one duplicate.
- A table of messages under assembly, which the sender never needs, because a pass sends one message at a time and in order.

## Decision

**The run-length histogram.** Bin $k$, for $k$ from 0 to 14, holds a run of exactly $k + 1$ lost packets. Bin 15 holds every run of 16 packets or more, which is the overflow bin that the command fields record requires. The scale is linear because the mass of a healthy pass sits at the shortest runs, and a fit of the burst model of thinkbook section 3.6 needs resolution there rather than above it.

**A packet that the node drops.** A receiver reply carries `dropped_packets`, a new counter that states the packets that reached the callback and that the node did not process. This amends the accepted record `2026-11-11-control-line-command-fields.md`, which states the other ten counters and which keeps `Status: Accepted`. The key reaches a node at `proto` version 2, which has not shipped, so it costs no second rise of that version. The run record format gains the same key while `record_version` is 1 and no run has written a record, so it costs no rise of that version either.

A dropped packet is not a loss of the link and not a corrupt frame. It states that the node did not keep up, so the report reads a cell with a count above zero as a cell that measured the node rather than the link.

**The queue.** The queue between the callback and the task holds 32 entries `[proposal]`. Each entry holds the frame header, the length, and the RSSI, and not the payload, because the task checks the fill from the header rather than from a copy of the bytes.

**Sequence numbers.** The receiver derives the position of a packet inside its pass from the message ID and the fragment index of its header, which rise together through a pass. It holds a window of the 64 most recent positions `[proposal]`. A packet whose position the window already marks counts in `duplicates`. A packet below the floor of the window counts in `duplicates` as well, because a pass sends each position once and the node already passed that position. The window bounds the memory of the receiver at 64 bits per pass.

**A message.** The receiver assembles one message at a time, because a pass sends whole messages in order. A message counts in `messages_complete` when every fragment of it arrives. It counts in `messages_incomplete` when a fragment of a later message arrives first, or when the pass ends with a fragment missing.

**RSSI.** `rssi_min_dbm`, `rssi_mean_dbm`, and `rssi_max_dbm` cover the packets that passed the header check. The mean is the arithmetic mean of those packets. A pass that received no such packet states no RSSI.

## Consequences

- `dropped_packets` separates the speed of a node from the loss of a link. Without it, a slow node and a bad link read the same in every record.
- This record amends the counter set of an accepted record for the second time, after the frame header encoding record added `run_id` to `role`. A reader of the control line contract reads the command fields record and every record that amends it.
- The schema of the run record gains `dropped_packets` in its receiver counters, and the loss derivations of the loss quantities record are unchanged, because that counter divides nothing.
- The bin edges bind every record that a corpus stores. A change to them needs a new record and makes a histogram of an earlier run incomparable with a later one.
- The queue depth, the window, and the bin edges carry `[proposal]` except where stated. The first bench run replaces the depth and the window with `[measured]` figures.
- A run of 16 or more lost packets lands in one bin, so a cell whose bin 15 holds a count needs the raw figure of a later version rather than this histogram.
- A reordered pair inside the window counts no duplicate and no loss, and a reordered pair wider than the window counts one duplicate.
- The receiver holds 64 bits of window and 32 queue entries per pass, and neither grows with the frame budget.
- Watch `dropped_packets` on the cell of the smallest payload. That cell has the highest packet rate of the sweep, so it is the cell where a node that cannot keep up shows first.
