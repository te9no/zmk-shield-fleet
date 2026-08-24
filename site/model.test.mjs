import assert from "node:assert/strict";
import test from "node:test";

import {
  actionEvidence,
  branchSummary,
  changeCounts,
  scopeLabel,
  selectStartAction,
  targetComplete,
} from "./model.js";

test("completion requires a terminal status and only passed or waived checks", () => {
  const cases = [
    [{ status: "merged", validation: { ci: "passed", hardware: "waived" } }, true],
    [{ status: "merged", validation: { ci: "failed" } }, false],
    [{ status: "merged", validation: { ci: "pending" } }, false],
    [{ status: "pr-open", validation: { ci: "passed" } }, false],
    [{ status: "not-applicable", validation: {} }, true],
  ];
  for (const [target, expected] of cases) assert.equal(targetComplete(target), expected);
});

test("scope labels distinguish single, explicit, all, and module scopes", () => {
  assert.equal(scopeLabel({ kind: "single", repositories: ["one"] }), "single repository: one");
  assert.equal(scopeLabel({ kind: "explicit", repositories: ["one", "two"] }), "explicit scope: 2 repositories");
  assert.equal(scopeLabel({ kind: "all" }), "all repositories");
  assert.equal(scopeLabel({ kind: "module", module: "trackball" }), "module: trackball");
});

test("start action is the first actionable entry by explicit order", () => {
  const actions = [
    { id: "blocked", order: 1, state: "waiting" },
    { id: "later", order: 3, state: "later" },
    { id: "start", order: 2, state: "active" },
  ];
  assert.equal(selectStartAction(actions).id, "start");
});

test("counts do not treat failed validation as complete", () => {
  const change = { tracking: {
    one: { status: "merged", validation: { ci: "passed" } },
    two: { status: "merged", validation: { ci: "failed" } },
  } };
  assert.deepEqual(changeCounts(change), { complete: 1, total: 2, incomplete: 1 });
});

test("action evidence exposes every requested validation URL", () => {
  const profile = { changes: [{ id: "cdc", tracking: { board: {
    validation: { ci: "passed", hardware: "pending" },
    validation_urls: { ci: "https://example.test/ci", hardware: "https://example.test/hardware" },
  } } }] };
  const evidence = actionEvidence(profile, {
    repository: "board", change_id: "cdc", validation_keys: ["ci", "hardware"], evidence: [],
  });
  assert.deepEqual(evidence.map((item) => item.url), ["https://example.test/ci", "https://example.test/hardware"]);
});

test("action evidence accepts the ledger contract's URL string list", () => {
  const evidence = actionEvidence({ changes: [] }, {
    evidence: ["https://example.test/one", "https://example.test/two"],
  });
  assert.deepEqual(evidence.map((item) => item.url), ["https://example.test/one", "https://example.test/two"]);
  assert.deepEqual(evidence.map((item) => item.label), ["Action evidence 1", "Action evidence 2"]);
});

test("action evidence preserves labeled object entries including info status", () => {
  const source = { label: "Design note", status: "info", url: "https://example.test/note" };
  const [evidence] = actionEvidence({ changes: [] }, { evidence: [source] });
  assert.deepEqual(evidence, { ...source, source: "action" });
});

test("action evidence includes every selected variant gate and evidence URL", () => {
  const profile = { changes: [{ id: "driver", tracking: { board: {
    validation: {}, validation_urls: {}, variants: [
      { id: "left", status: "passed", validation: { build: "passed" }, evidence: [{ label: "Left CI", status: "passed", url: "https://example.test/left" }] },
      { id: "right", status: "pending", validation: { hardware: "pending" }, evidence: [{ label: "Right log", status: "info", url: "https://example.test/right" }] },
    ],
  } } }] };
  const evidence = actionEvidence(profile, {
    repository: "board", change_id: "driver", validation_keys: [], variant_ids: ["right"], evidence: [],
  });
  assert.deepEqual(evidence.map((item) => item.label), ["right: hardware", "Right log"]);
  assert.equal(evidence[1].url, "https://example.test/right");
});

test("branch summary calls out work not reflected on the stable default branch", () => {
  assert.deepEqual(
    branchSummary(
      { default_branch: "main", maintenance_branch: "zmk-0.4" },
      { branch: "feature/cdc", base_branch: "zmk-0.4" },
    ),
    { branch: "feature/cdc", base: "zmk-0.4", stable: "main", stableUnreflected: true },
  );
});
