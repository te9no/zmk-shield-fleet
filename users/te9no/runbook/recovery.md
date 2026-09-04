# Fleet operations recovery runbook

This runbook recovers the ledger and dashboard after an interrupted rollout or
an accidental GitHub operation. The Fleet remains ledger-first: a recorded
action is not permission to edit firmware or mutate GitHub.

## Safety boundary

- Keep `rollout_enabled = false` until a user explicitly approves one named
  repository and operation. Keep `allow_external = false` for repositories not
  owned by the profile owner.
- Before any write, state the exact repository, source branch, base branch,
  commit, artifacts, and hardware gate. CI success is not hardware validation.
- Do not promote a ZMK 0.4 validation branch to the stable firmware branch by
  implication. SAA remains on the dedicated `zmk-0.4` branch; its `master`
  branch is outside the current rollout.
- Do not store credentials, local device paths, stable device identifiers, or
  raw private logs in `users/`; profile contents are published by GitHub Pages.

## Partial apply or interrupted rollout

1. Stop writes. Do not retry, force-push, merge, flash another half, or advance
   the next repository until the actual state is known.
2. Record the source commit, destination branch, completed variants, failed or
   unattempted variants, CI run, artifact names, and hardware observations.
3. Compare the remote branch head with the recorded `pr_head` and `commit`.
   Mark only observed gates `passed`; leave unobserved gates `pending`.
4. If the branch is disposable and unmerged, preserve its head as evidence and
   create a fresh recovery branch from the declared `base_branch`. Rewriting or
   deleting the old branch requires explicit approval.
5. If a commit was merged, prefer a reviewed revert PR to history rewriting.
   Never change the stable firmware branch while recovering a validation-only
   rollout unless the user explicitly names that branch.
6. Rebuild the affected matrix and repeat the hardware gates for every variant
   that may differ. Update the ledger only after the evidence exists.

## Accidental or premature PR

1. Capture the PR URL, state, base/head branches, and head SHA in the ledger.
2. Stop further comments, reviews, labels, or pushes. For an external owner,
   make no mutation until the user explicitly approves the exact response.
3. When withdrawal is approved, post the user-approved explanation, close the
   PR without merging, and retain the closed PR URL as evidence. Do not delete
   the branch unless separately approved.
4. Change the tracking status to the factual result (for example,
   `closed-unmerged` or `superseded`) and record why. A withdrawn PR is not a
   passed validation and must not unlock another rollout.

## Ledger synchronization

1. Read GitHub state without mutation: default/maintenance branch heads, open
   and closed PRs, draft state, base/head names, merge commit, and check runs.
2. Reconcile each record in this order: `status`, `branch`, `base_branch`,
   `pr_head`, `commit`, `validation`, then evidence URLs.
3. For module variants, record each variant separately. A passed variant must
   not satisfy pending siblings. Example: Polaris `right-iqs` is passed while
   `right-tb` and `right-tpd` remain pending in PR #7.
4. Re-run the Fleet audit and revision audit. Store the Fleet commit, run URL,
   measurement date/scope, and per-repository finding counts. Keep local-only
   results separate from CI totals.
5. Validate TOML and every JSON file, review the generated Pages data locally,
   and commit the ledger changes on a dedicated Fleet branch.

## GitHub Pages failure or bad publication

1. Identify the last successful Pages run and its Fleet commit. Preserve the
   failing run URL and browser symptom.
2. If only ledger data is wrong, correct or revert the data commit on a review
   branch and let the normal Pages workflow publish it. Do not manually edit
   generated output.
3. If the publishing workflow itself is broken, restore the last known-good
   workflow through a reviewed Fleet PR. Re-running or deploying is a GitHub
   mutation and requires approval.
4. Verify the public page after deployment: repository/action links, variant
   gates, stale evidence labels, and the next-action ordering.
5. If sensitive data was published, remove it from the current profile first,
   revoke any exposed credential immediately, then coordinate history/cache
   cleanup. A Pages rollback alone does not erase Git history.

## Minimum recovery evidence

- Fleet commit and Fleet Audit/Pages run URLs
- repository, `branch`, `base_branch`, and remote head SHA
- PR URL/state/draft flag or explicit `no PR`
- CI conclusion and artifact identity
- hardware variant, result, date, and public-safe evidence
- user approval for every GitHub write or external-repository interaction
