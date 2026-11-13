# The sending loop of a pass

Date: 2026-11-13
Status: Accepted

## Context

The frame codec reached the repository, so the sender task was the next module of the firmware. Thinkbook section 7 stated what that task does. It sends the next packet after the callback of the previous packet returns. It counts `esp_now_send` errors by code. On `ESP_ERR_ESPNOW_NO_MEM`, it waits, retries, and counts the event. It bins the send-to-callback time into a histogram in memory.

Three values that the task needs appeared in no source.

The `go` command carries `frames`, and the accepted command fields record gave the sender both a `packets_sent` counter and a `messages_sent` counter. Thinkbook section 2 called a frame one transmission, and thinkbook section 3.8 took the airtime of a cell as 2000 frames of one payload each, so a frame is one packet on the air. A payload above the limit $L$ takes $n(p)$ packets, and the v2.0 payload list holds three sizes above that limit. A budget of 2000 packets therefore does not divide into whole messages for every cell, and no source stated what the last message does.

The command fields record fixed every histogram at 16 bins, and it stated that the last bin counts every value at or above its lower edge. It stated no edge. A bin edge binds every record that a corpus stores, because two runs with different edges hold histograms that no reader can compare.

Thinkbook section 11 answered `ESP_ERR_ESPNOW_NO_MEM` with wait, retry, and count, and it stated no wait and no retry budget. The reply timeout record noted that the same wait bounds no part of a pass.

The send-to-callback time is itself one of the observables that thinkbook section 2 names, and the first run exists to measure it. A bin edge chosen now therefore rests on a distribution that no run has produced.

If nothing was decided, the sender task would fix the meaning of the frame budget, the edges of a histogram that every record carries, and the behavior after a failed send, all by accident.

## Alternatives considered

- A budget counted in messages rather than packets, which makes the airtime of a cell depend on the payload and breaks the 2000-frame figure of thinkbook section 3.8.
- A last message cut short at the budget, which reaches the receiver as an incomplete message and raises message loss by a frame that the sender never meant to complete.
- A linear scale for the send-to-callback histogram, which needs an upper bound that no run has produced.
- A doubling scale from 1 microsecond, which spends six bins below the airtime of the smallest frame of the sweep.
- Edges chosen after the first run, which leaves the sender with no histogram to write on that run.
- A send that stops the pass on the first failure, which loses a cell to one transient error.
- A retry without a budget, which hangs a pass on a node that never recovers.

## Decision

**The frame budget.** `frames` counts packets on the air, as thinkbook sections 2 and 3.8 use the term. A pass sends whole messages only. The sender sends the next message while the packets of that message fit inside the remaining budget, and it stops when they do not. `packets_sent` therefore reaches the budget exactly when $n(p)$ divides it, and falls short of it by fewer than $n(p)$ packets otherwise.

A message cut short at the budget would arrive at the receiver with a missing fragment, and the receiver would count it incomplete. That count feeds `message_loss`, so a truncated last message would state a loss that the link did not cause.

**The send-to-callback histogram.** The bins hold microseconds on a doubling scale. Bin 0 holds every value below 64 microseconds. Bin $k$, for $k$ from 1 to 14, holds every value from $64 \times 2^{k-1}$ up to $64 \times 2^{k}$, excluding the upper edge. Bin 15 holds every value at or above 1048576 microseconds, which is the overflow bin that the command fields record requires.

The scale is a `[proposal]`. It places the swept payload list across the middle of the range: the airtime of a 14-byte frame falls in bin 4, a 250-byte frame in bin 6, and a 1470-byte frame in bin 8. A callback cannot return before the airtime of its frame, so those bins are the floor of each cell, and the bins above them hold the retry structure that a unicast pass adds. The first bench run replaces the scale with one that the measured distribution supports.

**A failed send.** The sender counts every `esp_now_send` error by its code. On `ESP_ERR_ESPNOW_NO_MEM` it waits 10 milliseconds `[proposal]`, counts one event in `no_mem_events`, and sends that packet again. It makes at most 10 such attempts `[proposal]` for one packet. After the last attempt it counts the error under its code in `send_errors`, counts the packet as neither sent nor delivered, and moves to the next packet of the pass.

A pass therefore ends at its budget rather than at its first failure, and a node that never frees memory costs one pass rather than a run that never returns.

**What this record does not state.** The bins of `loss_run_length_histogram` belong to the receiver, and the record of the receiver task states them.

## Consequences

- `frames_sent` of a `go` reply and `packets_sent` of a `stats` reply hold one value for one pass, because both count packets that the sender put on the air.
- `packets_sent` falls below the budget for a payload above the limit $L$. The v2.0 list holds three such sizes, and the v1.0 list holds four.
- `messages_sent` is `packets_sent` divided by $n(p)$, with no remainder, because a pass sends whole messages only.
- The bin edges bind every record that a corpus stores. A change to them needs a new record, and it makes a histogram of an earlier run incomparable with a later one.
- The scale, the wait, and the attempt budget carry `[proposal]`. The first bench run replaces each one with a `[measured]` figure.
- A cell of the smallest payload fills bin 4 and above, so bins 0 to 3 stay empty on a healthy broadcast pass. A count in bin 0 states a callback that returned faster than the airtime of its frame, which is a result to investigate rather than to report.
- The wait after a no-memory error lengthens a pass, and the liveness timeout of the reply timeout record covers it, because that timeout measures silence between replies rather than the length of a pass.
- Watch `no_mem_events` against the long-run guard of thinkbook section 8. A count that rises through a run is the failure that the guard exists to catch.
