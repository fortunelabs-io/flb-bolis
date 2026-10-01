# Writing standard

These rules apply to every English text in the repository: Markdown documents, code comments, Doxygen blocks, docstrings, commit messages, PR bodies, CLI messages, and report text. They follow the Fortune Labs writing standard. The reader is an engineer who reads English as a second or third language, or a tool that parses the text with no author to ask.

## Vocabulary

- Use one term per concept, and reuse it. Do not switch between synonyms for the same concept.
- Use the Bolis terms as the thinkbook defines them: frame, packet, message, cell, pass, run, run record, report, node, sender, receiver, host, and baseline.
- Prefer the short, common word. Keep an established technical term, such as checksum or RSSI.
- State an action with its verb. Write "the host validates the line", not "the host performs validation of the line".
- Do not use a phrasal verb whose meaning does not follow from its parts. Write "configure", "execute", and "investigate", not "set up", "carry out", and "look into".

## Sentences

- Write one instruction per procedural sentence.
- Keep a subject next to its verb, a modal verb next to its main verb, and a preposition next to its object.
- Put a condition before the instruction it governs. Write "If the line is longer than the limit, reject it."
- Use the active voice and the present tense. Use the past tense only to recount a completed decision or event.
- Do not use an idiom or a cultural reference.

## Mechanics

- Use sentence case in headings.
- Use a serial comma in a list of three or more items.
- Use standard American spelling.
- Do not use contractions.
- Do not write "please".
- Never write an em dash. Use a period, a comma, a colon, or a new sentence.
- Use a colon only before a list, a definition, or one elaboration.

## Words to remove

Remove these words and constructions, or replace them with a plain statement:

- Persuasion: clearly, obviously, crucially, it is important to note, powerful, robust, seamless, elegant, simply, and of course.
- Hedges and intensifiers: arguably, essentially, quite, very, and really.
- Padding: in order to (write "to"), a number of (write a count or "several"), that being said, at the end of the day, when it comes to, and in the context of.
- Contrast scaffolding: "not only ... but also", "it is not X, it is Y", and "while some may think".

## Numbers, units, and labels

- State the unit with every quantity. Transmit power set values are in units of 0.25 dBm.
- In a run record, a report, or a public reply that quotes a Bolis number, label every number `[measured]`, `[configured]`, `[derived]`, or `[declared]` (decision 5).
- In a PR body, label every number `[borrowed: <source>]` or `[measured: <run or link>]` (see `pull-requests.md`).
- In a Fortune Labs document, a design choice that no run has confirmed carries `[proposal]`.
- Never blend numbers of different origins into one figure without the derivation.

## Formulas

- In Markdown, write formulas in LaTeX notation: `$...$` inline and `$$...$$` for a display formula, as in thinkbook v0.2.
- In code comments and docstrings, write formulas in plain ASCII, such as `n(p) = ceil(p / L)`.
