"""The control line transport of the host.

Owns the serial port of one node, writes a command line, and reads the reply
lines of that command. The codec in `bolis.protocol` holds text only and reads
no clock, so this module holds the port, the clock, and the reply timeout
(record 2026-11-12-serial-transport-reply-timeouts.md).

A node writes its application log to the same serial line as the control
plane, so the reader discards every line that the control prefix does not
start (thinkbook section 7).

Two timeouts apply. Every command other than `go` carries the short timeout,
and the host retries such a command once, with the next sequence number. `go`
carries a liveness timeout that restarts on every reply of its pass, so it
measures silence rather than the duration of a pass. The host never retries
`go`, because a retry sends the frames of a pass into a cell whose counters
already moved.
"""

import time
from collections.abc import Callable, Mapping
from typing import Any, Final, Protocol

import serial  # type: ignore[import-untyped]

from bolis import BolisError
from bolis.protocol import (
    BolisProtocolError,
    Reply,
    decode_reply,
    encode_command,
    is_control_line,
    raise_for_reply,
)

# The rate of the ESP-IDF console, in bits per second. The bench example does
# not override the default, so a node and the host agree on this value.
BAUD: Final = 115200

# The reply timeout of every command other than go, in seconds.
SHORT_TIMEOUT_S: Final = 2.0

# The liveness timeout of a go command, in seconds. It restarts on every reply
# of the pass, so it measures silence and not the length of a pass.
GO_LIVENESS_TIMEOUT_S: Final = 3.0

# One first attempt and one retry. The host cannot separate a lost line from a
# line that a node rejected, and an identical retry reproduces a rejection.
ATTEMPTS: Final = 2

# The command that reports its progress while it runs.
GO_COMMAND: Final = "go"

# The key of a go reply that states whether the pass ended.
_DONE_KEY: Final = "done"

# The reply that a node writes when it starts, without a command.
_BANNER_REPLY: Final = "hello"

_LINE_ENDING: Final = "\n"
_LINE_ENDING_BYTES: Final = b"\n"

# A reader of a monotonic clock, in seconds. The transport takes one so a test
# case drives every timeout with no wall clock.
Clock = Callable[[], float]

# A handler that one progress reply of a pass reaches.
ProgressHandler = Callable[[Reply], None]


class BolisTimeoutError(BolisError):
    """Raised when a command draws no reply inside its retry budget.

    The run stops and the host keeps the partial record (thinkbook section
    11).

    Attributes:
        command: The command name that drew no reply.
        seq: The sequence number of the last attempt.
        timeout_s: The reply timeout of one attempt, in seconds.
        attempts: The number of attempts that drew no reply.
    """

    def __init__(self, command: str, seq: int, timeout_s: float, attempts: int) -> None:
        """Builds the error from the command that drew no reply.

        Args:
            command: The command name that drew no reply.
            seq: The sequence number of the last attempt.
            timeout_s: The reply timeout of one attempt, in seconds.
            attempts: The number of attempts that drew no reply.
        """
        super().__init__(
            f"the node answered no {command!r} in {attempts} attempts, "
            f"each of {timeout_s} s."
        )
        self.command = command
        self.seq = seq
        self.timeout_s = timeout_s
        self.attempts = attempts


class BolisNodeResetError(BolisError):
    """Raised when a node states that it started while a command is outstanding.

    The cell is invalid, and the host runs it again once (thinkbook section
    11). A node that reset holds no role and no cell, so the host applies both
    again before that rerun.

    Attributes:
        seq: The sequence number of the outstanding command.
    """

    def __init__(self, seq: int) -> None:
        """Builds the error from the command that the reset interrupted.

        Args:
            seq: The sequence number of the outstanding command.
        """
        super().__init__(
            f"the node started again while the command with sequence number "
            f"{seq} was outstanding."
        )
        self.seq = seq


class BolisPassSilentError(BolisError):
    """Raised when a pass stops reporting before it states that it is done.

    The cell is invalid, and the host runs it again once. The host does not
    retry the `go` command, because a retry sends the frames of the pass into
    a cell whose counters already moved.

    Attributes:
        seq: The sequence number of the go command.
        timeout_s: The liveness timeout, in seconds.
        frames_sent: The frames that the last progress reply stated, or None
            when no progress reply arrived.
    """

    def __init__(self, seq: int, timeout_s: float, frames_sent: int | None) -> None:
        """Builds the error from the pass that fell silent.

        Args:
            seq: The sequence number of the go command.
            timeout_s: The liveness timeout, in seconds.
            frames_sent: The frames that the last progress reply stated, or
                None when no progress reply arrived.
        """
        if frames_sent is None:
            reached = "no progress reply"
        else:
            reached = f"{frames_sent} frames"
        super().__init__(
            f"the pass with sequence number {seq} wrote nothing for "
            f"{timeout_s} s, after {reached}."
        )
        self.seq = seq
        self.timeout_s = timeout_s
        self.frames_sent = frames_sent


class Port(Protocol):
    """The line reader and writer that the transport drives.

    The transport states this interface so a test case drives it with no
    serial port and with no node.
    """

    def read_line(self, timeout_s: float) -> str:
        """Returns one line, or the empty text when the timeout passes."""
        ...

    def write(self, text: str) -> None:
        """Writes one encoded line, which already carries its line ending."""
        ...

    def close(self) -> None:
        """Releases the port."""
        ...


class RawSerial(Protocol):
    """The pyserial entry points that `SerialPort` calls.

    `SerialPort` states this interface so a test case exercises the line
    buffering with no serial port.
    """

    timeout: float | None

    def read_until(self, expected: bytes) -> bytes:
        """Reads until the expected bytes arrive or the timeout passes."""
        ...

    def write(self, data: bytes) -> int:
        """Writes the bytes and returns the count that it wrote."""
        ...

    def flush(self) -> None:
        """Waits until every written byte leaves the buffer."""
        ...

    def close(self) -> None:
        """Releases the port."""
        ...


class SerialPort:
    """Reads and writes whole lines on one serial port.

    A read returns one line at a time. The reader holds the bytes that follow
    a line ending, so a chunk that carries part of the next line stays for the
    next read rather than reaching a caller in pieces.
    """

    def __init__(self, raw: RawSerial, clock: Clock = time.monotonic) -> None:
        """Wraps one open serial port.

        Args:
            raw: The open port.
            clock: A reader of a monotonic clock, in seconds.
        """
        self._raw = raw
        self._clock = clock
        self._buffer = ""

    def read_line(self, timeout_s: float) -> str:
        """Returns one line, with its line ending.

        Args:
            timeout_s: The time to wait for a complete line, in seconds.

        Returns:
            One line with its line ending, or the empty text when the timeout
            passes before a line ending arrives.
        """
        deadline = self._clock() + timeout_s
        while True:
            line = self._take_line()
            if line:
                return line
            remaining = deadline - self._clock()
            if remaining <= 0.0:
                return ""
            self._raw.timeout = remaining
            chunk = self._raw.read_until(_LINE_ENDING_BYTES)
            if chunk:
                self._buffer += chunk.decode("ascii", errors="replace")

    def write(self, text: str) -> None:
        """Writes one encoded line.

        `encode_command` returns a line that carries its line ending, so this
        method writes the text as it stands.

        Args:
            text: The line to write.
        """
        self._raw.write(text.encode("ascii"))
        self._raw.flush()

    def close(self) -> None:
        """Releases the port."""
        self._raw.close()

    def _take_line(self) -> str:
        """Removes the first complete line from the buffer and returns it.

        Returns:
            One line with its line ending, or the empty text when the buffer
            holds no line ending.
        """
        index = self._buffer.find(_LINE_ENDING)
        if index < 0:
            return ""
        line = self._buffer[: index + 1]
        self._buffer = self._buffer[index + 1 :]
        return line


def open_serial_port(port: str, baud: int = BAUD) -> SerialPort:
    """Opens one local serial port at the console rate.

    The port carries eight data bits, no parity, one stop bit, and no flow
    control.

    Args:
        port: The serial port of the node, such as /dev/ttyUSB0.
        baud: The rate, in bits per second.

    Returns:
        The open port.

    Raises:
        BolisError: The port names a network address rather than a local
            device.
    """
    # bolis.flasher imports esptool, which costs more to import than the rest
    # of the package. The check loads here, so a caller that holds a port
    # already pays nothing for it.
    from bolis.flasher import validate_local_port  # noqa: PLC0415

    validate_local_port(port)
    raw = serial.Serial(
        port=port,
        baudrate=baud,
        bytesize=serial.EIGHTBITS,
        parity=serial.PARITY_NONE,
        stopbits=serial.STOPBITS_ONE,
        xonxoff=False,
        rtscts=False,
        dsrdtr=False,
        timeout=0.0,
    )
    return SerialPort(raw)


class Transport:
    """Sends one command to a node and reads the replies of that command.

    One transport owns one port, so a pair of nodes takes two of them. The
    transport raises its sequence number for each command, and it discards
    every reply whose sequence number does not match the outstanding command,
    so a late reply to an earlier attempt changes no state.
    """

    def __init__(
        self,
        port: Port,
        clock: Clock = time.monotonic,
        short_timeout_s: float = SHORT_TIMEOUT_S,
        liveness_timeout_s: float = GO_LIVENESS_TIMEOUT_S,
    ) -> None:
        """Binds the transport to one open port.

        Args:
            port: The line reader and writer of one node.
            clock: A reader of a monotonic clock, in seconds.
            short_timeout_s: The reply timeout of every command other than go,
                in seconds.
            liveness_timeout_s: The timeout between two replies of a pass, in
                seconds.
        """
        self._port = port
        self._clock = clock
        self._short_timeout_s = short_timeout_s
        self._liveness_timeout_s = liveness_timeout_s
        self._next_seq_value = 0
        self._highest_seq = -1

    def command(self, name: str, fields: Mapping[str, Any] | None = None) -> Reply:
        """Sends one command and returns the reply that the node wrote.

        The host retries the command once when the first attempt draws no
        reply. The retry carries the next sequence number, so a late reply to
        the first attempt stays separable from the reply to the retry.

        Args:
            name: The command name, which is any command other than go.
            fields: The arguments of the command, by key, or None for a
                command that takes none.

        Returns:
            The reply of the node.

        Raises:
            ValueError: The name is the pass command, which `run_pass` sends.
            BolisTimeoutError: Neither attempt drew a reply.
            BolisNodeResetError: The node started again while the command was
                outstanding.
            BolisNodeError: The node answered with ok set to false.
            BolisProtocolError: A line did not meet the wire contract.
        """
        if name == GO_COMMAND:
            raise ValueError(f"{name!r} reports its progress, so run_pass sends it.")

        seq = 0
        for _attempt in range(ATTEMPTS):
            seq = self._send(name, fields)
            reply = self._read_reply(seq, self._short_timeout_s)
            if reply is not None:
                return raise_for_reply(reply)
        raise BolisTimeoutError(name, seq, self._short_timeout_s, ATTEMPTS)

    def run_pass(
        self,
        fields: Mapping[str, Any],
        on_progress: ProgressHandler | None = None,
    ) -> Reply:
        """Sends one go command and reads the replies until the pass ends.

        A sender writes a reply during the pass, carrying `done` set to false,
        and one reply at the end, carrying `done` set to true. The liveness
        timeout restarts on every reply of the pass.

        Args:
            fields: The arguments of the go command, by key.
            on_progress: A handler that each progress reply reaches, or None.

        Returns:
            The reply that carries `done` set to true.

        Raises:
            BolisPassSilentError: The pass wrote nothing for the liveness
                timeout, before it stated that it was done.
            BolisNodeResetError: The node started again during the pass.
            BolisNodeError: The node answered with ok set to false.
            BolisProtocolError: A line did not meet the wire contract, or a
                reply stated a `done` value that is not a boolean.
        """
        seq = self._send(GO_COMMAND, fields)
        frames_sent: int | None = None

        while True:
            reply = self._read_reply(seq, self._liveness_timeout_s)
            if reply is None:
                raise BolisPassSilentError(seq, self._liveness_timeout_s, frames_sent)
            raise_for_reply(reply)
            if _pass_is_done(reply):
                return reply
            frames_sent = _frames_sent(reply)
            if on_progress is not None:
                on_progress(reply)

    def close(self) -> None:
        """Releases the port of this transport."""
        self._port.close()

    def _send(self, name: str, fields: Mapping[str, Any] | None) -> int:
        """Writes one command and returns the sequence number it carried.

        Args:
            name: The command name.
            fields: The arguments of the command, by key, or None.

        Returns:
            The sequence number of the command.
        """
        seq = self._next_seq()
        self._port.write(encode_command(name, seq, fields))
        return seq

    def _next_seq(self) -> int:
        """Returns the next sequence number and records that the host sent it.

        Returns:
            The sequence number, which rises by one for each command.
        """
        seq = self._next_seq_value
        self._next_seq_value += 1
        self._highest_seq = seq
        return seq

    def _read_reply(self, seq: int, timeout_s: float) -> Reply | None:
        """Reads until the reply of one command arrives or the timeout passes.

        The reader discards a line that carries no control prefix, because the
        application log shares the serial line. It discards a reply whose
        sequence number does not match the outstanding command, because such a
        reply answers an earlier attempt.

        Args:
            seq: The sequence number of the outstanding command.
            timeout_s: The time to wait, in seconds.

        Returns:
            The reply of the command, or None when the timeout passes.

        Raises:
            BolisNodeResetError: A node wrote a hello reply that the host did
                not ask for.
            BolisProtocolError: A control line did not meet the wire contract.
        """
        deadline = self._clock() + timeout_s
        while True:
            remaining = deadline - self._clock()
            if remaining <= 0.0:
                return None
            line = self._port.read_line(remaining)
            if not line:
                return None
            if not is_control_line(line):
                continue
            reply = decode_reply(line)
            if reply.reply == _BANNER_REPLY and reply.seq > self._highest_seq:
                raise BolisNodeResetError(seq)
            if reply.seq == seq:
                return reply


def _pass_is_done(reply: Reply) -> bool:
    """Reports whether a go reply states that the pass ended.

    Args:
        reply: One reply of a go command.

    Returns:
        The value of the done key.

    Raises:
        BolisProtocolError: The reply states no done key, or states one that
            is not a boolean.
    """
    value = reply.fields.get(_DONE_KEY)
    if not isinstance(value, bool):
        raise BolisProtocolError(
            f"the go reply states {_DONE_KEY}={value!r}, which is not a boolean."
        )
    return value


def _frames_sent(reply: Reply) -> int | None:
    """Returns the frame count that a progress reply states.

    The count reaches the error of a silent pass, so a run record names how
    far the pass reached. A reply that states no count returns None rather
    than stopping the pass, because the count carries no decision.

    Args:
        reply: One progress reply of a go command.

    Returns:
        The frames whose send callback returned, or None when the reply states
        no count.
    """
    value = reply.fields.get("frames_sent")
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value
