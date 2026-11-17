# The drift band and the record link of a report

Date: 2026-11-16
Status: Accepted

## Context

The report builder was the last module of the host. Thinkbook section 10 stated its sections, and specification section 6 stated the same list in fewer words. Both were detailed enough to build from, and three choices inside them appeared in no source.

Thinkbook section 8 stated the drift band in one sentence: the baseline cell repeats after every 5 cells, and the spread of these repeats forms the drift band. The loss quantities record added that the band reads `first_attempt_loss` of the repeated baseline cells. Neither source stated what the spread of those repeats is.

The word carried two readings, and section 10 used both. The rule for "moved loss" stated that a variable moved loss when two of its cells hold Wilson intervals that do not overlap and their difference exceeds the drift band, which reads the band as one width. The chart list stated that the drift band shows as a shaded range, which reads the band as an interval. A width and an interval are not the same object, and the rule needs the width.

That rule decides which variables a report names, so the definition of the band changes the conclusion of a run. Thinkbook section 10 called the rule mechanical, so that two readers of one record reach the same paragraph. Two readers who read the spread differently reach different paragraphs.

Specification section 6 asked for an origin label and a link to the run record beside every number. The record is a separate file of JSON, so a link into it needs a form, and no source stated one.

The record of a run took the name `bolis-<run_id>.json` from `record_path` in `host/src/bolis/record.py`. No source named the report file.

If nothing was decided, the first report would fix the drift band, and therefore the conclusion of every run that a corpus stores, by accident.

## Alternatives considered

- The drift band as the difference between the highest and the lowest ratio of the baseline repeats, which states the spread that the run observed.
- The drift band as the difference between the highest interval edge and the lowest interval edge of those repeats, which adds the sampling error of the baseline to a rule that already tests the intervals of the two cells it compares.
- The drift band as a standard deviation of the repeats, which rests on a distribution that no source of this repository states and which a count of six repeats estimates poorly.
- A link that names the record file alone, which leaves a reader of a report to find the number by hand.
- A link that carries a JSON Pointer to the key of the number, which names the exact key and which a browser does not resolve inside a file of JSON.
- A report that embeds the whole record, which drops the link and doubles every number of a run inside one file.

## Decision

**The drift band.** The drift band of one pass is a width. It is the difference between the highest `ratio` and the lowest `ratio` of `first_attempt_loss` across the valid baseline cells of that pass. A pass with fewer than two valid baseline cells has a drift band of 0.

A chart shows the band as a shaded range from the lowest of those ratios to the highest, which is the same two numbers that the width comes from. The rule for "moved loss" uses the width.

**The rule for moved loss.** A variable moved loss when two of its valid cells in one pass hold Wilson intervals that do not overlap and the difference between their ratios exceeds the drift band of that pass. Both tests read the record and nothing else, so two readers of one record name the same variables.

**The record link.** A number in a report links to `bolis-<run_id>.json`, with a fragment that holds the JSON Pointer of the key that states it, as in `bolis-7.json#/cells/3/first_attempt_loss/ratio`. The report sits beside the record, so the link is relative and needs no path of the machine that wrote it. A browser opens the record and does not resolve the fragment inside it, so the fragment serves a reader who looks the key up and a tool that follows it.

**The report file.** The report of a run takes the name `bolis-<run_id>.html`, beside the record of that run and in the directory that `--out` names.

## Consequences

- The drift band reads the ratios of the baseline repeats, so it states the spread that the run observed and adds no sampling error of its own.
- The rule for moved loss tests the intervals of two cells and then the width of the band, so a difference inside the drift of the bench names no variable.
- A pass of fewer than two valid baseline cells falls back to the interval test alone, because its band is 0. The default plan holds six baseline cells, so a run reaches that case only when the bench invalidated most of them.
- The definition of the band binds every report that a corpus publishes. A change to it changes which variables a report names, so it needs a new record and makes the paragraph of an earlier run incomparable with a later one.
- A report names a variable only from the record, so a reader who holds the record reproduces the paragraph without the report.
- The link carries a JSON Pointer that a browser does not follow. A reader of a report therefore reaches the file and then the key, rather than the key directly.
- The report and the record share one directory and one stem, so a user who copies a pair keeps both.
- A run that stops early writes a report of the cells that ran, because the record of that run already holds them and states why it stopped.
- Watch the first bench run for a drift band wider than the difference between two cells of every variable. Such a run names no variable, and the band rather than the link is what the report then needs to explain.
