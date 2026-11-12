"""Tests for the control line transport.

Every case runs with no serial port and with no node. The transport takes a
port and a clock, so a case drives a timeout without waiting for one.
"""

import json

import pytest

from bolis import BolisError
from bolis.protocol import (
    LINE_PREFIX,
    PROTO_VERSION,
    BolisNodeError,
    BolisProtocolError,
    Reply,
)
from bolis.transport import (
    ATTEMPTS,
    GO_LIVENESS_TIMEOUT_S,
    SHORT_TIMEOUT_S,
    BolisNodeResetError,
    BolisPassSilentError,
    BolisPortError,
    BolisTimeoutError,
    SerialPort,
    Transport,
    open_serial_port,
)

# A line that a port returns when it reads nothing before its timeout.
SILENCE = ""

# The frames of one pass (thinkbook section 8).
FRAMES_PER_PASS = 2000

# The frames that one progress reply of a stalled pass states.
PROGRESS_FRAMES = 700


def reply_line(name: str, seq: int, ok: bool = True, **fields: object) -> str:
    """Builds one node reply line.

    Args:
        name: The command name that the reply answers.
        seq: The sequence number that the node copied.
        ok: Whether the node applied the command.
        **fields: Every key that the envelope does not own.

    Returns:
        The control line, with its prefix and its line ending.
    """
    obj: dict[str, object] = {
        "proto": PROTO_VERSION,
        "reply": name,
        "seq": seq,
        "ok": ok,
    }
    obj.update(fields)
    return LINE_PREFIX + json.dumps(obj, separators=(",", ":")) + "\n"


def command_seq(line: str) -> int:
    """Returns the sequence number of one encoded command line.

    Args:
        line: One command line that the transport wrote.

    Returns:
        The sequence number that the line carries.
    """
    obj = json.loads(line[len(LINE_PREFIX) :])
    seq = obj["seq"]
    assert isinstance(seq, int)
    return seq


class StepClock:
    """A monotonic clock that advances by one step on every read."""

    def __init__(self, step_s: float = 0.0) -> None:
        """Starts the clock at zero.

        Args:
            step_s: The seconds that each read adds.
        """
        self.now_s = 0.0
        self._step_s = step_s

    def __call__(self) -> float:
        """Returns the current time and advances the clock by one step."""
        value = self.now_s
        self.now_s += self._step_s
        return value


class FakePort:
    """A port that returns a scripted list of lines."""

    def __init__(self, lines: list[str]) -> None:
        """Scripts the lines that the reader returns, in order.

        Args:
            lines: One entry per read. An entry of SILENCE models a read that
                returned nothing before its timeout.
        """
        self._lines = list(lines)
        self.written: list[str] = []
        self.timeouts_s: list[float] = []
        self.closed = False

    def read_line(self, timeout_s: float) -> str:
        """Returns the next scripted line, or SILENCE when the script ends."""
        self.timeouts_s.append(timeout_s)
        if not self._lines:
            return SILENCE
        return self._lines.pop(0)

    def write(self, text: str) -> None:
        """Records one written line."""
        self.written.append(text)

    def close(self) -> None:
        """Records that the caller released the port."""
        self.closed = True


class FakeRawSerial:
    """A serial port that returns a scripted list of byte chunks."""

    def __init__(self, chunks: list[bytes]) -> None:
        """Scripts the chunks that each read returns, in order.

        Args:
            chunks: One entry per read.
        """
        self._chunks = list(chunks)
        self.timeout: float | None = None
        self.written = b""
        self.flushed = False
        self.closed = False

    def read_until(self, expected: bytes) -> bytes:
        """Returns the next scripted chunk, or no bytes when the script ends."""
        assert expected == b"\n"
        if not self._chunks:
            return b""
        return self._chunks.pop(0)

    def write(self, data: bytes) -> int:
        """Records the written bytes and returns their count."""
        self.written += data
        return len(data)

    def flush(self) -> None:
        """Records that the caller flushed the port."""
        self.flushed = True

    def close(self) -> None:
        """Records that the caller released the port."""
        self.closed = True


def make_transport(lines: list[str], step_s: float = 0.0) -> tuple[Transport, FakePort]:
    """Builds a transport over a scripted port.

    Args:
        lines: One entry per read of the port.
        step_s: The seconds that each clock read adds.

    Returns:
        The transport and the port it drives.
    """
    port = FakePort(lines)
    return Transport(port, clock=StepClock(step_s)), port


def test_command_returns_the_reply_of_its_sequence_number() -> None:
    """A command returns the reply that carries its own sequence number."""
    transport, port = make_transport([reply_line("hello", 0)])

    reply = transport.command("hello")

    assert isinstance(reply, Reply)
    assert reply.reply == "hello"
    assert reply.seq == 0
    assert command_seq(port.written[0]) == 0


def test_command_discards_a_line_that_carries_no_control_prefix() -> None:
    """A log line on the same serial line reaches no caller."""
    log = "I (123) bolis: The control task reads the console.\n"
    transport, _ = make_transport([log, reply_line("hello", 0)])

    reply = transport.command("hello")

    assert reply.reply == "hello"


def test_command_discards_a_reply_of_another_sequence_number() -> None:
    """A late reply to an earlier attempt changes no state."""
    stale = reply_line("cell", 99)
    transport, _ = make_transport([stale, reply_line("hello", 0)])

    reply = transport.command("hello")

    assert reply.seq == 0


def test_command_retries_once_with_the_next_sequence_number() -> None:
    """A retry carries the next sequence number, not the one that fell silent."""
    transport, port = make_transport([SILENCE, reply_line("cell", 1)])

    reply = transport.command("cell", {"cell_id": 3})

    assert reply.seq == 1
    assert [command_seq(line) for line in port.written] == [0, 1]


def test_command_raises_when_every_attempt_falls_silent() -> None:
    """The run stops when neither attempt draws a reply."""
    transport, port = make_transport([SILENCE, SILENCE])

    with pytest.raises(BolisTimeoutError) as caught:
        transport.command("cell")

    assert caught.value.command == "cell"
    assert caught.value.attempts == ATTEMPTS
    assert caught.value.timeout_s == SHORT_TIMEOUT_S
    assert len(port.written) == ATTEMPTS


def test_command_uses_the_short_timeout() -> None:
    """Every command other than go waits for the short timeout."""
    transport, port = make_transport([reply_line("hello", 0)])

    transport.command("hello")

    assert port.timeouts_s == [SHORT_TIMEOUT_S]


def test_command_raises_when_the_node_states_an_error() -> None:
    """A node that answers with ok false stops the command without a retry."""
    line = reply_line("stats", 0, ok=False, err="ESP_ERR_NOT_SUPPORTED")
    transport, port = make_transport([line])

    with pytest.raises(BolisNodeError) as caught:
        transport.command("stats")

    assert caught.value.err == "ESP_ERR_NOT_SUPPORTED"
    assert len(port.written) == 1


def test_command_refuses_the_pass_command() -> None:
    """The go command reports its progress, so run_pass sends it."""
    transport, _ = make_transport([])

    with pytest.raises(ValueError, match="run_pass"):
        transport.command("go")


def test_command_raises_when_a_node_states_that_it_started() -> None:
    """A hello reply that the host did not ask for names a node that reset."""
    banner = reply_line("hello", 7)
    transport, _ = make_transport([banner])

    with pytest.raises(BolisNodeResetError) as caught:
        transport.command("cell")

    assert caught.value.seq == 0


def test_a_solicited_hello_reply_is_not_a_reset() -> None:
    """A hello reply of the outstanding command states no reset."""
    transport, _ = make_transport([reply_line("hello", 0)])

    assert transport.command("hello").seq == 0


def test_run_pass_returns_the_reply_that_states_done() -> None:
    """A pass ends on the reply that carries done set to true."""
    lines = [
        reply_line("go", 0, cell_id=3, done=False, frames_sent=500),
        reply_line("go", 0, cell_id=3, done=True, frames_sent=FRAMES_PER_PASS),
    ]
    transport, _ = make_transport(lines)

    fields = {"cell_id": 3, "pass": "broadcast", "frames": FRAMES_PER_PASS}
    reply = transport.run_pass(fields)

    assert reply.fields["done"] is True
    assert reply.fields["frames_sent"] == FRAMES_PER_PASS


def test_run_pass_reports_every_progress_reply() -> None:
    """Each reply that carries done false reaches the handler."""
    lines = [
        reply_line("go", 0, done=False, frames_sent=500),
        reply_line("go", 0, done=False, frames_sent=1500),
        reply_line("go", 0, done=True, frames_sent=FRAMES_PER_PASS),
    ]
    transport, _ = make_transport(lines)
    seen: list[int] = []

    def record(reply: Reply) -> None:
        seen.append(reply.fields["frames_sent"])

    transport.run_pass({"cell_id": 3}, on_progress=record)

    assert seen == [500, 1500]


def test_run_pass_uses_the_liveness_timeout_for_every_reply() -> None:
    """Each reply of a pass waits for the whole liveness timeout.

    The clock does not advance here, so the time that the reader passes to the
    port states the timeout itself rather than the part of it that remains.
    """
    lines = [reply_line("go", 0, done=False, frames_sent=n) for n in (400, 800, 1200)]
    lines.append(reply_line("go", 0, done=True, frames_sent=FRAMES_PER_PASS))
    transport, port = make_transport(lines)

    transport.run_pass({"cell_id": 3})

    assert port.timeouts_s == [GO_LIVENESS_TIMEOUT_S] * len(lines)


def test_a_read_waits_only_for_the_time_that_remains() -> None:
    """Time that a read already spent comes off the timeout of the next read."""
    transport, port = make_transport([reply_line("hello", 0)], step_s=1.0)

    transport.command("hello")

    assert port.timeouts_s == [SHORT_TIMEOUT_S - 1.0]


def test_run_pass_outlives_a_pass_longer_than_one_timeout() -> None:
    """A pass of many replies runs past the liveness timeout without a failure."""
    counts = range(0, FRAMES_PER_PASS, 100)
    lines = [reply_line("go", 0, done=False, frames_sent=n) for n in counts]
    lines.append(reply_line("go", 0, done=True, frames_sent=FRAMES_PER_PASS))
    clock = StepClock(step_s=1.0)
    port = FakePort(lines)
    transport = Transport(port, clock=clock)

    reply = transport.run_pass({"cell_id": 3})

    assert reply.fields["done"] is True
    assert clock.now_s > GO_LIVENESS_TIMEOUT_S


def test_run_pass_raises_when_the_pass_falls_silent() -> None:
    """A pass that stops reporting invalidates its cell."""
    lines = [reply_line("go", 0, done=False, frames_sent=PROGRESS_FRAMES), SILENCE]
    transport, port = make_transport(lines)

    with pytest.raises(BolisPassSilentError) as caught:
        transport.run_pass({"cell_id": 3})

    assert caught.value.frames_sent == PROGRESS_FRAMES
    assert caught.value.timeout_s == GO_LIVENESS_TIMEOUT_S
    assert len(port.written) == 1


def test_run_pass_never_retries_the_go_command() -> None:
    """A retry would send the frames of a pass a second time."""
    transport, port = make_transport([SILENCE])

    with pytest.raises(BolisPassSilentError) as caught:
        transport.run_pass({"cell_id": 3})

    assert caught.value.frames_sent is None
    assert len(port.written) == 1


def test_run_pass_raises_when_a_reply_states_no_done_key() -> None:
    """A go reply without a boolean done key does not meet the contract."""
    transport, _ = make_transport([reply_line("go", 0, cell_id=3)])

    with pytest.raises(BolisProtocolError, match="done"):
        transport.run_pass({"cell_id": 3})


def test_transport_closes_its_port() -> None:
    """Closing the transport releases the port."""
    transport, port = make_transport([])

    transport.close()

    assert port.closed


def test_serial_port_joins_chunks_into_one_line() -> None:
    """A line that arrives in pieces reaches the caller once it is whole."""
    raw = FakeRawSerial([b'@bol {"a":1}', b"\n"])
    port = SerialPort(raw, clock=StepClock())

    assert port.read_line(1.0) == '@bol {"a":1}\n'


def test_serial_port_holds_the_bytes_after_a_line_ending() -> None:
    """A chunk that carries the next line keeps it for the next read."""
    raw = FakeRawSerial([b'@bol {"a":1}\n@bol {"b":2}\n'])
    port = SerialPort(raw, clock=StepClock())

    assert port.read_line(1.0) == '@bol {"a":1}\n'
    assert port.read_line(1.0) == '@bol {"b":2}\n'


def test_serial_port_returns_no_line_when_the_timeout_passes() -> None:
    """A read that finds no line ending returns the empty text."""
    raw = FakeRawSerial([b"partial"])
    port = SerialPort(raw, clock=StepClock(step_s=1.0))

    assert port.read_line(1.0) == ""


def test_serial_port_writes_the_line_as_it_stands() -> None:
    """A command line already carries its line ending."""
    raw = FakeRawSerial([])
    port = SerialPort(raw, clock=StepClock())

    port.write('@bol {"a":1}\n')

    assert raw.written == b'@bol {"a":1}\n'
    assert raw.flushed


def test_open_serial_port_names_the_port_that_did_not_open() -> None:
    """A node that is not attached draws a message that names the port."""
    with pytest.raises(BolisPortError) as caught:
        open_serial_port("/dev/ttyUSB-absent")

    assert caught.value.port == "/dev/ttyUSB-absent"
    assert "attached" in str(caught.value)


def test_open_serial_port_refuses_a_url() -> None:
    """A port that pyserial would read as a URL never opens."""
    with pytest.raises(BolisError, match="URL"):
        open_serial_port("rfc2217://10.0.0.5:4000")


def test_serial_port_closes_the_raw_port() -> None:
    """Closing the port releases the serial device."""
    raw = FakeRawSerial([])
    port = SerialPort(raw, clock=StepClock())

    port.close()

    assert raw.closed
