# The mapping of a message to the frames that carry it

Date: 2026-11-16
Status: Accepted

## Context

The frame header record fixed the byte order, the magic, the pass bit, the fragment split, and the fill of a Bolis frame. It stated that how a message maps to the frames that carry it stays outside that record, and it named the fragmentation work as the place that states it. No record stated it.

Thinkbook section 3.1 fixed the packet count of a message. A message of $p$ bytes, at a packet payload limit of $L$ bytes, takes $n(p) = \lceil p / L \rceil$ packets. `bol_stats_packets_per_message` in `components/bolis/src/bol_stats.c` already held that formula.

`ESP_NOW_MAX_DATA_LEN_V2` holds 1470, and that limit covers one whole transmission. A Bolis frame carries its 14-byte header inside that limit, so a message of 1470 bytes is one frame at the limit, and a message of 14 bytes is a header with no fill. Thinkbook section 7 stated the fill as $p - 14$ bytes, which holds for a message of one frame and states nothing for a message of more than one.

Thinkbook section 3.4 wrote the message loss as a product over the packets of a message, where $p_i$ is the payload of packet $i$. It stated no value for $p_i$.

The v2.0 payload list held 1471 and 2941 bytes, and the v1.0 list held 251 and 501 bytes. A split that fills each frame to the limit leaves a second frame of one byte for a message of 1471 bytes, and a third frame of one byte for a message of 2941 bytes. A frame of one byte cannot hold a 14-byte header, so that split carries neither size.

The sender task was the next module of the firmware, and it builds every frame of a pass. It could not build one without this mapping.

If nothing was decided, the sender would fix the frame sizes of every fragmented cell by accident, and the corpus would hold runs whose frames a later reader could not reproduce.

## Alternatives considered

- An even split of the message across its frames, which holds every frame above the header without a padding rule.
- A split that fills each frame to the limit, which leaves a frame of one byte for two sizes of the v2.0 list.
- A split that fills each frame to the limit and raises a short last frame to the header size, which puts more bytes on the air than the message holds.
- A split that fills each frame to the limit, which needs the removal of the boundary sizes that the payload sweep exists to probe.
- A frame that carries its own header beside a full share of the limit, which exceeds the length of one ESP-NOW transmission.
- A message counted without the headers of its frames, which breaks $n(p)$ of thinkbook section 3.1 and the counter that the firmware already holds.

## Decision

A message of $p$ bytes maps to $n(p)$ frames, and those frames divide $p$ as evenly as they can.

Let $n$ be $n(p)$, let $b$ be $\lfloor p / n \rfloor$, and let $r$ be $p \bmod n$. The first $r$ frames hold $b + 1$ bytes each, and the remaining $n - r$ frames hold $b$ bytes each. Each count holds the whole frame, which is the 14-byte header and the fill after it.

The sender puts the frames of one message on the air in fragment index order, starting at index 0. The `fragment_count` field of each header holds $n$.

| $p$ | $L$ | $n(p)$ | The frames |
|---|---|---|---|
| 14 | 1470 | 1 | 14 |
| 1470 | 1470 | 1 | 1470 |
| 1471 | 1470 | 2 | 736, 735 |
| 2941 | 1470 | 3 | 981, 980, 980 |
| 251 | 250 | 2 | 126, 125 |
| 501 | 250 | 3 | 167, 167, 167 |

A message of more than one frame holds $p > L (n - 1)$, so its smallest frame holds more than $L (n - 1) / n$ bytes, which is more than $L / 2$. The v1.0 limit gives a smallest frame above 125 bytes, and the v2.0 limit gives one above 735 bytes. Both sit above the 14-byte header, so this record states no padding and no minimum frame.

## Consequences

- Every frame of every payload of both lists holds its header, so this record adds no padding rule and no minimum frame size.
- The bytes of one message on the air equal $p$ exactly, so the airtime of a cell needs no correction for the frames that carry a fragmented message.
- No frame of a fragmented cell sits at the limit, so the airtime that thinkbook section 3 states for a full-size frame applies to an unfragmented cell only.
- $p_i$ of the message loss product of thinkbook section 3.4 takes these frame sizes.
- A cell at $p = 1471$ puts two frames of about half the limit on the air rather than one full frame and one short frame. The step at that boundary therefore measures the cost of a second frame rather than the cost of a short frame.
- The frame sizes of a cell bind every run that a corpus stores. A change to them needs a new record, and it makes a run of an earlier mapping incomparable with a later one.
- The receiver checks the fill to the end of each frame, so it needs no table of the expected length of a fragment.
- `bol_frame_encode` already takes the length of the frame that it writes, so this record changes no merged code.
- Thinkbook section 7 states the fill as $p - 14$ bytes. That holds for a message of one frame, and a later version of the thinkbook states the fill of a fragmented message as the frame size minus 14.
- Watch the first run for the step at $p = 1471$ and at $p = 251$. A step that this mapping does not predict states that the frame size, rather than the frame count, moved the loss of that cell.
