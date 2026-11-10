"""The control line codec (decision 2026-10-01-control-line-wire-format.md).

Encodes one host command and decodes one node reply. Every control line
carries the prefix "@bol ", one JSON object, and a newline, in both
directions. The console of a node carries the application log on the same
serial line, so a reader ignores every line that the prefix does not start
(thinkbook section 7).

This module holds text only. It opens no serial port and it reads no clock,
so the transport that owns the port enforces the read timeout. It attaches no
origin label: a node states no label, and the host attaches one when it
writes the run record.

The module names the keys of the envelope and the keys of the hello reply,
which the record states. It names no key of the role, cell, go, or stats
command, because the record states none. A key that this module invented
would fix the wire contract by accident, and a change to any key raises
`proto` and needs a new record.
"""

import json
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Final

from bolis import BolisError

# Every control line carries this prefix, in both directions.
LINE_PREFIX: Final = "@bol "

# A control line holds at most 512 bytes, including the prefix and the
# newline. A node rejects a longer line and counts it.
LINE_MAX_BYTES: Final = 512

# The version of this wire contract. The first version is 1.
PROTO_VERSION: Final = 1

# The five commands of the contract. The firmware answers hello and names the
# other four as unsupported until it carries them.
COMMANDS: Final = ("hello", "role", "cell", "go", "stats")

# The host raises seq for each command and the node copies it into the reply.
# The node holds it in a uint32_t.
SEQ_MIN: Final = 0
SEQ_MAX: Final = 0xFFFFFFFF

# The keys that the envelope owns. A command field cannot reuse one.
_ENVELOPE_KEYS: Final = frozenset({"proto", "cmd", "seq", "reply", "ok", "err"})

# The hello reply states the ELF SHA-256 as 64 lowercase hexadecimal
# characters, encoded from the 32 bytes of the application description.
ELF_SHA256_TEXT_LENGTH: Final = 64
_HEX_LOWERCASE: Final = frozenset("0123456789abcdef")

# The two firmware paths that a node reports, from the Kconfig option that
# marks a release image.
FIRMWARE_PATHS: Final = ("prebuilt", "source")

# The two states that a node reports for its Bluetooth controller.
BLUETOOTH_STATES: Final = ("enabled", "disabled")


class BolisProtocolError(BolisError):
    """Raised when a control line does not meet the wire contract."""


class BolisNodeError(BolisError):
    """Raised when a node answers a command with ok set to false.

    Attributes:
        reply: The command name that the failed reply answers.
        seq: The sequence number of the command that failed.
        err: The name of the ESP-IDF error code that the node stated, such as
            ESP_ERR_NOT_SUPPORTED.
    """

    def __init__(self, reply: str, seq: int, err: str) -> None:
        """Builds the error from the three fields of a failed reply.

        Args:
            reply: The command name that the failed reply answers.
            seq: The sequence number of the command, SEQ_MIN to SEQ_MAX.
            err: The name of the ESP-IDF error code that the node stated.
        """
        super().__init__(f"the node answered {reply!r} with {err}.")
        self.reply = reply
        self.seq = seq
        self.err = err


@dataclass(frozen=True, repr=False)
class Reply:
    """One decoded node line.

    The text form states the envelope alone. A role reply carries the MAC
    address of the receiver (thinkbook section 7), and the host holds a MAC
    address in memory only, so the other fields stay out of any text that
    reaches a log.

    Attributes:
        reply: The command name that this line answers.
        seq: The sequence number that the host sent and the node copied.
        proto: The contract version that the node stated.
        ok: Whether the node applied the command.
        err: The name of the ESP-IDF error code when ok is false, and None
            when ok is true.
        fields: Every key of the object that the envelope does not own, as a
            read-only mapping. The dataclass is frozen, which stops a rebind
            of this attribute and not a write into the mapping it holds, so
            decode_reply wraps the mapping as well.
    """

    reply: str
    seq: int
    proto: int
    ok: bool
    err: str | None
    fields: Mapping[str, Any]

    def __repr__(self) -> str:
        """Returns the envelope of the reply, without the other fields."""
        return (
            f"Reply(reply={self.reply!r}, seq={self.seq}, "
            f"proto={self.proto}, ok={self.ok}, err={self.err!r})"
        )


@dataclass(frozen=True)
class Hello:
    """The test condition that a node states in its hello reply.

    Attributes:
        chip: The chip model, such as esp32.
        chip_revision: The chip revision that the node read.
        idf_version: The ESP-IDF version that built the image.
        espnow_version: The ESP-NOW version that the node reports.
        payload_limit_bytes: The packet payload limit L, in bytes.
        bolis_version: The Bolis version of the image.
        firmware_path: One of FIRMWARE_PATHS.
        elf_sha256: The ELF SHA-256, as 64 lowercase hexadecimal characters.
        bluetooth_controller: One of BLUETOOTH_STATES.
    """

    chip: str
    chip_revision: int
    idf_version: str
    espnow_version: int
    payload_limit_bytes: int
    bolis_version: str
    firmware_path: str
    elf_sha256: str
    bluetooth_controller: str


def _require_key(obj: Mapping[str, Any], key: str) -> Any:  # noqa: ANN401
    """Returns the value of a key, or raises when the object omits it.

    Args:
        obj: The decoded JSON object of one control line.
        key: The key to read.

    Returns:
        The value, which the caller narrows at once.

    Raises:
        BolisProtocolError: The object carries no such key.
    """
    if key not in obj:
        raise BolisProtocolError(f"the control line carries no key {key!r}.")
    return obj[key]


def _require_int(obj: Mapping[str, Any], key: str) -> int:
    """Reads one key as an integer.

    Args:
        obj: The decoded JSON object of one control line.
        key: The key to read.

    Returns:
        The integer value.

    Raises:
        BolisProtocolError: The key is absent, or its value is not an integer.
            JSON holds true and false as a kind of integer in Python, and this
            check rejects both.
    """
    value = _require_key(obj, key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise BolisProtocolError(f"the key {key!r} holds no integer.")
    return value


def _require_text(obj: Mapping[str, Any], key: str) -> str:
    """Reads one key as a non-empty text value.

    Args:
        obj: The decoded JSON object of one control line.
        key: The key to read.

    Returns:
        The text value.

    Raises:
        BolisProtocolError: The key is absent, or its value is not text, or
            the text is empty.
    """
    value = _require_key(obj, key)
    if not isinstance(value, str):
        raise BolisProtocolError(f"the key {key!r} holds no text.")
    if len(value) == 0:
        raise BolisProtocolError(f"the key {key!r} holds empty text.")
    return value


def _require_bool(obj: Mapping[str, Any], key: str) -> bool:
    """Reads one key as a boolean.

    Args:
        obj: The decoded JSON object of one control line.
        key: The key to read.

    Returns:
        The boolean value.

    Raises:
        BolisProtocolError: The key is absent, or its value is not a boolean.
    """
    value = _require_key(obj, key)
    if not isinstance(value, bool):
        raise BolisProtocolError(f"the key {key!r} holds no boolean.")
    return value


def _require_seq(seq: int) -> int:
    """Checks that a sequence number fits the range the node holds.

    Args:
        seq: The sequence number to check.

    Returns:
        The same sequence number, unchanged.

    Raises:
        BolisProtocolError: The value sits outside SEQ_MIN to SEQ_MAX.
    """
    if not (SEQ_MIN <= seq <= SEQ_MAX):
        raise BolisProtocolError(
            f"the sequence number is {seq}. A node holds {SEQ_MIN} to {SEQ_MAX}."
        )
    return seq


def _require_choice(value: str, allowed: tuple[str, ...], key: str) -> str:
    """Checks that a text value is one of the values the contract names.

    Args:
        value: The text value to check.
        allowed: The values that the contract names.
        key: The key that held the value, for the message.

    Returns:
        The same value, unchanged.

    Raises:
        BolisProtocolError: The value is not a member of allowed.
    """
    if value not in allowed:
        names = ", ".join(allowed)
        raise BolisProtocolError(
            f"the key {key!r} holds {value!r}. The contract names: {names}."
        )
    return value


def _strip_one_line_ending(line: str) -> str:
    """Removes one trailing line ending, and no more.

    A strip of every trailing newline would hide the extra bytes of a line
    that carries several, and the length check counts the line as it arrived.

    Args:
        line: One line, with or without its trailing line ending.

    Returns:
        The line without its last line ending. A line that carries none
        returns unchanged.
    """
    if line.endswith("\r\n"):
        return line[:-2]
    if line.endswith(("\n", "\r")):
        return line[:-1]
    return line


def is_control_line(line: str) -> bool:
    """Reports whether one console line carries a control line.

    A node writes the application log to the same serial line, so a reader
    calls this function before it decodes a line.

    Args:
        line: One line that the console produced, with or without its newline.

    Returns:
        True when the line starts with LINE_PREFIX.
    """
    return line.startswith(LINE_PREFIX)


def encode_command(name: str, seq: int, fields: Mapping[str, Any] | None = None) -> str:
    """Encodes one host command as a control line.

    Args:
        name: The command name, one of COMMANDS.
        seq: The sequence number, SEQ_MIN to SEQ_MAX. The host raises it for
            each command and the node copies it into the reply.
        fields: The arguments of the command, by key, or None for a command
            that takes none. A key that the envelope owns is rejected.

    Returns:
        The control line, with its prefix and its trailing newline.

    Raises:
        BolisProtocolError: The name is not a command of the contract, the
            sequence number sits outside its range, a field reuses a key that
            the envelope owns, a field holds a value that JSON cannot encode,
            or the encoded line exceeds LINE_MAX_BYTES.
    """
    if name not in COMMANDS:
        names = ", ".join(COMMANDS)
        raise BolisProtocolError(
            f"the command is {name!r}. The contract names: {names}."
        )
    _require_seq(seq)

    object_fields: dict[str, Any] = {"proto": PROTO_VERSION, "cmd": name, "seq": seq}
    for key, value in (fields or {}).items():
        if key in _ENVELOPE_KEYS:
            raise BolisProtocolError(
                f"the field {key!r} reuses a key that the envelope owns."
            )
        object_fields[key] = value

    try:
        text = json.dumps(object_fields, separators=(",", ":"), ensure_ascii=True)
    except (TypeError, ValueError) as error:
        raise BolisProtocolError(
            f"the fields of {name!r} hold a value that JSON cannot encode."
        ) from error

    line = f"{LINE_PREFIX}{text}\n"
    size_bytes = len(line.encode("utf-8"))
    if size_bytes > LINE_MAX_BYTES:
        raise BolisProtocolError(
            f"the line of {name!r} holds {size_bytes} bytes. A control line "
            f"holds at most {LINE_MAX_BYTES} bytes."
        )
    return line


def decode_reply(line: str) -> Reply:
    """Decodes one node line into its envelope and its other fields.

    Treats the line as untrusted. It checks the prefix, the length, the shape
    of the JSON object, and the type of every key that the envelope owns. A
    node that states a different contract version is refused here, because the
    host refuses a node whose proto differs from its own.

    The length check counts the line as it arrived, including its line ending.
    A line that carries no ending counts one byte for the newline it travelled
    with, so the limit means the same thing for a reader that strips the ending
    and a reader that keeps it.

    Args:
        line: One console line that is_control_line accepted, with or without
            its trailing line ending.

    Returns:
        The decoded reply. Its fields mapping is read-only.

    Raises:
        BolisProtocolError: The line misses the prefix, exceeds
            LINE_MAX_BYTES, holds no JSON object, omits a key of the envelope,
            holds a key of the envelope at the wrong type, states a contract
            version other than PROTO_VERSION, carries err while ok is true, or
            omits err while ok is false.
    """
    body = _strip_one_line_ending(line)
    # The prefix decides whether this is a control line at all, so it is the
    # first check. A long log line that reaches this function then names the
    # missing prefix rather than its byte count.
    if not is_control_line(body):
        raise BolisProtocolError(
            f"the line starts with no {LINE_PREFIX!r} prefix, so it is no control line."
        )

    # The contract counts the prefix and the newline inside the limit, so the
    # check counts the line as it arrived. A line that carries no ending still
    # travelled with one, which the check adds. A line that carries a carriage
    # return and a newline counts both of those bytes, because both crossed
    # the serial link.
    size_bytes = len(line.encode("utf-8"))
    if len(line) == len(body):
        size_bytes += 1
    if size_bytes > LINE_MAX_BYTES:
        raise BolisProtocolError(
            f"the control line holds {size_bytes} bytes. A control line holds "
            f"at most {LINE_MAX_BYTES} bytes."
        )

    text = body[len(LINE_PREFIX) :]
    try:
        decoded: Any = json.loads(text)
    except ValueError as error:
        raise BolisProtocolError("the control line holds no readable JSON.") from error
    if not isinstance(decoded, dict):
        raise BolisProtocolError("the control line holds no JSON object.")

    proto = _require_int(decoded, "proto")
    if proto != PROTO_VERSION:
        raise BolisProtocolError(
            f"the node states proto {proto}. This host speaks proto "
            f"{PROTO_VERSION}, so it refuses the node."
        )

    name = _require_text(decoded, "reply")
    seq = _require_seq(_require_int(decoded, "seq"))
    ok = _require_bool(decoded, "ok")

    err: str | None = None
    if ok:
        if "err" in decoded:
            raise BolisProtocolError(
                "the reply carries err while ok is true. A node states err "
                "only with ok set to false."
            )
    else:
        err = _require_text(decoded, "err")

    fields = {key: value for key, value in decoded.items() if key not in _ENVELOPE_KEYS}
    return Reply(
        reply=name,
        seq=seq,
        proto=proto,
        ok=ok,
        err=err,
        fields=MappingProxyType(fields),
    )


def raise_for_reply(reply: Reply) -> Reply:
    """Raises when a node reported a failure, and returns the reply otherwise.

    Args:
        reply: One decoded reply.

    Returns:
        The same reply, unchanged, when ok is true.

    Raises:
        BolisNodeError: The node set ok to false. The error carries the
            command name, the sequence number, and the ESP-IDF error code name.
    """
    if not reply.ok:
        # decode_reply rejects a failed reply that omits err, so err holds text
        # on this path.
        raise BolisNodeError(reply.reply, reply.seq, reply.err or "")
    return reply


def parse_hello(reply: Reply) -> Hello:
    """Reads the nine fields of a hello reply and checks each one.

    Args:
        reply: The decoded reply to a hello command.

    Returns:
        The test condition that the node stated.

    Raises:
        BolisProtocolError: The reply answers another command, a field is
            absent, a field holds the wrong type, the ELF SHA-256 is not 64
            lowercase hexadecimal characters, the payload limit is not above
            0, a count is negative, or the firmware path or the Bluetooth
            state is not a value that the contract names.
        BolisNodeError: The node set ok to false.
    """
    if reply.reply != "hello":
        raise BolisProtocolError(
            f"the reply answers {reply.reply!r}, and parse_hello reads a hello reply."
        )
    raise_for_reply(reply)

    fields = reply.fields
    chip_revision = _require_int(fields, "chip_revision")
    espnow_version = _require_int(fields, "espnow_version")
    payload_limit_bytes = _require_int(fields, "payload_limit_bytes")
    if chip_revision < 0:
        raise BolisProtocolError(
            f"the chip revision is {chip_revision}. A revision is 0 or greater."
        )
    if espnow_version < 0:
        raise BolisProtocolError(
            f"the ESP-NOW version is {espnow_version}. A version is 0 or greater."
        )
    if payload_limit_bytes <= 0:
        raise BolisProtocolError(
            f"the payload limit is {payload_limit_bytes} bytes. A limit is above 0."
        )

    elf_sha256 = _require_text(fields, "elf_sha256")
    if len(elf_sha256) != ELF_SHA256_TEXT_LENGTH:
        raise BolisProtocolError(
            f"the ELF SHA-256 holds {len(elf_sha256)} characters. The contract "
            f"states {ELF_SHA256_TEXT_LENGTH} lowercase hexadecimal characters."
        )
    if not set(elf_sha256) <= _HEX_LOWERCASE:
        raise BolisProtocolError(
            "the ELF SHA-256 holds a character that is no lowercase hexadecimal digit."
        )

    return Hello(
        chip=_require_text(fields, "chip"),
        chip_revision=chip_revision,
        idf_version=_require_text(fields, "idf_version"),
        espnow_version=espnow_version,
        payload_limit_bytes=payload_limit_bytes,
        bolis_version=_require_text(fields, "bolis_version"),
        firmware_path=_require_choice(
            _require_text(fields, "firmware_path"), FIRMWARE_PATHS, "firmware_path"
        ),
        elf_sha256=elf_sha256,
        bluetooth_controller=_require_choice(
            _require_text(fields, "bluetooth_controller"),
            BLUETOOTH_STATES,
            "bluetooth_controller",
        ),
    )


def require_same_firmware(sender: Hello, receiver: Hello) -> None:
    """Checks that two nodes run the same firmware image.

    Both nodes run the same image (decision
    2026-10-01-radio-ownership-and-prebuilt-firmware.md), and the host refuses
    a pair whose hello replies differ in firmware. The ELF SHA-256 names the
    image, so it decides the question: one hash fixes the Bolis version, the
    ESP-IDF version, and the firmware path together.

    Args:
        sender: The hello reply of the node that takes the sender role.
        receiver: The hello reply of the node that takes the receiver role.

    Raises:
        BolisProtocolError: The two ELF SHA-256 values differ.
    """
    if sender.elf_sha256 != receiver.elf_sha256:
        raise BolisProtocolError(
            "the two nodes run different firmware, so the run stops before the "
            f"first cell. One node reports ELF SHA-256 {sender.elf_sha256} and "
            f"the other reports {receiver.elf_sha256}."
        )
