# The reply timeout of each command, the progress reply of a pass, and the meaning of a timeout

Date: 2026-11-12
Status: Accepted

## Context

The host held a control line codec and a firmware flasher, and it held no transport. `host/src/bolis/protocol.py` encoded one command and decoded one reply as text, and it stated that the transport that owns the port enforces the read timeout. `host/src/bolis/flasher.py` took a reader from its caller rather than opening a port. `bolis flash` and `bolis run` raised an error that named the missing transport. Every consumer of the transport was written and tested, so the transport was the one module between the host and a first run.

The accepted record [2026-11-11-control-line-command-fields.md](./2026-11-11-control-line-command-fields.md) stated that a `go` reply arrives after the pass ends, and that the host therefore holds a longer reply timeout for `go` than for any other command. It stated no value for either timeout.

A timeout that covers a whole pass rests on the duration of that pass. Thinkbook section 3.8 bounded one term of that duration: a cell of 1470-byte frames needs at least $2000 \times 12.58$ ms of airtime, about 25 s. It bounded no other term. The send-to-callback time of each frame is one of the observables of thinkbook section 2, and the command fields record gives it the histogram `send_to_callback_us_histogram`, so the quantity that sets such a timeout is a quantity that the first run exists to measure. A unicast pass adds retry backoff, which no source bounds. The long-run guard adds a wait on `ESP_ERR_ESPNOW_NO_MEM`, which no source bounds. A timeout for a whole pass therefore rested on a figure that no run had produced, and a figure set too low sends the frames of a pass a second time into a cell that already counted them.

The accepted record gave the `go` reply three fields: `cell_id`, `done`, and `frames_sent`. A reply that a node writes once, at the end of a pass, has no use for `done`, because the arrival of that reply states that the pass ended. The field set therefore already described a reply that carries `done` set to false.

`bol_handle_line` in `components/bolis/src/bol_console.c` answered nothing to a line whose `cmd`, `seq`, or `proto` did not parse. The node counted the line and wrote a log warning, because it could not name the command it failed to read. A comment in that file stated the behavior, and no record stated it. The host therefore saw three failures as one silence: a lost line, a node that reset, and a line that the node rejected.

Thinkbook section 11 gave a reply timeout one response, which retries the command, then stops the run and keeps the partial record. It gave a node reset a different response, which marks the cell invalid and reruns it once, and it named a new `hello` banner or a missing reply as the detection of that reset. A missing reply satisfied both rows, so two responses rested on one observation.

If nothing was decided, the first module to open the port would fix every timeout value by accident. That module would also read a rejected line as a lost line, and an identical retry reproduces a rejection rather than recovering from it.

## Alternatives considered

- One `go` reply at the end of a pass, with a host timeout sized for the whole pass, which sizes a timeout from the send-to-callback time that the first run exists to measure.
- A progress reply after a fixed number of frames, which stretches the interval between replies as the payload grows, so one value cannot separate a slow cell from a stalled cell.
- One timeout for every command, sized for a pass, which makes an unreachable node cost a pass timeout at `hello`.
- An error reply for a line whose keys do not parse, which the envelope cannot represent, because a reply carries `reply` and `seq` and the node read neither.
- A retry of `go` after a silence, which sends the frames of a pass into a cell whose counters already moved.
- A retry budget above one for a short command, which repeats the rejection of a line that the node cannot parse.
- The original `seq` on a retry, which leaves a late reply to the first attempt indistinguishable from the reply to the retry.
- Every timeout read as a node reset, which reruns a cell that a lost line explains.
- Every timeout read as line loss, which stops a run that one reset explains.

## Decision

The transport owns the port, the read timeout, and the retry of one command.

**The port.** The transport opens the port at 115200 baud, with eight data bits, no parity, one stop bit, and no flow control. That rate is the ESP-IDF console default, and `components/bolis/examples/bench/sdkconfig.defaults` does not override it.

**Lines.** The transport reads whole lines. It discards every line that does not start with `@bol `, so the application log and the control plane share one port (thinkbook section 7). It passes a prefixed line to the codec. The transport refuses a port name that pyserial reads as a URL, through the check that the flasher already holds, so no command reaches a serial server over a network (specification section 7).

**The progress reply.** A sender writes a `go` reply at an interval during a pass, and not at the end alone. A reply that a sender writes during a pass carries `done` set to false, and `frames_sent` set to the number of frames whose send callback has returned. The reply at the end of the pass carries `done` set to true. Every reply of one pass carries the `seq` of its `go` command.

This amends the accepted record `2026-11-11-control-line-command-fields.md`, which states that a node writes the `go` reply when the send callback of the last frame of the pass returns. This record changes when a node writes a reply. It adds no key and removes none, because that record already gives the reply `done` and `frames_sent`. It replaces no other statement of that record, and that record keeps `Status: Accepted`.

A sender writes a progress reply when 1000 ms have passed since its last line of that pass `[proposal]`. A sender writes that line between two frames, and never between a send and its callback, so a console write stays outside the window that `send_to_callback_us_histogram` measures.

**Two reply timeouts.** Every command other than `go` carries the short timeout, which is 2 s `[proposal]`. One line of 512 bytes takes about 44 ms at 115200 baud, and a command with its reply takes about 89 ms, so the short timeout leaves margin for log lines that queue ahead of a reply.

`go` carries a liveness timeout, which is 3 s `[proposal]`. The host restarts that timeout on every line that the node writes for the pass. The timeout therefore measures silence, and not the duration of a pass. Three times the progress interval leaves one lost progress line without effect.

A pass of the largest payload of the sweep lasts about 25 s, and a pass of the smallest lasts about 1.3 s, from the airtime that thinkbook section 3 states. One liveness timeout covers that range, because the host waits on a line rather than on a pass.

**A timeout of a command other than `go`.** A timeout names one of three failures, and the host separates them by observation rather than by assumption. If the transport reads a `hello` banner while a command is outstanding, the node reset, and the run applies the reset response of thinkbook section 11, which marks the cell invalid and reruns it once. Otherwise the host retries the command once, as the reply timeout response of thinkbook section 11 states.

A retry carries the next `seq`, because the wire format record [2026-10-01-control-line-wire-format.md](./2026-10-01-control-line-wire-format.md) states that the host raises `seq` for each command. The transport discards every reply whose `seq` does not match the outstanding command, so a late reply to a first attempt changes no state.

The retry budget is one. The host cannot separate a lost line from a rejected line at the moment of a timeout, and an identical retry reproduces a rejection. If the retry also times out, the host stops the run and keeps the partial record.

**A timeout of `go`.** The host does not retry a `go` command. A retry sends the frames of a pass into a cell whose counters already moved, and a progress reply states how far that pass reached. The host marks the cell invalid and reruns it once, as thinkbook section 11 states for a node that reset. If the rerun also falls silent, the host stops the run and keeps the partial record.

**Evidence after a run.** The `rejected_lines` counter of the `stats` reply separates a rejected line from a lost line after a run. The host reads that counter and states it in the run record.

## Consequences

- The `go` timeout rests on no figure that a run has yet to produce. It measures silence, so the progress interval and the liveness timeout are properties of a node and a serial line rather than of a radio link.
- This record amends the timing of the `go` reply in an accepted record. It adds no key, so the reply shape of `proto` version 2 is unchanged.
- A host and a node of version 2 both carry the progress reply, because version 2 has not shipped. A host that expects one reply and a node that writes many would otherwise disagree inside one version.
- The transport reads `go` replies until one carries `done` set to true, so the read loop of a pass differs from the read loop of every other command.
- A progress line measures about 92 bytes and takes about 8 ms at 115200 baud. A pass of the largest payload holds about 25 such lines, which adds about 200 ms to a pass of about 25 s, or about 0.8 percent of it.
- A pass of the smallest payload ends before its first progress reply, so that pass writes one reply, with `done` set to true.
- The host reads `frames_sent` during a pass, so a run that stops names the frame count that the pass reached.
- A node that stops sending without resetting is detected in about 3 s, rather than after a pass timeout.
- The progress interval, the liveness timeout, and the short timeout carry `[proposal]`. The first bench run replaces each with a `[measured]` figure.
- A console write between two frames lengthens the gap between those frames. Watch the first run for a difference between a cell of the largest payload and the airtime that thinkbook section 3 states for it.
- An unreachable node costs 2 s at `hello` rather than a pass timeout.
- A `hello` banner during a run costs the cell, because a reset node holds no role and no cell. The host applies `role` and `cell` again before it reruns that cell.
- A host line longer than 512 bytes draws no reply, so the codec enforces the limit before the transport writes a line.
- `stats` must read `rejected_lines` for a run record to separate a rejected line from a lost line, so the suppression of Rule 8.9 on `s_rejected_line_count` is removed when `stats` lands.
- The settle time between the last `go` reply and a `stats` command stays outside this record. The orchestrator states it.
- A change to the progress interval, to the liveness timeout, or to the retry budget needs a new record, because each one changes how a run ends.
