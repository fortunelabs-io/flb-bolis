"""Tests for the firmware flasher.

Every case runs offline. A stub backend stands in for the esptool Python API,
so no case opens a serial port and no case needs a node.
"""

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
from esptool.targets import CHIP_DEFS

from bolis.flasher import (
    FLASH_ADDRESS,
    MANIFEST_NAME,
    MANIFEST_VERSION,
    SHA256_TEXT_LENGTH,
    BolisFlashError,
    chip_key,
    confirm_node,
    flash_node,
    flash_pair,
    image_sha256,
    read_manifest,
    resolve_entry,
    validate_local_port,
    verify_image,
)
from bolis.protocol import LINE_PREFIX, PROTO_VERSION, BolisProtocolError

# The literal values below come from the carriage record and the wire format
# record, not from bolis.flasher's own constants, so a typo in the module
# cannot make its own test pass.
EXPECTED_MANIFEST_VERSION = 1
EXPECTED_MANIFEST_NAME = "manifest.json"
EXPECTED_SHA256_TEXT_LENGTH = 64
EXPECTED_FLASH_ADDRESS = 0

CHIP = "esp32"
CHIP_DISPLAY_NAME = "ESP32"
OTHER_CHIP_DISPLAY_NAME = "ESP32-S3"
IMAGE_NAME = "bolis-esp32.bin"
IMAGE_BYTES = b"a firmware image that stands in for the real one"
ELF_SHA256 = "ab" * 32
OTHER_ELF_SHA256 = "cd" * 32
BOLIS_VERSION = "0.1.0"
PORTS = ("/dev/ttyUSB0", "/dev/ttyUSB1")
NODES_PER_RUN = 2

# Port names that pyserial reads as a URL. Each one would reach a serial
# server over the network, which specification section 7 rules out.
URL_PORTS = ("rfc2217://10.0.0.5:4000", "socket://10.0.0.5:4000")


class StubBackend:
    """A backend that records its calls and opens no port.

    Attributes:
        chip_display_name: The name that chip_name returns.
        calls: The method names in the order the flasher called them.
        written: Each address and block of bytes that write_flash received.
    """

    def __init__(self, chip_display_name: str = CHIP_DISPLAY_NAME) -> None:
        """Builds the stub.

        Args:
            chip_display_name: The name that chip_name returns, such as ESP32.
        """
        self.chip_display_name = chip_display_name
        self.calls: list[str] = []
        self.written: list[tuple[int, bytes]] = []

    def detect_chip(self, port: str, baud: int) -> Any:  # noqa: ANN401
        """Records the call and returns a stand-in loader.

        Args:
            port: The serial port of the node.
            baud: The rate, in bits per second.

        Returns:
            The port, which later calls carry back.
        """
        self.calls.append("detect_chip")
        return port

    def attach_flash(self, esp: Any) -> None:  # noqa: ANN401
        """Records the call.

        Args:
            esp: The stand-in loader.
        """
        self.calls.append("attach_flash")

    def write_flash(self, esp: Any, addr_data: list[tuple[int, bytes]]) -> None:  # noqa: ANN401
        """Records the call and the bytes.

        Args:
            esp: The stand-in loader.
            addr_data: One pair per block.
        """
        self.calls.append("write_flash")
        self.written.extend(addr_data)

    def reset_chip(self, esp: Any) -> None:  # noqa: ANN401
        """Records the call.

        Args:
            esp: The stand-in loader.
        """
        self.calls.append("reset_chip")

    def chip_name(self, esp: Any) -> str:  # noqa: ANN401
        """Returns the configured chip name.

        Args:
            esp: The stand-in loader.

        Returns:
            The display name.
        """
        return self.chip_display_name


def _hello_line(elf_sha256: str = ELF_SHA256, **overrides: object) -> str:
    """Builds a hello reply line that a node would write after a write.

    Args:
        elf_sha256: The ELF hash the node reports.
        overrides: Keys to add to the object, or to replace in it.

    Returns:
        The control line, with its prefix and its trailing newline.
    """
    fields: dict[str, object] = {
        "proto": PROTO_VERSION,
        "reply": "hello",
        "seq": 1,
        "ok": True,
        "chip": CHIP,
        "chip_revision": 301,
        "idf_version": "v5.5.4",
        "espnow_version": 2,
        "payload_limit_bytes": 1470,
        "bolis_version": BOLIS_VERSION,
        "firmware_path": "prebuilt",
        "elf_sha256": elf_sha256,
        "bluetooth_controller": "disabled",
    }
    fields.update(overrides)
    text = json.dumps(fields, separators=(",", ":"), ensure_ascii=True)
    return f"{LINE_PREFIX}{text}\n"


def _entry(**overrides: object) -> dict[str, object]:
    """Builds one manifest entry as the decoded object.

    Args:
        overrides: Keys to replace. A value of None removes the key.

    Returns:
        The entry.
    """
    entry: dict[str, object] = {
        "chip": CHIP,
        "file": IMAGE_NAME,
        "sha256": hashlib.sha256(IMAGE_BYTES).hexdigest(),
        "elf_sha256": ELF_SHA256,
        "bolis_version": BOLIS_VERSION,
    }
    entry.update(overrides)
    for key, value in list(entry.items()):
        if value is None:
            del entry[key]
    return entry


def _release(
    tmp_path: Path,
    image_bytes: bytes = IMAGE_BYTES,
    *,
    write_image: bool = True,
    **manifest_overrides: object,
) -> Path:
    """Writes a stand-in release directory and returns its path.

    Args:
        tmp_path: The directory to write into.
        image_bytes: The bytes of the image file.
        write_image: Whether to write the image file at all.
        manifest_overrides: Keys to replace in the manifest object.

    Returns:
        The directory holding the manifest and the image.
    """
    manifest: dict[str, object] = {
        "manifest_version": MANIFEST_VERSION,
        "images": [_entry()],
    }
    manifest.update(manifest_overrides)
    (tmp_path / MANIFEST_NAME).write_text(json.dumps(manifest), encoding="utf-8")
    if write_image:
        (tmp_path / IMAGE_NAME).write_bytes(image_bytes)
    return tmp_path


def test_the_constants_match_the_records() -> None:
    """The module states the values that the two records fix."""
    assert MANIFEST_VERSION == EXPECTED_MANIFEST_VERSION
    assert MANIFEST_NAME == EXPECTED_MANIFEST_NAME
    assert SHA256_TEXT_LENGTH == EXPECTED_SHA256_TEXT_LENGTH
    assert FLASH_ADDRESS == EXPECTED_FLASH_ADDRESS


def test_chip_key_matches_every_target_that_esptool_ships() -> None:
    """The manifest key of each chip equals the key esptool uses for that target.

    The carriage record keys the manifest by the name that the esptool Python
    API reports, and a release of esptool that renames a chip breaks the
    lookup. This case compares the conversion against the table of esptool
    itself, so such a rename fails here rather than at a bench.
    """
    for key, definition in CHIP_DEFS.items():
        assert chip_key(definition.CHIP_NAME) == key


def test_chip_key_removes_the_hyphen_and_the_case() -> None:
    """A display name becomes the compact name that the manifest uses."""
    assert chip_key("ESP32") == "esp32"
    assert chip_key("ESP32-S3") == "esp32s3"


def test_read_manifest_reads_every_entry(tmp_path: Path) -> None:
    """A manifest of one entry reads back with every field."""
    manifest = read_manifest(_release(tmp_path))
    assert set(manifest) == {CHIP}
    entry = manifest[CHIP]
    assert entry.file == IMAGE_NAME
    assert entry.elf_sha256 == ELF_SHA256
    assert entry.bolis_version == BOLIS_VERSION
    assert entry.sha256 == hashlib.sha256(IMAGE_BYTES).hexdigest()


def test_read_manifest_reports_an_absent_manifest(tmp_path: Path) -> None:
    """A checkout carries no manifest, and the message says so."""
    with pytest.raises(BolisFlashError, match="absent"):
        read_manifest(tmp_path)


def test_read_manifest_rejects_another_manifest_version(tmp_path: Path) -> None:
    """A manifest of a later layout raises and names the version."""
    directory = _release(tmp_path, manifest_version=MANIFEST_VERSION + 1)
    with pytest.raises(BolisFlashError, match="manifest version"):
        read_manifest(directory)


def test_read_manifest_rejects_malformed_json(tmp_path: Path) -> None:
    """A manifest that does not parse raises."""
    (tmp_path / MANIFEST_NAME).write_text("{not json", encoding="utf-8")
    with pytest.raises(BolisFlashError, match="JSON"):
        read_manifest(tmp_path)


@pytest.mark.parametrize(
    "key", ["chip", "file", "sha256", "elf_sha256", "bolis_version"]
)
def test_read_manifest_rejects_an_entry_that_omits_a_key(
    tmp_path: Path, key: str
) -> None:
    """Every key of an entry is required, and the message names the missing one."""
    manifest = {"manifest_version": MANIFEST_VERSION, "images": [_entry(**{key: None})]}
    (tmp_path / MANIFEST_NAME).write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(BolisFlashError, match=key):
        read_manifest(tmp_path)


@pytest.mark.parametrize("key", ["sha256", "elf_sha256"])
def test_read_manifest_rejects_a_hash_of_the_wrong_form(
    tmp_path: Path, key: str
) -> None:
    """A hash that is not 64 lowercase hexadecimal characters raises."""
    manifest = {
        "manifest_version": MANIFEST_VERSION,
        "images": [_entry(**{key: "AB" * 32})],
    }
    (tmp_path / MANIFEST_NAME).write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(BolisFlashError, match="hexadecimal"):
        read_manifest(tmp_path)


def test_read_manifest_rejects_two_entries_for_one_chip(tmp_path: Path) -> None:
    """A manifest that names one chip twice raises, because the lookup is by chip."""
    manifest = {"manifest_version": MANIFEST_VERSION, "images": [_entry(), _entry()]}
    (tmp_path / MANIFEST_NAME).write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(BolisFlashError, match="two entries"):
        read_manifest(tmp_path)


def test_resolve_entry_names_the_chips_the_manifest_carries(tmp_path: Path) -> None:
    """A chip with no entry raises, and the message names the chips on offer."""
    manifest = read_manifest(_release(tmp_path))
    with pytest.raises(BolisFlashError, match=CHIP):
        resolve_entry(manifest, "esp32s3")


def test_image_sha256_reads_the_file(tmp_path: Path) -> None:
    """The hash of a file matches the hash of its bytes."""
    path = tmp_path / IMAGE_NAME
    path.write_bytes(IMAGE_BYTES)
    assert image_sha256(path) == hashlib.sha256(IMAGE_BYTES).hexdigest()


def test_verify_image_accepts_a_matching_file(tmp_path: Path) -> None:
    """An image whose hash matches its entry passes."""
    directory = _release(tmp_path)
    entry = read_manifest(directory)[CHIP]
    verify_image(directory / entry.file, entry)


def test_verify_image_refuses_a_corrupted_file(tmp_path: Path) -> None:
    """An image whose bytes changed raises, and the message says nothing was sent."""
    directory = _release(tmp_path, image_bytes=IMAGE_BYTES + b"corruption")
    entry = read_manifest(directory)[CHIP]
    with pytest.raises(BolisFlashError, match="wrote nothing"):
        verify_image(directory / entry.file, entry)


def test_flash_node_writes_the_image_and_confirms_the_node(tmp_path: Path) -> None:
    """The happy path writes the image at the start of the flash and reads the reply."""
    directory = _release(tmp_path)
    backend = StubBackend()
    hello = flash_node(
        PORTS[0], lambda _port: _hello_line(), directory=directory, backend=backend
    )
    assert hello.elf_sha256 == ELF_SHA256
    assert hello.firmware_path == "prebuilt"
    assert backend.calls == [
        "detect_chip",
        "attach_flash",
        "write_flash",
        "reset_chip",
    ]
    assert backend.written == [(FLASH_ADDRESS, IMAGE_BYTES)]


def test_flash_node_stops_before_a_write_when_no_entry_matches(tmp_path: Path) -> None:
    """A chip with no image never reaches a write."""
    directory = _release(tmp_path)
    backend = StubBackend(chip_display_name=OTHER_CHIP_DISPLAY_NAME)
    with pytest.raises(BolisFlashError, match="esp32s3"):
        flash_node(
            PORTS[0], lambda _port: _hello_line(), directory=directory, backend=backend
        )
    assert "write_flash" not in backend.calls


def test_flash_node_stops_before_a_write_on_a_hash_mismatch(tmp_path: Path) -> None:
    """A corrupted image never reaches a write."""
    directory = _release(tmp_path, image_bytes=IMAGE_BYTES + b"corruption")
    backend = StubBackend()
    with pytest.raises(BolisFlashError, match="wrote nothing"):
        flash_node(
            PORTS[0], lambda _port: _hello_line(), directory=directory, backend=backend
        )
    assert "write_flash" not in backend.calls


def test_flash_node_stops_before_a_write_when_the_image_is_absent(
    tmp_path: Path,
) -> None:
    """A manifest naming a file the directory lacks never reaches a write."""
    directory = _release(tmp_path, write_image=False)
    backend = StubBackend()
    with pytest.raises(BolisFlashError, match="absent"):
        flash_node(
            PORTS[0], lambda _port: _hello_line(), directory=directory, backend=backend
        )
    assert "write_flash" not in backend.calls


def test_flash_node_refuses_a_node_that_runs_another_image(tmp_path: Path) -> None:
    """The check after the write proves what runs, so another ELF hash raises."""
    directory = _release(tmp_path)
    backend = StubBackend()
    with pytest.raises(BolisFlashError, match="did not take effect"):
        flash_node(
            PORTS[0],
            lambda _port: _hello_line(elf_sha256=OTHER_ELF_SHA256),
            directory=directory,
            backend=backend,
        )
    assert "write_flash" in backend.calls


def test_confirm_node_treats_the_reply_as_untrusted(tmp_path: Path) -> None:
    """A reply that breaks the wire contract raises a protocol error."""
    entry = read_manifest(_release(tmp_path))[CHIP]
    with pytest.raises(BolisProtocolError):
        confirm_node("not a control line at all\n", entry)


def test_flash_pair_writes_both_nodes(tmp_path: Path) -> None:
    """Both nodes take the same image, and the pair passes the firmware check."""
    directory = _release(tmp_path)
    backend = StubBackend()
    sender, receiver = flash_pair(
        PORTS[0],
        PORTS[1],
        lambda _port: _hello_line(),
        directory=directory,
        backend=backend,
    )
    assert sender.elf_sha256 == receiver.elf_sha256
    assert backend.calls.count("write_flash") == NODES_PER_RUN


def test_flash_pair_refuses_two_nodes_on_different_images(tmp_path: Path) -> None:
    """A pair whose replies differ in firmware raises before a run starts.

    The manifest states one ELF hash, so a node that reports another one fails
    the check after its own write. This case states the pair rule by reaching
    that refusal through flash_pair.
    """
    directory = _release(tmp_path)
    backend = StubBackend()
    replies = iter([_hello_line(), _hello_line(elf_sha256=OTHER_ELF_SHA256)])

    with pytest.raises(BolisFlashError, match="did not take effect"):
        flash_pair(
            PORTS[0],
            PORTS[1],
            lambda _port: next(replies),
            directory=directory,
            backend=backend,
        )


def test_validate_local_port_accepts_a_device_path() -> None:
    """A device path passes unchanged."""
    for port in PORTS:
        assert validate_local_port(port) == port


@pytest.mark.parametrize("port", URL_PORTS)
def test_validate_local_port_refuses_a_url(port: str) -> None:
    """A port that pyserial would read as a URL raises, which keeps the host offline."""
    with pytest.raises(BolisFlashError, match="URL"):
        validate_local_port(port)


@pytest.mark.parametrize("port", URL_PORTS)
def test_flash_node_opens_no_url(tmp_path: Path, port: str) -> None:
    """A URL port never reaches esptool, so no node and no socket is opened."""
    directory = _release(tmp_path)
    backend = StubBackend()
    with pytest.raises(BolisFlashError, match="URL"):
        flash_node(
            port, lambda _port: _hello_line(), directory=directory, backend=backend
        )
    assert backend.calls == []


def test_the_flasher_states_no_mac_address(tmp_path: Path) -> None:
    """A hello reply carries no MAC address, so no message of the flasher states one."""
    directory = _release(tmp_path)
    entry = read_manifest(directory)[CHIP]
    hello = confirm_node(_hello_line(), entry)
    assert "mac" not in repr(hello).lower()
