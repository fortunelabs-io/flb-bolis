"""Tests for the control line codec."""

import json

import pytest

from bolis.protocol import (
    ELF_SHA256_TEXT_LENGTH,
    LINE_MAX_BYTES,
    LINE_PREFIX,
    PROTO_VERSION,
    SEQ_MAX,
    BolisNodeError,
    BolisProtocolError,
    Hello,
    decode_reply,
    encode_command,
    is_control_line,
    parse_hello,
    raise_for_reply,
    require_same_firmware,
)

# The fields of the reference hello reply. Each one carries a name, so an
# assertion states which field it checks.
HELLO_SEQ = 1
CHIP = "esp32"
CHIP_REVISION = 301
IDF_VERSION = "v5.5.4"
ESPNOW_VERSION = 2
PAYLOAD_LIMIT_BYTES = 1470
BOLIS_VERSION = "0.1.0"
FIRMWARE_PATH = "source"
BLUETOOTH_CONTROLLER = "disabled"

# Two hashes of the right shape: 64 lowercase hexadecimal characters each.
SHA256_TEXT = "ab" * 32
OTHER_SHA256_TEXT = "cd" * 32

# The sequence numbers and the one channel that single cases use.
CELL_SEQ = 7
CELL_CHANNEL = 6
ROLE_SEQ = 4
GO_SEQ = 9
MATCHED_SEQ = 42


def _hello_line(**overrides: object) -> str:
    """Builds a hello reply line in the compact form that the firmware writes.

    Args:
        overrides: Keys to add to the object, or to replace in it. A value of
            None removes the key.

    Returns:
        The control line, with its prefix and its trailing newline.
    """
    fields: dict[str, object] = {
        "proto": PROTO_VERSION,
        "reply": "hello",
        "seq": HELLO_SEQ,
        "ok": True,
        "chip": CHIP,
        "chip_revision": CHIP_REVISION,
        "idf_version": IDF_VERSION,
        "espnow_version": ESPNOW_VERSION,
        "payload_limit_bytes": PAYLOAD_LIMIT_BYTES,
        "bolis_version": BOLIS_VERSION,
        "firmware_path": FIRMWARE_PATH,
        "elf_sha256": SHA256_TEXT,
        "bluetooth_controller": BLUETOOTH_CONTROLLER,
    }
    fields.update(overrides)
    for key, value in list(fields.items()):
        if value is None:
            del fields[key]
    text = json.dumps(fields, separators=(",", ":"), ensure_ascii=True)
    return f"{LINE_PREFIX}{text}\n"


def _line_of_size(size_bytes: int) -> str:
    """Builds a readable reply line of exactly size_bytes, including the newline.

    Args:
        size_bytes: The total size of the line, in bytes, including the prefix
            and the newline.

    Returns:
        The control line, padded to that size.
    """
    head = (
        f'{LINE_PREFIX}{{"proto":{PROTO_VERSION},"reply":"hello",'
        f'"seq":{HELLO_SEQ},"ok":true,"pad":"'
    )
    tail = '"}'
    fill = size_bytes - 1 - len(head) - len(tail)
    return f"{head}{'x' * fill}{tail}\n"


def _hello() -> Hello:
    """Returns a Hello whose every field holds a valid value."""
    return parse_hello(decode_reply(_hello_line()))


def test_encode_command_writes_the_prefix_the_envelope_and_the_newline() -> None:
    """A command line carries the prefix, proto, cmd, seq, and one newline."""
    line = encode_command("hello", HELLO_SEQ)
    assert line.startswith(LINE_PREFIX)
    assert line.endswith("\n")
    assert line.count("\n") == 1
    decoded = json.loads(line[len(LINE_PREFIX) :])
    assert decoded == {"proto": PROTO_VERSION, "cmd": "hello", "seq": HELLO_SEQ}


def test_encode_command_carries_the_fields_of_the_command() -> None:
    """A field of a command reaches the object beside the envelope."""
    line = encode_command("cell", CELL_SEQ, {"channel": CELL_CHANNEL})
    decoded = json.loads(line[len(LINE_PREFIX) :])
    assert decoded["channel"] == CELL_CHANNEL
    assert decoded["cmd"] == "cell"
    assert decoded["seq"] == CELL_SEQ


def test_encode_command_rejects_a_command_outside_the_contract() -> None:
    """A command name that the contract does not name raises."""
    with pytest.raises(BolisProtocolError, match="reboot"):
        encode_command("reboot", HELLO_SEQ)


def test_encode_command_rejects_a_sequence_number_above_the_range() -> None:
    """A sequence number that a node cannot hold raises."""
    with pytest.raises(BolisProtocolError, match="sequence number"):
        encode_command("hello", SEQ_MAX + 1)


def test_encode_command_rejects_a_negative_sequence_number() -> None:
    """A negative sequence number raises."""
    with pytest.raises(BolisProtocolError, match="sequence number"):
        encode_command("hello", -1)


def test_encode_command_rejects_a_field_that_reuses_an_envelope_key() -> None:
    """A field named like an envelope key raises, because it would corrupt the line."""
    with pytest.raises(BolisProtocolError, match="seq"):
        encode_command("cell", HELLO_SEQ, {"seq": GO_SEQ})


def test_encode_command_rejects_a_line_above_the_limit() -> None:
    """A command whose fields exceed the line limit raises and names the size."""
    with pytest.raises(BolisProtocolError, match=str(LINE_MAX_BYTES)):
        encode_command("cell", HELLO_SEQ, {"fill": "x" * LINE_MAX_BYTES})


def test_encode_command_rejects_a_value_that_json_cannot_encode() -> None:
    """A field value outside the JSON types raises."""
    with pytest.raises(BolisProtocolError, match="JSON"):
        encode_command("cell", HELLO_SEQ, {"when": object()})


def test_is_control_line_separates_a_control_line_from_a_log_line() -> None:
    """The prefix decides, so the application log shares the serial line."""
    assert is_control_line(f"{LINE_PREFIX}" + '{"proto":1}')
    assert not is_control_line("I (123) bolis: the node started.")
    assert not is_control_line("")


def test_decode_reply_reads_the_envelope_of_a_hello_reply() -> None:
    """A hello reply decodes into its envelope, and the other keys stay in fields."""
    reply = decode_reply(_hello_line())
    assert reply.reply == "hello"
    assert reply.seq == HELLO_SEQ
    assert reply.proto == PROTO_VERSION
    assert reply.ok
    assert reply.err is None
    assert reply.fields["chip"] == CHIP
    assert "proto" not in reply.fields
    assert "ok" not in reply.fields


def test_the_text_form_of_a_reply_hides_the_other_fields() -> None:
    """The repr states the envelope alone, so a role reply leaks no MAC address."""
    reply = decode_reply(_hello_line())
    text = repr(reply)
    assert "hello" in text
    assert CHIP not in text
    assert SHA256_TEXT not in text


def test_decode_reply_accepts_a_line_without_a_trailing_newline() -> None:
    """A reader that strips the newline still decodes the line."""
    reply = decode_reply(_hello_line().rstrip("\n"))
    assert reply.reply == "hello"


def test_decode_reply_accepts_a_line_that_ends_with_carriage_return() -> None:
    """A serial line that carries a carriage return before the newline decodes."""
    reply = decode_reply(_hello_line().replace("\n", "\r\n"))
    assert reply.reply == "hello"


def test_decode_reply_rejects_a_line_without_the_prefix() -> None:
    """A log line that reaches the decoder raises."""
    with pytest.raises(BolisProtocolError, match="prefix"):
        decode_reply('{"proto":1,"reply":"hello","seq":1,"ok":true}')


def test_decode_reply_accepts_a_line_at_the_limit() -> None:
    """A line of exactly the limit decodes, so the boundary is inclusive."""
    reply = decode_reply(_line_of_size(LINE_MAX_BYTES))
    assert reply.reply == "hello"


def test_decode_reply_rejects_an_oversized_line() -> None:
    """A line one byte above the limit raises and names the size."""
    with pytest.raises(BolisProtocolError, match=str(LINE_MAX_BYTES)):
        decode_reply(_line_of_size(LINE_MAX_BYTES + 1))


def test_decode_reply_rejects_a_truncated_line() -> None:
    """A line that the serial link cut mid-object raises."""
    truncated = _hello_line().rstrip("\n")[:-20]
    with pytest.raises(BolisProtocolError, match="JSON"):
        decode_reply(truncated)


def test_decode_reply_rejects_malformed_json() -> None:
    """A line whose object does not parse raises."""
    with pytest.raises(BolisProtocolError, match="JSON"):
        decode_reply(f"{LINE_PREFIX}" + "{not json at all}\n")


def test_decode_reply_rejects_a_json_value_that_is_no_object() -> None:
    """A line that carries an array rather than an object raises."""
    with pytest.raises(BolisProtocolError, match="object"):
        decode_reply(f"{LINE_PREFIX}" + "[1,2,3]\n")


def test_decode_reply_refuses_a_node_that_states_another_proto() -> None:
    """A node on another contract version raises, and the message names both."""
    with pytest.raises(BolisProtocolError, match="proto"):
        decode_reply(_hello_line(proto=PROTO_VERSION + 1))


def test_decode_reply_rejects_a_reply_that_omits_an_envelope_key() -> None:
    """A reply without ok raises and names the key."""
    with pytest.raises(BolisProtocolError, match="ok"):
        decode_reply(_hello_line(ok=None))


def test_decode_reply_rejects_a_boolean_sequence_number() -> None:
    """JSON true is a kind of integer in Python, and the decoder rejects it."""
    with pytest.raises(BolisProtocolError, match="seq"):
        decode_reply(_hello_line(seq=True))


def test_decode_reply_rejects_text_in_place_of_the_sequence_number() -> None:
    """A sequence number that arrives as text raises."""
    with pytest.raises(BolisProtocolError, match="seq"):
        decode_reply(_hello_line(seq="1"))


def test_decode_reply_rejects_an_empty_reply_name() -> None:
    """A reply whose command name is empty raises."""
    with pytest.raises(BolisProtocolError, match="reply"):
        decode_reply(_hello_line(reply=""))


def test_decode_reply_rejects_err_beside_ok_true() -> None:
    """A reply that reports success and an error at once raises."""
    with pytest.raises(BolisProtocolError, match="err"):
        decode_reply(_hello_line(err="ESP_ERR_NOT_SUPPORTED"))


def test_decode_reply_requires_err_when_ok_is_false() -> None:
    """A failed reply without err raises."""
    with pytest.raises(BolisProtocolError, match="err"):
        decode_reply(_hello_line(ok=False))


def test_decode_reply_reads_a_failed_reply() -> None:
    """A failed reply decodes, and err holds the name of the ESP-IDF code."""
    line = (
        f"{LINE_PREFIX}"
        '{"proto":1,"reply":"role","seq":4,"ok":false,"err":"ESP_ERR_NOT_SUPPORTED"}\n'
    )
    reply = decode_reply(line)
    assert not reply.ok
    assert reply.err == "ESP_ERR_NOT_SUPPORTED"
    assert reply.seq == ROLE_SEQ


def test_raise_for_reply_passes_a_successful_reply_through() -> None:
    """A reply with ok true returns unchanged."""
    reply = decode_reply(_hello_line())
    assert raise_for_reply(reply) is reply


def test_raise_for_reply_raises_on_a_failed_reply() -> None:
    """A reply with ok false raises, and the error carries the three fields."""
    line = (
        f"{LINE_PREFIX}"
        '{"proto":1,"reply":"go","seq":9,"ok":false,"err":"ESP_ERR_INVALID_STATE"}\n'
    )
    reply = decode_reply(line)
    with pytest.raises(BolisNodeError) as exc_info:
        raise_for_reply(reply)
    assert exc_info.value.reply == "go"
    assert exc_info.value.seq == GO_SEQ
    assert exc_info.value.err == "ESP_ERR_INVALID_STATE"


def test_parse_hello_reads_every_field_of_the_reply() -> None:
    """The nine fields of a hello reply reach the Hello object."""
    hello = parse_hello(decode_reply(_hello_line()))
    assert hello.chip == CHIP
    assert hello.chip_revision == CHIP_REVISION
    assert hello.idf_version == IDF_VERSION
    assert hello.espnow_version == ESPNOW_VERSION
    assert hello.payload_limit_bytes == PAYLOAD_LIMIT_BYTES
    assert hello.bolis_version == BOLIS_VERSION
    assert hello.firmware_path == FIRMWARE_PATH
    assert hello.elf_sha256 == SHA256_TEXT
    assert hello.bluetooth_controller == BLUETOOTH_CONTROLLER


def test_parse_hello_rejects_a_reply_to_another_command() -> None:
    """A reply that answers another command raises."""
    reply = decode_reply(_hello_line(reply="stats"))
    with pytest.raises(BolisProtocolError, match="stats"):
        parse_hello(reply)


def test_parse_hello_raises_a_node_error_on_a_failed_hello() -> None:
    """A hello that the node refused raises the node error, not a format error."""
    reply = decode_reply(_hello_line(ok=False, err="ESP_ERR_INVALID_STATE"))
    with pytest.raises(BolisNodeError, match="ESP_ERR_INVALID_STATE"):
        parse_hello(reply)


def test_parse_hello_rejects_a_short_elf_sha256() -> None:
    """A truncated hash raises, because the record states the full length."""
    reply = decode_reply(_hello_line(elf_sha256="ab" * 4))
    with pytest.raises(BolisProtocolError, match=str(ELF_SHA256_TEXT_LENGTH)):
        parse_hello(reply)


def test_parse_hello_rejects_an_uppercase_elf_sha256() -> None:
    """The record states lowercase characters, so an uppercase hash raises."""
    reply = decode_reply(_hello_line(elf_sha256="AB" * 32))
    with pytest.raises(BolisProtocolError, match="hexadecimal"):
        parse_hello(reply)


def test_parse_hello_rejects_a_non_hexadecimal_elf_sha256() -> None:
    """A hash of the right length with a bad character raises."""
    reply = decode_reply(_hello_line(elf_sha256="z" * ELF_SHA256_TEXT_LENGTH))
    with pytest.raises(BolisProtocolError, match="hexadecimal"):
        parse_hello(reply)


def test_parse_hello_rejects_a_payload_limit_of_zero() -> None:
    """A payload limit that is not above zero raises."""
    reply = decode_reply(_hello_line(payload_limit_bytes=0))
    with pytest.raises(BolisProtocolError, match="payload limit"):
        parse_hello(reply)


def test_parse_hello_rejects_a_negative_chip_revision() -> None:
    """A negative chip revision raises."""
    reply = decode_reply(_hello_line(chip_revision=-1))
    with pytest.raises(BolisProtocolError, match="chip revision"):
        parse_hello(reply)


def test_parse_hello_rejects_a_firmware_path_outside_the_contract() -> None:
    """A firmware path that the contract does not name raises."""
    reply = decode_reply(_hello_line(firmware_path="homebrew"))
    with pytest.raises(BolisProtocolError, match="firmware_path"):
        parse_hello(reply)


def test_parse_hello_rejects_a_bluetooth_state_outside_the_contract() -> None:
    """A Bluetooth controller state that the contract does not name raises."""
    reply = decode_reply(_hello_line(bluetooth_controller="asleep"))
    with pytest.raises(BolisProtocolError, match="bluetooth_controller"):
        parse_hello(reply)


def test_parse_hello_rejects_a_missing_field() -> None:
    """A hello reply without the chip raises and names the key."""
    reply = decode_reply(_hello_line(chip=None))
    with pytest.raises(BolisProtocolError, match="chip"):
        parse_hello(reply)


def test_require_same_firmware_accepts_two_nodes_on_one_image() -> None:
    """Two nodes that report one hash pass the check."""
    require_same_firmware(_hello(), _hello())


def test_require_same_firmware_rejects_two_images() -> None:
    """Two nodes that report different hashes raise before the first cell."""
    other = parse_hello(decode_reply(_hello_line(elf_sha256=OTHER_SHA256_TEXT)))
    with pytest.raises(BolisProtocolError, match="different firmware"):
        require_same_firmware(_hello(), other)


def test_a_command_and_its_reply_share_the_sequence_number() -> None:
    """The node copies seq, so a reader matches a reply to its command."""
    command = encode_command("hello", MATCHED_SEQ)
    sent = json.loads(command[len(LINE_PREFIX) :])
    reply = decode_reply(_hello_line(seq=MATCHED_SEQ))
    assert sent["seq"] == reply.seq
