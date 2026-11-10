# Firmware images

CI places one prebuilt image per supported chip in this directory when it builds a release, beside one `manifest.json` that names the file, the image hash, the ELF hash, and the Bolis version of each entry (`docs/adr/2026-11-10-firmware-image-carriage.md`). Git tracks neither the images nor the manifest (`.gitignore`).

A checkout therefore carries no image, and `bolis flash` reports that the package holds none. An installed release carries both. A source build follows the example project in `components/bolis/examples/bench/`.
