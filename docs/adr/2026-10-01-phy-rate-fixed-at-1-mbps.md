# PHY rate fixed at 1 Mbps for Bolis v0

Date: 2026-10-01
Status: Accepted

## Context

The default bit rate of ESP-NOW is 1 Mbps, and a 2025 study observed 802.11b frames at that rate. The rate sets the airtime of a frame and the sensitivity of the receiver, so loss measured at one rate does not compare with loss measured at another rate. The base metric from [2026-10-01-loss-metric-and-send-mode.md](./2026-10-01-loss-metric-and-send-mode.md) feeds the corpus, so records compare only when they share a rate. From ESP-IDF v5.2, a user can change the rate per peer with `esp_now_set_peer_rate_config`, but the rate cannot be read back. Nobody had verified whether the per-peer rate setting applies to the broadcast peer. The v0 specification (v0.3) sweeps three variables, and the rate is not one of them. If nothing was decided, the rate of a run would depend on driver defaults and on code outside Bolis, and the record would not state which rate applied.

## Alternatives considered

- Fix the rate at 1 Mbps for every pass of every run.
- Let the user pick one rate for a whole run, and record it.
- Sweep the rate as a fourth variable.
- Run a base pass at 1 Mbps, and add a pass at the rate of the user's application when that rate differs.

## Decision

Every pass of every v0 run sends at 1 Mbps. The component sets 1 Mbps for every peer it adds. The run record states the rate as a configured value. The report states that its results apply to 1 Mbps. A run setting for the rate waits for a later version.

## Consequences

- Every v0 record compares with every other v0 record on rate.
- The sweep keeps the three variables of the specification.
- A user whose application sends at another rate receives results that do not describe that rate.
- The report states the 1 Mbps limit next to the claim-limit sentence.
- A frame with a 1470-byte payload takes about 12.6 ms of airtime, so v2.0 payload cells take longer than other cells.
- The bench spike checks whether `esp_now_set_peer_rate_config` applies to the broadcast peer.
- A run setting for the rate needs that check, a new ADR, and a rate field in the corpus grouping.
- The run record format carries a rate field from v0, so records at other rates stay separable from v0 records later.
- Specification section 4 states the fixed rate in v0.4.
