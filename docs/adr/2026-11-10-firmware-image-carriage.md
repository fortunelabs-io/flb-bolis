# The host package carries each firmware image with a manifest

Date: 2026-11-10
Status: Proposed

## Context

The radio ownership record made prebuilt firmware the default path. It stated that the images ship inside the host package, so that flashing needs no network access, and that CI publishes the hash of each image with each release. It did not state how the package carries an image, how the host finds the image of a chip, or where the host reads the hash that it checks. `host/src/bolis/firmware/` held one placeholder file, and `.gitignore` kept the images out of git, so CI was the only producer of that directory. The Python coding standard required a check of the SHA-256 of an image before the CLI flashes it, and no tracked file stated where the expected value came from. The hash that the radio ownership record named sat on the GitHub release, which the host cannot read, because specification section 7 keeps the host offline. The control line wire format record already made a node state its ELF SHA-256 in the `hello` reply, as 64 lowercase hexadecimal characters. `bolis flash` raised `BolisNotImplementedError`, and no flasher module existed. If nothing was decided, the first flasher would fix the layout of the package by accident, and CI would have to match a layout that no record stated.

## Alternatives considered

- A manifest beside the images that CI writes at release time, naming the file, the image hash, and the ELF hash of each chip.
- A tracked file of expected hashes, committed while a release is cut.
- No expected hash, with the hash that the flasher computes written to the run record instead.
- The hash of each image read from the GitHub release at flash time, which needs network access.
- The expected hash embedded in a Python module that CI generates.
- The image hash reused from the control line, which states the hash of the ELF rather than the hash of the image file.

## Decision

The host package carries one directory, `bolis/firmware/`. CI writes one image per supported chip and one `manifest.json` into that directory at release time. Git tracks neither the images nor the manifest.

The manifest names one entry per chip. Each entry carries the file name, the SHA-256 of the image file, the ELF SHA-256 that the image reports in its `hello` reply, and the Bolis version that built it. The manifest carries `manifest_version`, an integer that names the version of this layout, and the first version is 1. That key is separate from `proto`, which names the control line contract, because the two contracts change on their own schedules.

```json
{
  "manifest_version": 1,
  "images": [
    {
      "chip": "esp32",
      "file": "bolis-esp32.bin",
      "sha256": "<64 hex characters>",
      "elf_sha256": "<64 hex characters>",
      "bolis_version": "0.1.0"
    }
  ]
}
```

`bolis flash` detects the chip of each node through the esptool Python API, reads the manifest, and resolves the entry of the detected chip. It stops before it writes when the manifest names no entry for that chip, and the message names the chips that the manifest carries.

The flasher computes the SHA-256 of the image file and refuses to write when the value differs from the entry. That check covers the integrity of the file and does not enter the run record.

After the write, the host reads the `hello` reply of the node and refuses the node when its `elf_sha256` differs from the entry. The run record states the ELF SHA-256 that the node reported, which thinkbook section 9 already lists, as a `[measured]` value.

The flasher keys the manifest by the chip name that the esptool Python API reports.

## Consequences

- A truncated or corrupted image is refused before a write reaches a node.
- The host checks an image with no network access, so specification section 7 holds.
- The manifest is the one place that names the layout, so CI and the flasher agree through a file rather than through a convention that each side repeats.
- CI gains a step that writes the manifest, and a release that omits the manifest fails the flasher rather than flashing an unchecked image.
- Authenticity rests on the wheel that PyPI serves, because the manifest travels beside the images. The manifest detects corruption, and it does not detect substitution.
- The check after the write proves what runs on a node, which the check before the write cannot.
- The run record format does not change, because the hash it already lists is the value that a node reports.
- The hash of the image file reaches no run record, so no number of a run needs a new origin label.
- This rules out reading a hash from a GitHub release at flash time.
- A change to any manifest key raises `manifest_version` and needs a new record.
- A checkout carries no image, so the default path needs an installed release, and a source build covers the other case.
- A source build reports the firmware path `source` and matches no manifest entry, so `bolis flash` serves the prebuilt path alone.
- Watch the chip names that the esptool Python API reports. A release of esptool that renames a chip breaks the lookup, and `host/pyproject.toml` states `esptool>=5`, which is a floor and not a pin, so a later release reaches an installed package.
