# Broadcast first-attempt loss as the base metric, with a unicast pass for unicast applications

Date: 2026-10-01
Status: Accepted

## Context

The Bolis v0 specification (v0.3) promised a report that shows which variable moves frame loss, but it did not define frame loss. The Bolis thinkbook (section 2) showed that ESP-NOW exposes three different quantities: first-attempt loss, post-retry loss, and message loss. Broadcast frames carry no acknowledgement and no retransmission, so a broadcast cell exposes first-attempt loss directly. A 2025 study observed up to 31 retransmissions of one unicast frame, so post-retry loss stays near zero until the link almost fails, and the retry load then appears only in the send-to-callback time. The run record also feeds the shared corpus (Loop A), so the chosen quantity sets what records from different users and chips can be compared on. If nothing was decided, a user of a unicast application could receive a flat chart and a report paragraph that names no variable while the link degrades.

## Alternatives considered

- Send every cell in broadcast only, and report first-attempt loss.
- Send every cell in unicast only, and report post-retry loss.
- Send every cell in both modes for every user, and report both quantities.
- Send every cell in broadcast, and add a unicast pass of every cell when the user's application uses unicast.

## Decision

Every run sends each cell in broadcast mode. Broadcast first-attempt loss is the base metric of every run. The corpus compares runs on this metric. The run mode defaults to broadcast. If the user's application uses unicast, the user sets the run mode to unicast. In a unicast run, each cell runs a unicast pass after its broadcast pass. For each unicast pass, the report adds post-retry loss and the send-to-callback time histogram. Each chart states its mode and its loss quantity.

## Consequences

- Every record carries one metric that compares across users and chips, because broadcast first-attempt loss does not depend on the retry limit of a driver.
- A unicast run sends twice the frames of a broadcast run and takes about twice as long.
- The default plan of a unicast run sends about 144,000 frames.
- The long-run guard in thinkbook section 8 becomes required, because a public issue reports a send failure near 78,000 broadcast frames on one ESP-IDF v5.x build.
- The report builder holds two chart paths, one per mode.
- This rules out a run without broadcast cells.
- Unicast numbers stay outside the corpus metric, because the retry limit differs by chip.
- Watch for users who read broadcast loss as the loss that their unicast application sees.
- The run record format, a reused asset that feeds the corpus, gains a mode field per cell and a field for each loss quantity.
- A later change of the corpus metric requires a new ADR and a new version of the run record format.
- Specification section 4 names the loss quantity and the run mode in v0.4.
