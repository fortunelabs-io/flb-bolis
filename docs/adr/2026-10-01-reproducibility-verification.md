# Reproducibility verification by re-placing the nodes on a later day

Date: 2026-10-01
Status: Accepted

## Context

The Bolis v0 specification (v0.3) allowed the repository to show a real report only after a run clears reproducibility verification, but it did not define the verification. Section 8.3 of the specification also required one reproduced result in each public reply. The literature reviewed for the sweep plan showed that packet reception in the transitional region varies over time, including between day and night (Son, Krishnamachari, and Heidemann 2004; Zhao and Govindan 2003). The same literature showed that moving a receiver by less than 2 meters changes delivery sharply. Two runs started back to back with untouched nodes would almost always agree, and their agreement would show only that the bench did not change within minutes. If nothing was decided, Fortune Labs could call a result reproduced without any test that a third party would face.

## Alternatives considered

- Run twice back to back on the same bench, without touching the nodes.
- Run twice on different days, without touching the nodes.
- Run twice on different days, and remove and place the nodes again between the runs according to the declared geometry.
- Require a reproduction by a third party before a real report appears.

## Decision

A result counts as reproduced when a verification pair of two runs passes. Both runs use the same bench and the same declared geometry. Between the runs, the founder removes both nodes and places them again according to the declared geometry. The second run starts on a later calendar day than the first run. The pair passes when two conditions hold. The baseline loss intervals of the two runs overlap. The lists of variables that moved loss are identical. This definition applies to the sample report in the repository and to every result that a public reply calls reproduced. If the pair fails, the mockup stays in place. A failed pair is published as a log entry in the same form as any other entry.

## Consequences

- A verification takes at least two calendar days.
- A pass shows that the declared geometry is enough to rebuild the result on the same bench.
- A pass does not show that the result holds on other hardware or at another site.
- Overlapping intervals are a weak test of equality, so the identical list of variables carries most of the test.
- A failed pair can expose a geometry field that the run record lacks.
- Reproduction by a third party stays a separate result event under specification section 8.6.
- The run record format gains a field that links the two runs of a verification pair.
- Specification sections 6 and 8.3 and thinkbook section 10 refer to this definition in their next versions.
