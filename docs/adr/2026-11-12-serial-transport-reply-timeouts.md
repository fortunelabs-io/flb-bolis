# The reply timeout of each command and the meaning of a timeout

Date: 2026-11-12
Status: Proposed

## Context

The host held a control line codec and a firmware flasher, and it held no transport. `host/src/bolis/protocol.py` encoded one command and decoded one reply as text, and it stated that the transport that owns the port enforces the read timeout. `host/src/bolis/flasher.py` took a reader from its caller rather than opening a port. `bolis flash` and `bolis run` raised an error that named the missing transport. Every consumer of the transport was written and tested, so the transport was the one module between the host and a first run.

The accepted record [2026-11-11-control-line-command-fields.md](./2026-11-11-control-line-command-fields.md) stated that a `go` reply arrives after the pass ends, and that the host therefore holds a longer reply timeout for `go` than for any other command. It stated no value for either timeout. Thinkbook section 3.8 stated that a cell of 1470-byte frames needs at least $2000 \times 12.58$ ms of airtime, about 25 s, and that a unicast pass of the same cell lasts at least as long because each retry adds backoff time. No source bounded the retry backoff. No source bounded the wait that the long-run guard adds on `ESP_ERR_ESPNOW_NO_MEM` (thinkbook section 8).

`bol_handle_line` in `components/bolis/src/bol_console.c` answered nothing to a line whose `cmd`, `seq`, or `proto` did not parse. The node counted the line and wrote a log warning, because it could not name the command it failed to read. A comment in that file stated the behavior, and no record stated it. The host therefore saw three failures as one silence: a lost line, a node that reset, and a line that the node rejected.

Thinkbook section 11 gave a reply timeout one response, which retries the command, then stops the run and keeps the partial record. It gave a node reset a different response, which marks the cell invalid and reruns it once, and it named a new `hello` banner or a missing reply as the detection of that reset. A missing reply satisfied both rows, so two responses rested on one observation.

If nothing was decided, the first module to open the port would fix every timeout value by accident. That module would also read a rejected line as a lost line, and an identical retry reproduces a rejection rather than recovering from it.

## Alternatives considered

- One timeout for every command, sized for `go`, which makes an unreachable node cost a full pass timeout at `hello`.
- A constant for the `go` timeout, which holds only while the frame count and the payload limit hold.
- A progress reply during a pass, which changes the `go` reply that the command fields record fixed, and which raises `proto`.
- An error reply for a line whose keys do not parse, which the envelope cannot represent, because a reply carries `reply` and `seq` and the node read neither.
- A retry budget above one, which repeats the rejection of a line that the node cannot parse.
- The original `seq` on a retry, which leaves a late reply to the first attempt indistinguishable from the reply to the retry.
- Every timeout read as a node reset, which reruns a cell that a lost line explains.
- Every timeout read as line loss, which stops a run that one reset explains.

## Decision

The transport owns the port, the read timeout, and the retry of one command.

The transport opens the port at 115200 baud, with eight data bits, no parity, one stop bit, and no flow control. That rate is the ESP-IDF console default, and `components/bolis/examples/bench/sdkconfig.defaults` does not override it.

The transport reads whole lines. It discards every line that does not start with `@bol `, so the application log and the control plane share one port (thinkbook section 7). It passes a prefixed line to the codec.

The transport refuses a port name that pyserial reads as a URL, through the check that the flasher already holds, so no command reaches a serial server over a network (specification section 7).

Two reply timeouts apply. Every command other than `go` carries the short timeout, which is 2 s `[proposal]`. One line of 512 bytes takes about 44 ms at 115200 baud, and a command with its reply takes about 89 ms, so the short timeout leaves margin for log lines that queue ahead of a reply.

The `go` command carries a timeout that the host computes for the pass:

$$t_{go} = N \times a_{max} \times k + m$$

$N$ is the frame count that the command carries `[configured]`. $a_{max}$ is 12.58 ms, the airtime of one frame at the payload limit (thinkbook section 3.8). The payload limit bounds the airtime of every frame, so one value of $a_{max}$ covers every cell of the sweep. $k$ is 2 for a broadcast pass and 4 for a unicast pass `[proposal]`. $m$ is 5 s `[proposal]`.

The broadcast factor absorbs the inter-frame gap, the send callback latency, and the control overhead, which no source quantifies. The unicast factor is larger, because retry backoff extends a unicast pass by an amount that no source bounds.

A timeout names one of three failures, and the host separates them by observation rather than by assumption. If the transport reads a `hello` banner while a command is outstanding, the node reset, and the run applies the reset response of thinkbook section 11, which marks the cell invalid and reruns it once. Otherwise the host retries the command once, as the reply timeout response of thinkbook section 11 states.

A retry carries the next `seq`, because the wire format record [2026-10-01-control-line-wire-format.md](./2026-10-01-control-line-wire-format.md) states that the host raises `seq` for each command. The transport discards every reply whose `seq` does not match the outstanding command, so a late reply to a first attempt changes no state.

The retry budget is one. The host cannot separate a lost line from a rejected line at the moment of a timeout, and an identical retry reproduces a rejection. If the retry also times out, the host stops the run and keeps the partial record.

The `rejected_lines` counter of the `stats` reply is the evidence that separates a rejected line from a lost line after a run. The host reads that counter and states it in the run record.

## Consequences

- The transport is the one module that opens a serial port on the host, so the codec, the flasher, and the sweep stay testable with no port.
- The host and the image agree on 115200 baud through an ESP-IDF default that neither side states. Pinning `CONFIG_ESP_CONSOLE_UART_BAUDRATE` in `sdkconfig.defaults` makes that agreement explicit, and this record does not pin it.
- The `go` timeout of a default broadcast pass is about 55 s, from $2000 \times 12.58$ ms $\times 2 + 5$ s. The unicast pass of the same cell is about 106 s.
- An unreachable node costs 2 s at `hello` rather than a pass timeout.
- $k$, $m$, and the short timeout carry no source. The first bench run measures the margin between a pass and its timeout, and a later record replaces each value with a `[measured]` figure.
- A pass that exceeds its timeout stops the run after one retry, and that retry sends $N$ frames again.
- A `hello` banner during a run costs the cell, because a reset node holds no role and no cell. The host applies `role` and `cell` again before it reruns that cell.
- A host line longer than 512 bytes draws no reply, so the codec enforces the limit before the transport writes a line.
- `stats` must read `rejected_lines` for a run record to separate a rejected line from a lost line, so the suppression of Rule 8.9 on `s_rejected_line_count` is removed when `stats` lands.
- The settle time between a `go` reply and a `stats` command stays outside this record. The orchestrator states it.
- A change to the short timeout, to $a_{max}$, or to the retry budget needs a new record, because each one changes how a run ends.
- Watch a cell of the smallest payload. Its airtime falls far below its timeout, so a stall in that cell surfaces as a long wait rather than a fast failure.
