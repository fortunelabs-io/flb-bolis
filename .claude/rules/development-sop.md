# Development SOP

This procedure governs every change to the repository. Claude follows it for each task. The founder approves every merge and every release.

## 1. Scope the change

1. Name the specification section, the thinkbook section, or the decision record that the change implements.
2. If no source covers the change, ask before writing code.
3. Run the ADR test in `decision-records.md`.
4. If the change needs an ADR, draft the ADR first.
5. Do not write the code of that change until the founder accepts the ADR.

## 2. Branch

1. Create a branch from `main`.
2. Name the branch `<type>/<slug>`. The type is `feature`, `fix`, `docs`, `ci`, or `chore`. The slug is lowercase words joined by hyphens.
3. Keep one decision per branch.

## 3. Write

1. Follow the rule file of each language you change.
2. Add or update tests in the same change.
3. Update the Doxygen blocks and the docstrings in the same change.
4. If a C change needs a MISRA deviation, write the deviation record in the same change (`c/misra-c-2012.md`).
5. If a change adds a dependency to the firmware component, stop. A new dependency changes the adopted code in scope, so it needs an ADR.

## 4. Verify

1. Run every check in `CLAUDE.md` that applies to the changed files.
2. For a C change, follow `skills/c-compliance-check/SKILL.md`.
3. Report each check with its result.
4. If a check cannot run, name the check and the reason.
5. Never report a check as passed if it did not run.

## 5. Commit

1. Stage only the files of this change. Name each path in `git add`.
2. Write the commit message as `pull-requests.md` states.
3. Never use `--no-verify`.
4. Never amend, rebase, or force-push a commit that another branch or person can already see.
5. Never change the git configuration.
6. Never commit a secret, a credential, a standard document, a build output, or `.claude/`.
7. If a hook fails, fix the cause. Do not bypass the hook.

## 6. Pull request

1. Push the branch.
2. Open the PR with the title and the body that `pull-requests.md` states.
3. Do not open the PR while a required check fails.
4. Do not merge. The founder reviews and merges.

## 7. Review

When the founder asks for a review of a PR:

1. Check the PR body against the six fields in `pull-requests.md`.
2. Run the checks in section 4 on the PR branch.
3. Check each changed file against the rule file of its language.
4. Report each finding with the file, the line, the rule or guideline, and a proposed fix.
5. Report findings only. Do not push fixes to the PR unless the founder asks.

## 8. Release

1. Release only from `main`, with a tag `vMAJOR.MINOR.PATCH` that follows Semantic Versioning.
2. CI builds each firmware image from the tag on ESP-IDF v5.5.x (decision 7).
3. The GitHub release carries each image, the hash of each image, and the ELF SHA-256 that each image reports in `hello` (thinkbook section 11).
4. The PyPI package and the ESP Component Registry component carry the version of the tag.
5. If release notes quote a result as reproduced, the result needs a verification pair that passed (decision 6).
6. Never publish a release without the approval of the founder.
