# Local one-variable-at-a-time sweep around the user's configuration

Date: 2026-10-01
Status: Accepted

## Context

The Bolis v0 specification (v0.3) sweeps three variables: channel, payload size, and transmit power. It did not fix how the sweep combines them. Varying one variable at a time around a baseline needs about 36 cells and about 4 minutes of broadcast sending. A full grid needs 968 cells, about 1.7 hours per broadcast pass, and about 1.9 million frames per pass. A literature review on 2026-10-01 tested this tradeoff. The literature on designed experiments shows that factorial designs estimate effects with less variance per run and detect interactions, which a one-variable-at-a-time design cannot do (Czitrom 1999). An adaptive one-variable-at-a-time design can outperform fractional designs for improvement when experimental error is small and interactions are strong, but Bolis describes behavior and does not optimize it (Frey, Engelhardt, and Greitzer 2003). The literature on wireless links shows that the interactions exist. Packet loss grows with packet size at a rate that depends on the channel condition (Korhonen and Wang 2005). Small changes of transmit power or receiver position swing delivery inside a transitional region and leave it unchanged outside that region (Son, Krishnamachari, and Heidemann 2004; Zhao and Govindan 2003). A one-variable-at-a-time sweep therefore yields conclusions that hold only at its baseline. The claim limit of the specification asks how the user's own configuration behaves, which is a local question. If nothing was decided, a report could state that a variable does not move loss while its baseline sat outside the transitional region.

## Alternatives considered

- Vary one variable at a time around the user's configuration.
- Vary one variable at a time around a fixed baseline that Bolis defines.
- Measure the full grid of all three variables.
- Use a fractional design, such as a two-level factorial or a Latin hypercube.
- Sweep transmit power first, then sweep channel and payload size at a power inside the transitional region.

## Decision

The default sweep varies one variable at a time around a baseline. The baseline is the user's configuration of channel, transmit power, and payload size. If the user gives no configuration, Bolis uses a fallback baseline of channel 1, transmit power set value 44 (11 dBm), and a payload of 128 bytes. The full grid is an option that the user selects. Each cell sends 2000 frames per pass. The host shuffles the cells with a recorded seed. The baseline cell repeats after every 5 cells to measure drift. The report states that its conclusions hold at the baseline. The report states that the sweep does not test interactions.

## Consequences

- A default run has about 36 cells per pass.
- The report answers which single change moves loss near the user's configuration.
- The report does not answer whether two variables act together.
- A baseline in a strong-signal region can show no variable that moves loss.
- The report shows the baseline loss next to its paragraph, so a reader can recognize that case.
- At 5% loss, 2000 frames give a 95% interval half-width under 1 percentage point if losses are independent.
- On a bursty link, the Wilson intervals can be too narrow, because most 802.11b links lose packets independently only below about 0.1 s (Aguayo et al. 2004).
- The loss run-length histogram of each cell flags a bursty link.
- The full grid needs the long-run guard of thinkbook section 8 on every pass.
- A power-first adaptive sweep stays a candidate for a later version.
- That candidate needs a new ADR, because it moves the baseline away from the user's configuration.
- The run record format gains a field that states whether the baseline came from the user or from the fallback.
- Specification section 4 and thinkbook section 8 state this sweep plan in their next versions.
