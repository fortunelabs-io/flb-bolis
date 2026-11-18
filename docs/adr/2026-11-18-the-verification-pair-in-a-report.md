# The verification pair in a report

Date: 2026-11-18
Status: Proposed

## Context

The run record format required `verification_pair_run_id` in the `run` section. The field holds the run ID of the other run of a verification pair, or null when the run belongs to no pair. The report builder never read it, so the one value of a record that bears on reproduction reached no page.

Specification section 6 listed the contents of a report in five bullets and named no reproduction status. Thinkbook section 10 listed the same sections and stated that the builder reads the run record and writes one static HTML file. Neither source said what a report does with the field.

Record `2026-10-01-reproducibility-verification.md` defined the pass test of a pair over two runs. The pair passes when the baseline loss intervals of the two runs overlap and the lists of variables that moved loss are identical. Both conditions read two records. A builder that reads one record therefore holds half of the test, and a report that stated a verdict would state one it cannot compute.

The same record put the mockup of the repository, not the report of a run, under the failure case. Specification section 6 repeated that rule. So the report carried no obligation to judge a pair, and it also carried no statement that a pair exists.

The mockup stopped being an idea while this record was a draft. `host/src/bolis/mockup.py` and `docs/mockup-report.html` reused the text and the style of `bolis.report`, so the mockup could not drift from the report that a run writes. The mockup stated the definition of a pair and the pass test in its own closing banner, which states what replaces the page. Its Coverage and limits section held the three limits of specification section 4 and named no pair. The mockup linked to no record, because no run produced it. A statement of the pair in a report therefore reaches two pages, and only one of them can carry a link.

If nothing was decided, a report would stay silent about the pair. A reader who holds a report and not the record would not learn that a second run completes the result, and the next change to the builder would settle the question by accident.

## Alternatives considered

- Omit the field, which keeps a reader of a report from learning that the run belongs to a pair.
- State the pair run ID and state that the report does not judge the pair, which separates the fact of the pair from the verdict of decision 6.
- Read both records and state whether the pair passed, which breaks the rule that the builder reads one record and fails when the second record sits elsewhere.
- Add a reproduction section that carries the verdict, which repeats the previous fault and adds a section that specification section 6 does not list.
- Link the pair to the report file `bolis-<run_id>.html` of the other run, which dangles when that report was never written.
- Link the pair to the record file `bolis-<run_id>.json` of the other run, which dangles when the two runs used different output directories.
- Place the pair in the test condition table, which mixes a fact about the strength of a claim into a list of radio and build settings.

## Decision

**The placement.** The report states the verification pair in the Coverage and limits section. That section carries the coverage and the limits of the run under specification section 6, and whether a second run completes the result is a statement about the strength of the claim. The test condition table keeps to the firmware, radio, and baseline settings of the run.

**The statement.** When `verification_pair_run_id` holds a run ID, the report states that this run belongs to a verification pair with that run. When the field holds null, the report states that this run belongs to no verification pair. A null field produces a sentence, not an empty row.

**The verdict.** The report does not state whether the pair passed. It states that the pass test of `2026-10-01-reproducibility-verification.md` reads both runs of the pair, and that this report reads one record.

**The label.** The pair run ID carries no origin label. The run record format states that a run ID names a run rather than stating a quantity of it, so it carries no label, and the pair run ID is a run ID.

**The link.** The pair run ID links to `bolis-<run_id>.json` of this run, with the fragment `/run/verification_pair_run_id`, which follows the record link of `2026-11-16-the-drift-band-and-the-record-link-of-a-report.md`. The report carries no link to the record or the report of the other run.

## Consequences

- A reader of a report alone learns whether the run belongs to a pair and which run completes it.
- A report never calls a result reproduced, so it cannot overstate the claim limit of specification section 4.
- The pass test stays with a reader who holds both records, and the mockup of the repository stays the artifact that waits for a pair.
- The builder keeps reading one record, so a report needs no second file to exist.
- A null field prints a sentence, so a reader cannot read silence as a pair.
- The pair run ID carries no origin label, which keeps the legend of the four labels to the quantities of a run.
- The link names a key of this record, so it resolves whenever the report and its record sit together.
- A reader who wants to check a pair finds the other record by its run ID and not by a link.
- The mockup reuses the text of a report, so a statement of the pair reaches the mockup as a placeholder.
- The placeholder of the mockup carries no record link, because no run produced that page.
- The mockup states the pair twice, once as a placeholder in Coverage and limits and once in the banner that states what replaces the page.
- Watch a report whose pair run ID names a run whose record the user no longer holds. The report states the ID, and the reader cannot reach the second half of the test.
