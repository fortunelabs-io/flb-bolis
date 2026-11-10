"""The firmware flasher (decision 2026-11-10-firmware-image-carriage.md).

Writes one prebuilt image to a node and proves what runs on it afterward. The
host package carries one image per supported chip in `bolis/firmware/`, beside
a `manifest.json` that CI writes at release time. Git tracks neither.

The flasher checks the SHA-256 of an image file before it writes, which covers
the integrity of the file, and it reads the `elf_sha256` of the `hello` reply
after it writes, which is the one check that proves what runs on a node. The
first value reaches no run record. The second one does, as a `[measured]`
value (thinkbook section 9).

Every check happens with no network access, so specification section 7 holds.
A checkout carries no image, so this module serves the prebuilt path alone. A
source build reports the firmware path `source` and matches no manifest entry.

This module opens no serial port. The caller supplies a reader that returns
one `hello` reply line, so the transport that owns the port stays a separate
change and every test case runs offline.
"""

import hashlib
import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, Protocol

import esptool.cmds  # type: ignore[import-untyped]

from bolis import BolisError
from bolis.protocol import Hello, decode_reply, parse_hello, require_same_firmware

# The esptool loader of one node. esptool ships no type information, so this
# alias names the one boundary that the Python coding standard allows to carry
# Any. Every value of this type crosses straight back into esptool.
EspLoader = Any

# The manifest that CI writes beside the images. The name and every key below
# belong to the carriage record, and a change to any of them raises
# MANIFEST_VERSION and needs a new record.
MANIFEST_NAME: Final = "manifest.json"
MANIFEST_VERSION: Final = 1

# The directory inside the installed package that carries the images and the
# manifest.
FIRMWARE_DIRECTORY: Final = Path(__file__).parent / "firmware"

# A SHA-256 reaches the manifest as 64 lowercase hexadecimal characters, the
# same form the control line states for the ELF hash.
SHA256_TEXT_LENGTH: Final = 64
_HEX_LOWERCASE: Final = frozenset("0123456789abcdef")

# The keys of one manifest entry.
_ENTRY_KEYS: Final = ("chip", "file", "sha256", "elf_sha256", "bolis_version")

# A release image is one standalone image per chip, so it carries the
# bootloader and the partition table and the write starts at the beginning of
# the flash. No record states this offset. It follows from the image being
# standalone: an image that the host writes with no second artifact has to hold
# every artifact, which places it at offset 0.
FLASH_ADDRESS: Final = 0x0

# The rate that the esptool Python API uses unless a caller states another one.
DEFAULT_BAUD: Final = 460800


class BolisFlashError(BolisError):
    """Raised when the flasher refuses to write, or refuses a node after a write."""


@dataclass(frozen=True)
class ImageEntry:
    """One entry of the manifest, which names the image of one chip.

    Attributes:
        chip: The chip name that the esptool Python API reports, in the form
            that `chip_key` returns, such as esp32.
        file: The name of the image file, inside the same directory as the
            manifest.
        sha256: The SHA-256 of the image file, as 64 lowercase hexadecimal
            characters.
        elf_sha256: The ELF SHA-256 that the image states in its hello reply,
            in the same form.
        bolis_version: The Bolis version that built the image.
    """

    chip: str
    file: str
    sha256: str
    elf_sha256: str
    bolis_version: str


class FlashBackend(Protocol):
    """The esptool entry points that the flasher calls.

    The flasher states this interface so a test case drives it with no serial
    port and with no node, and so one class holds every call into esptool.
    """

    def detect_chip(self, port: str, baud: int) -> EspLoader:
        """Opens the port and identifies the chip."""
        ...

    def attach_flash(self, esp: EspLoader) -> None:
        """Attaches the flash of the node."""
        ...

    def write_flash(self, esp: EspLoader, addr_data: list[tuple[int, bytes]]) -> None:
        """Writes each block of bytes to its address."""
        ...

    def reset_chip(self, esp: EspLoader) -> None:
        """Resets the node, so the image it now holds starts."""
        ...

    def chip_name(self, esp: EspLoader) -> str:
        """Returns the chip name that the loader reports."""
        ...


class EsptoolBackend:
    """The backend that drives a node through the esptool Python API.

    Decision 2026-10-01-radio-ownership-and-prebuilt-firmware.md requires the
    Python API, so this class starts no subprocess and builds no command line.
    """

    def detect_chip(self, port: str, baud: int) -> EspLoader:
        """Opens the port and identifies the chip.

        Args:
            port: The serial port of the node.
            baud: The rate, in bits per second.

        Returns:
            The esptool loader of the detected chip.
        """
        return esptool.cmds.detect_chip(port=port, baud=baud)

    def attach_flash(self, esp: EspLoader) -> None:
        """Attaches the flash of the node.

        Args:
            esp: The esptool loader of the node.
        """
        esptool.cmds.attach_flash(esp)

    def write_flash(self, esp: EspLoader, addr_data: list[tuple[int, bytes]]) -> None:
        """Writes each block of bytes to its address.

        Args:
            esp: The esptool loader of the node.
            addr_data: One pair per block, each holding the flash offset and
                the bytes to write.
        """
        esptool.cmds.write_flash(esp, addr_data)

    def reset_chip(self, esp: EspLoader) -> None:
        """Resets the node, so the image it now holds starts.

        Args:
            esp: The esptool loader of the node.
        """
        esptool.cmds.reset_chip(esp)

    def chip_name(self, esp: EspLoader) -> str:
        """Returns the chip name that the loader reports.

        Args:
            esp: The esptool loader of the node.

        Returns:
            The display name, such as ESP32-S3.
        """
        return str(esp.CHIP_NAME)


# A reader that sends one hello command to a port and returns the reply line.
HelloReader = Callable[[str], str]

# esptool opens a port through pyserial, which reads a name holding this mark
# as a URL and can reach a serial server over the network.
_PORT_URL_MARK: Final = "://"


def validate_local_port(port: str) -> str:
    """Checks that a port names a local device rather than a network address.

    pyserial accepts a URL in place of a device path, such as one that reaches
    a serial server over the network. Specification section 7 keeps the host
    offline, so the flasher refuses such a name rather than opening it. No
    record states this check. It follows from that section, which the Python
    coding standard also states as a rule for the package.

    Args:
        port: The serial port that the user typed.

    Returns:
        The same port, unchanged.

    Raises:
        BolisFlashError: The port holds a URL scheme.
    """
    if _PORT_URL_MARK in port:
        raise BolisFlashError(
            f"the port {port!r} names a URL rather than a device. Bolis flashes "
            "a local device, because the host sends nothing off the machine of "
            "the user."
        )
    return port


def chip_key(chip_name: str) -> str:
    """Converts a chip name that esptool reports into its manifest key.

    The esptool Python API carries two forms of a chip name. It keys its
    targets by a compact name, such as esp32s3, and a loader reports a display
    name, such as ESP32-S3. The manifest uses the compact form, which is also
    the form a node states in the chip field of its hello reply.

    Args:
        chip_name: The display name that a loader reports.

    Returns:
        The compact name, in lowercase and with no hyphen.
    """
    return chip_name.replace("-", "").lower()


def _require_text(entry: Mapping[str, Any], key: str, file_name: str) -> str:
    """Reads one key of a manifest entry as non-empty text.

    Args:
        entry: One decoded entry of the manifest.
        key: The key to read.
        file_name: The manifest path, for the message.

    Returns:
        The text value.

    Raises:
        BolisFlashError: The key is absent, or its value is not text, or the
            text is empty.
    """
    if key not in entry:
        raise BolisFlashError(f"{file_name} holds an entry with no key {key!r}.")
    value = entry[key]
    if not isinstance(value, str) or len(value) == 0:
        raise BolisFlashError(f"{file_name} holds a {key!r} that is not text.")
    return value


def _require_hash(entry: Mapping[str, Any], key: str, file_name: str) -> str:
    """Reads one key of a manifest entry as a SHA-256 in text form.

    Args:
        entry: One decoded entry of the manifest.
        key: The key to read.
        file_name: The manifest path, for the message.

    Returns:
        The hash, as 64 lowercase hexadecimal characters.

    Raises:
        BolisFlashError: The value is not 64 lowercase hexadecimal characters.
    """
    value = _require_text(entry, key, file_name)
    if len(value) != SHA256_TEXT_LENGTH or not set(value) <= _HEX_LOWERCASE:
        raise BolisFlashError(
            f"{file_name} holds a {key!r} that is not {SHA256_TEXT_LENGTH} "
            "lowercase hexadecimal characters."
        )
    return value


def read_manifest(directory: Path | None = None) -> Mapping[str, ImageEntry]:
    """Reads the manifest and returns one entry per chip.

    Args:
        directory: The directory that holds the manifest and the images. None
            reads the firmware directory of the installed package.

    Returns:
        The entries, by the manifest key of their chip.

    Raises:
        BolisFlashError: The manifest is absent, it holds no readable JSON, it
            states another manifest version, an entry omits a key, an entry
            holds a key of the wrong form, or two entries name one chip.
    """
    root = FIRMWARE_DIRECTORY if directory is None else directory
    path = root / MANIFEST_NAME
    file_name = str(path)
    if not path.is_file():
        raise BolisFlashError(
            f"{file_name} is absent, so this package carries no prebuilt image. "
            "An installed release carries the images, and a checkout does not."
        )

    try:
        decoded: Any = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as error:
        raise BolisFlashError(f"{file_name} holds no readable JSON.") from error
    if not isinstance(decoded, dict):
        raise BolisFlashError(f"{file_name} holds no JSON object.")

    version = decoded.get("manifest_version")
    if version != MANIFEST_VERSION:
        raise BolisFlashError(
            f"{file_name} states manifest version {version!r}. This host reads "
            f"version {MANIFEST_VERSION}."
        )

    images = decoded.get("images")
    if not isinstance(images, list):
        raise BolisFlashError(f"{file_name} holds no images list.")

    entries: dict[str, ImageEntry] = {}
    for image in images:
        if not isinstance(image, dict):
            raise BolisFlashError(f"{file_name} holds an entry that is no object.")
        entry = ImageEntry(
            chip=_require_text(image, "chip", file_name),
            file=_require_text(image, "file", file_name),
            sha256=_require_hash(image, "sha256", file_name),
            elf_sha256=_require_hash(image, "elf_sha256", file_name),
            bolis_version=_require_text(image, "bolis_version", file_name),
        )
        if entry.chip in entries:
            raise BolisFlashError(
                f"{file_name} names the chip {entry.chip!r} in two entries."
            )
        entries[entry.chip] = entry
    return entries


def resolve_entry(manifest: Mapping[str, ImageEntry], chip: str) -> ImageEntry:
    """Returns the entry of one chip, or raises and names the chips on offer.

    Args:
        manifest: The entries, by the manifest key of their chip.
        chip: The manifest key of the detected chip.

    Returns:
        The entry of that chip.

    Raises:
        BolisFlashError: The manifest names no entry for that chip. The message
            names the chips that the manifest carries, so a user learns which
            chips the release supports.
    """
    entry = manifest.get(chip)
    if entry is None:
        carried = ", ".join(sorted(manifest)) if manifest else "no chip"
        raise BolisFlashError(
            f"the node reports the chip {chip!r}, and this package carries an "
            f"image for: {carried}."
        )
    return entry


def image_sha256(path: Path) -> str:
    """Computes the SHA-256 of a file.

    Args:
        path: The file to read.

    Returns:
        The hash, as 64 lowercase hexadecimal characters.

    Raises:
        BolisFlashError: The file is absent.
    """
    if not path.is_file():
        raise BolisFlashError(f"{path} is absent, so no image reached the node.")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_image(path: Path, entry: ImageEntry) -> None:
    """Refuses an image file whose hash differs from its manifest entry.

    This check covers the integrity of the file. It detects a truncated or a
    corrupted image before a write reaches a node, and it does not detect a
    substitution, because the manifest travels beside the images. The value it
    computes reaches no run record.

    Args:
        path: The image file.
        entry: The manifest entry of that image.

    Raises:
        BolisFlashError: The hash of the file differs from the entry.
    """
    found = image_sha256(path)
    if found != entry.sha256:
        raise BolisFlashError(
            f"{path} hashes to {found}, and the manifest states {entry.sha256}. "
            "The flasher wrote nothing."
        )


def confirm_node(reply_line: str, entry: ImageEntry) -> Hello:
    """Reads a hello reply and refuses a node that runs another image.

    This is the one check that proves what runs on a node. The check before the
    write covers the file alone.

    Args:
        reply_line: One control line that the node wrote, which this function
            treats as untrusted.
        entry: The manifest entry of the image that the flasher wrote.

    Returns:
        The test condition that the node stated.

    Raises:
        BolisFlashError: The node reports another ELF SHA-256.
        BolisProtocolError: The line does not meet the wire contract.
        BolisNodeError: The node answered hello with ok set to false.
    """
    hello = parse_hello(decode_reply(reply_line))
    if hello.elf_sha256 != entry.elf_sha256:
        raise BolisFlashError(
            f"the node runs ELF SHA-256 {hello.elf_sha256}, and the image "
            f"states {entry.elf_sha256}. The write did not take effect."
        )
    return hello


def flash_node(
    port: str,
    read_hello: HelloReader,
    *,
    directory: Path | None = None,
    backend: FlashBackend | None = None,
    baud: int = DEFAULT_BAUD,
) -> Hello:
    """Writes the image of the detected chip to one node and confirms the result.

    Follows the order that the carriage record states: read the manifest,
    detect the chip, resolve the entry, check the hash of the file, write,
    reset, then read the hello reply and compare the ELF SHA-256.

    Args:
        port: The serial port of the node.
        read_hello: A reader that sends one hello command to a port and returns
            the reply line.
        directory: The directory that holds the manifest and the images. None
            reads the firmware directory of the installed package.
        backend: The esptool entry points. None drives the esptool Python API.
        baud: The rate, in bits per second.

    Returns:
        The test condition that the node stated after the write.

    Raises:
        BolisFlashError: The manifest or the image is absent or malformed, the
            manifest names no entry for the detected chip, the hash of the file
            differs from the entry, or the node reports another ELF SHA-256.
    """
    validate_local_port(port)
    driver: FlashBackend = EsptoolBackend() if backend is None else backend
    root = FIRMWARE_DIRECTORY if directory is None else directory

    manifest = read_manifest(root)
    esp = driver.detect_chip(port, baud)
    entry = resolve_entry(manifest, chip_key(driver.chip_name(esp)))

    image_path = root / entry.file
    verify_image(image_path, entry)

    driver.attach_flash(esp)
    driver.write_flash(esp, [(FLASH_ADDRESS, image_path.read_bytes())])
    driver.reset_chip(esp)

    return confirm_node(read_hello(port), entry)


# The six arguments are the two ports, the reader, and three overrides that a
# caller rarely sets. A type that bundled the three would add a name without
# removing a decision.
def flash_pair(  # noqa: PLR0913
    sender_port: str,
    receiver_port: str,
    read_hello: HelloReader,
    *,
    directory: Path | None = None,
    backend: FlashBackend | None = None,
    baud: int = DEFAULT_BAUD,
) -> tuple[Hello, Hello]:
    """Writes the image to both nodes and refuses a pair that differs in firmware.

    Both nodes run the same image (decision
    2026-10-01-radio-ownership-and-prebuilt-firmware.md), and the host refuses
    a pair whose hello replies differ in firmware.

    Args:
        sender_port: The serial port of the node that takes the sender role.
        receiver_port: The serial port of the node that takes the receiver role.
        read_hello: A reader that sends one hello command to a port and returns
            the reply line.
        directory: The directory that holds the manifest and the images. None
            reads the firmware directory of the installed package.
        backend: The esptool entry points. None drives the esptool Python API.
        baud: The rate, in bits per second.

    Returns:
        The test condition of the sender and of the receiver, in that order.

    Raises:
        BolisFlashError: Either node failed a check of flash_node.
        BolisProtocolError: The two nodes report different firmware.
    """
    sender = flash_node(
        sender_port, read_hello, directory=directory, backend=backend, baud=baud
    )
    receiver = flash_node(
        receiver_port, read_hello, directory=directory, backend=backend, baud=baud
    )
    require_same_firmware(sender, receiver)
    return sender, receiver
