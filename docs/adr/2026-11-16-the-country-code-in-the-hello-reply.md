# The country code in the hello reply

Date: 2026-11-16
Status: Proposed

## Context

The run record format required `setup.country_code`, and `build_setup` in `host/src/bolis/orchestrator.py` took that value from the `Bench` object that its caller supplied. No caller could fill it, because the host had no way to learn it.

The `hello` reply stated nine fields, and none of them was the country code. `bol_radio.c` set the country with `esp_wifi_set_country_code(CONFIG_BOL_COUNTRY_CODE, false)`, and the Kconfig entry of that setting defaults to `01` and takes any code that the call accepts. The value therefore varied from one image to the next, and only the node held it.

`host/src/bolis/sweep.py` and `host/src/bolis/cli.py` both checked a channel against the range that the code `01` allows, which is 1 to 11. Each check stated that range as a property of the default country code, so each one rested on an assumption about the image rather than on a reading from the node. A node built with another country code made the host validate the wrong range and write a country code that the radio never used.

The `bolis run` command stopped after it read the `hello` reply of both nodes. It could not write a record without that field, because the schema requires it.

`proto` version 2 held every key of the contract, and no release had shipped it. A key added before that version ships costs no rise of it, and a key added after it ships costs version 3.

If nothing was decided, the host would write a country code that it assumed, and a run on a node of another country would state a setup that the bench never had.

## Alternatives considered

- The country code in the `hello` reply, read back from the radio, which states the code that applied rather than the code that configured it.
- The country code in the `hello` reply, taken from the Kconfig macro, which states the code that the build asked for and not the one the driver holds.
- A command line option that the user types, which labels the value as declared and lets a record disagree with the radio of its own run.
- The host assuming the default country code, which is wrong for every other image and which keeps the channel check resting on that assumption.
- A key for the power save mode beside it, which spends a key on a value that the coding standard fixes for both nodes, and which the record already states as configured for the PHY rate.
- A command of its own for the setup of a node, which adds an exchange for one field that `hello` already has room for.

## Decision

The `hello` reply carries `country_code`, which is its tenth field. The node reads it with `esp_wifi_get_country_code` after the radio starts, so the reply states the code that the radio holds rather than the macro that configured it. This follows `power_set_value_read_back` of the `cell` reply, which states what the radio reports rather than what the host requested.

This amends the accepted record [2026-10-01-control-line-wire-format.md](./2026-10-01-control-line-wire-format.md), which states the nine fields of the `hello` reply. That record keeps `Status: Accepted`.

`proto` stays at version 2, because that version has not shipped.

The host takes `setup.country_code` of the run record from that field, and the value keeps the `[configured]` label, because the component set it.

The host holds no table of the channels that a country code allows, and it builds none. Such a table is data that no source of this repository states. The channel list of a plan follows the range that the default code `01` allows, and the check that the host runs while it reads the command line keeps that range, so a channel of 12 fails before a port opens.

A node refuses a channel that its own code does not allow, because `esp_wifi_set_channel` returns a code for that channel. The `cell` command answers with that code, and the run stops at that cell and names it. The authority on a channel is therefore the driver of the node rather than a table in the host.

```
@bol {"proto":2,"reply":"hello","seq":1,"ok":true,"chip":"esp32",
      "chip_revision":301,"idf_version":"v5.5.4","espnow_version":2,
      "payload_limit_bytes":1470,"bolis_version":"0.1.0",
      "firmware_path":"prebuilt","elf_sha256":"<64 hex characters>",
      "bluetooth_controller":"disabled","country_code":"01"}
```

## Consequences

- `proto` stays at version 2, and this key reaches a node inside that version.
- This record amends the field set of the wire format record. A reader of the control line contract reads that record and every record that amends it.
- The widest `hello` reply measures 365 bytes against the 512-byte limit, so the reply keeps 147 bytes.
- `setup.country_code` states the code that the radio holds, so no record states a country that its bench did not use.
- A pair of nodes built with different country codes carries two different ELF hashes, because the code reaches a node through Kconfig. `require_same_firmware` already stops such a pair, so this record adds no check of its own.
- The host keeps the range of the default code for the check it runs while it reads the command line, so a channel of 12 still fails before a port opens.
- A channel that a node refuses stops the run at that cell, with the code that the driver returned. The host states no reason of its own for that refusal, because it holds no table of the channels of a code.
- A sweep on a node whose code allows fewer channels than the default code stops at the first cell outside that range. The record of that run holds the cells that ran, which the run record format already allows through its stopped reason.
- The power save mode stays a value that the host states, because the coding standard fixes it for both nodes and no build changes it.
- `esp_wifi_get_country_code` runs after `esp_wifi_start`, so the console starts after the radio, which `bol_radio_up` already does.
- Watch the first run on a node of a country code other than the default. The channel list of the sweep follows the code, so the cell count of that run differs from the cell count of a default run.
