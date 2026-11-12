# The byte encoding of the frame header and the carrier of the run ID

Date: 2026-11-12
Status: Proposed

## Context

Thinkbook section 7 fixed the frame header at 14 bytes and named its five fields: a 2-byte magic, a 4-byte run ID, a 2-byte field that holds the cell in its low 15 bits and the pass in its top bit, a 4-byte message ID, and a 2-byte field that holds the fragment index and the fragment count. It stated that the fill after the header follows a pattern derived from the header, and that the receiver checks the header and the fill. Those names and widths were settled before this record, and this record changes none of them.

Five choices inside those widths stayed open. Section 7 stated no byte order for a multi-byte field, no magic value, no mapping from the pass bit to a pass, no split of the two bytes that hold the fragment index and the count, and no derivation for the fill. The C coding standard required one fixed byte order, and it named the header documentation as the place that states that order. MISRA C:2012 Rule 11.3 ruled out a cast from a receive buffer to a structure pointer, so every field is decoded byte by byte or copied with `memcpy`.

`components/bolis/src/bol_radio.c` held 140 lines, which brought the radio up. No sender task and no receiver task existed. The accepted record [2026-11-11-control-line-command-fields.md](./2026-11-11-control-line-command-fields.md) named the keys of the four commands and listed the counters of each pass, so the firmware held a contract for `go` and for `stats` and no frame to send.

The run ID held no carrier. Neither accepted record of the control line named a `run_id` key, and `run_id` appeared in no source file of either language. Thinkbook section 9 listed a run ID in the `run` section of the run record. Thinkbook section 7 gave the header a 4-byte run ID, to reject a frame from another run. A node therefore held a header field that no exchange filled, so the header was not implementable as stated.

If nothing was decided, the first sender task would fix the five open choices by accident. Those values bind every released image and every run that a corpus stores, and a change to one of them invalidates every stored run.

## Alternatives considered

- Little-endian fields, to match the ESP32 and the host, which saves no work because Rule 11.3 forces byte-by-byte decoding either way.
- A magic of `0x0000` or `0xFFFF`, which erased memory and a stuck line both reproduce.
- A 4-bit fragment index with a 12-bit count, which fixes a fragment range that the fragmentation work has not settled.
- A checksum field over the frame, which needs a byte that the 14-byte header does not hold.
- A pseudorandom fill, which gives the firmware a generator that the CERT baseline states it does not hold, and which adds state to every frame.
- A constant fill, which detects truncation and no change inside a frame, because every position then holds the same byte.
- A fill seed wide enough to tell every frame apart, which one byte per fill position cannot carry.
- The run ID on the `cell` command, which resends a value that holds for a whole run.
- The run ID formed on the node, such as from a boot counter, which leaves the host unable to name the run that it records.
- A fifth command for the run ID, which adds an exchange where `role` already runs once per node and per run.
- A run ID taken from a chip identifier, which puts a device identifier into a record that specification section 7 keeps free of one.
- A run ID drawn with no check against the stored records, which repeats a value that the host could have read.
- A host that checks a drawn value against the corpus, which specification section 7 rules out, because the host sends nothing off the machine of the user and a corpus holds records that other machines shared by choice.

## Decision

This record fixes five encodings inside the field widths that thinkbook section 7 settled. It amends the accepted record `2026-11-11-control-line-command-fields.md` by adding one key to the `role` command. It replaces no other statement of that record, and that record keeps `Status: Accepted`.

**Byte order.** Every multi-byte field of the frame header is big-endian, with the most significant byte first. A hex dump then reads in field order, and a hex dump is the one diagnostic that a bench holds for a corrupt frame.

**Magic.** The magic holds `0x42` and then `0x4F` `[proposal]`. The magic marks a frame as a Bolis frame, and it carries no other function. The value avoids `0x0000` and `0xFFFF`, because erased memory and a stuck line produce those patterns, and a marker that agrees with a degenerate buffer marks nothing. The pair reads as `BO` in a hex dump.

**Pass bit.** The pass bit is the most significant bit of the cell and pass field. It holds 0 for a broadcast pass and 1 for a unicast pass. Every run carries a broadcast pass, and a unicast pass follows it in a unicast run (record [2026-10-01-loss-metric-and-send-mode.md](./2026-10-01-loss-metric-and-send-mode.md)), so 0 names the pass that every run holds. The low 15 bits hold the cell, which gives the range 0 to 32767 that the command fields record states for `cell_id`.

**Fragment field.** The field holds the index in its first byte and the count in its second byte. The index counts from 0. The count holds the number of frames of the message. An even split needs no range analysis, and each byte holds 0 to 255. How many frames a message of a given size takes stays with the fragmentation work. This record requires only that a count fit one byte.

**Fill.** The fill holds every byte after the header, to the end of the frame that carries it. Its length follows the length of that frame. This record states no relation between a message and the frames that carry it. The byte at fill offset $i$ holds $f(i)$:

$$f(i) = (s + i) \bmod 256$$

$s$ is the seed of that frame:

$$s = (m + g) \bmod 256$$

$m$ is the message ID and $g$ is the fragment index, and the receiver reads both from the header of the frame it checks.

The fill detects a change to any byte of one frame, because every fill position holds one expected value once the header is read. It detects a frame shorter than the length that its header implies. It does not tell one frame from another, and this record claims no such property. A seed of one byte cannot separate every pair of a 32-bit message ID and an 8-bit fragment index, so two frames can carry an identical fill. The header tells frames apart, through the magic, the run ID, the cell and pass, the message ID, and the fragment index, and the receiver checks the header before it checks the fill. A seed taken from the header costs nothing and makes the fill of two frames differ in most cases, which this record treats as an aid rather than as a guarantee.

**The run ID.** The `role` command carries `run_id`, an unsigned integer of 32 bits. The host draws the value with `random.getrandbits(32)`, as it draws the shuffle seed, because the value needs uniqueness across runs and holds no secret. A node stores the value that its `role` command carried. A sender stamps that value into every frame it sends. A receiver rejects a frame whose run ID differs from the stored value.

A run ID is unique among the run records that the host can read. Before a run starts, the host compares the drawn value against the run IDs of the records in the directory it writes to, and it draws again on a match. That check covers what the frame header needs, because the run ID rejects a frame of a run that overlaps this one in time and place, and such a run wrote its record on this machine.

The host guarantees no more than that. Specification section 7 keeps the host offline, and a corpus holds records that users of other machines shared by choice, so no host reads a corpus. A random draw of 32 bits reaches an even chance of a repeat at about 77,000 records, from $1.177\sqrt{2^{32}}$, so a corpus large enough meets a repeat. A corpus resolves a repeat when a shared record enters it, and this record states nothing about that process.

The draw is random rather than derived from the hardware, because specification section 7 states that a record carries no device identifier that the user did not add.

`run_id` is a new key, so it reaches a node at `proto` version 2, beside the keys that the command fields record states.

## Consequences

- This record fixes the byte order, the magic, the pass bit, the fragment split, and the fill. Each one binds every released image and every run that a corpus stores, and a change to any one of them needs a new record.
- This record adds `run_id` to the `role` command, so the command fields record no longer states every key of that command. A reader of the control line contract reads both records.
- `run_id` costs no second rise of `proto`, because `proto` rises to 2 for the command fields record and that version has not shipped. A key added after version 2 ships costs version 3.
- The header holds no version field, and its 14 bytes carry no spare byte. A run record therefore names the frame encoding of its run only through the ELF SHA-256 that the node reported.
- A frame that fails the magic or the run ID counts as a foreign packet, which the command fields record lists as `foreign_packets`.
- A frame that fails the fill check, or that is shorter than the length that its header implies, counts as a corrupt packet, which the command fields record lists as `corrupt_packets`.
- The receiver reads the message ID and the fragment index before it checks the fill, because the seed comes from those two fields.
- A frame of the smallest swept payload of 14 bytes holds a header and no fill, so the fill check is empty and only the length detects truncation.
- The fill costs one addition per byte on each node. A larger fill lowers the frame rate, so the cost per second stays near the cost of the link rate rather than rising with the payload.
- The host reads the run IDs of the records in its output directory before a run starts. The run record format record states where the host writes a record, in what text form a record states a run ID, and what the host does when it cannot read that directory.
- Uniqueness across a corpus rests outside the host, because an offline host cannot see a record that another machine wrote. A corpus resolves a repeat at the point where a shared record enters it.
- How a message maps to the frames that carry it stays outside this record. The fragmentation work states it, and every encoding here holds for any mapping that work chooses.
- The magic value carries `[proposal]`, so no run rests on it yet. A later record may replace the value, and that change invalidates every image built before it.
- Watch a run whose record states an ELF SHA-256 that no release names. Such a run carries a frame encoding that no record describes.
