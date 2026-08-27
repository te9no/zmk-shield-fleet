import assert from "node:assert/strict";
import test from "node:test";

import {
  actionEvidence,
  branchSummary,
  buildAuditRequest,
  changeCounts,
  copyAuditRequest,
  evidenceCounts,
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

function auditFixture() {
  return {
    id: "alice",
    repositories: [{ id: "board", github: "alice/board", maintenance_branch: "not-a-recorded-target-branch" },
      { id: "other", github: "alice/other" }],
    changes: [{ id: "driver", title: "ドライバ対応", source: { repository: "upstream/driver" }, tracking: {
      board: { status: "applied", branch: "old-validation", commit: "old-source-sha",
        pr: "https://github.com/alice/board/pull/1",
        validation: { ci: "pending", hardware: "failed", build: "passed", waived: "waived" },
        variants: [{ id: "left", status: "pending", validation: { leftInput: "pending" } },
          { id: "right", status: "failed", validation: { rightInput: "failed" } }],
      },
      other: { branch: "OTHER-BRANCH", commit: "OTHER-COMMIT", validation: { OTHER: "failed" } },
    } }],
    next_actions: [{ id: "check-right", repository: "board", change_id: "driver", action: "右を確認",
      validation_keys: ["hardware"], variant_ids: ["right"] }],
  };
}

test("audit request identifies one cell and clearly labels old references and unverified gates", () => {
  const text = buildAuditRequest({ profile: auditFixture(), changeId: "driver", repositoryId: "board",
    sourceCommit: "dashboard-sha", generatedAt: "2026-08-27T00:00:00Z" });
  assert.ok(text.startsWith("boardの「ドライバ対応」について対応したので、確認してください。"));
  for (const part of ["Profile: alice", "Change ID: driver", "https://github.com/alice/board", "dashboard-sha",
    "2026-08-27T00:00:00Z", "参考旧値", "branch: old-validation", "commit: old-source-sha",
    "ci (pending)", "hardware (failed)", "variant right: rightInput (failed)",
    "コード・ビルド・実機結果を区別", "未確認は保留", "監査と台帳更新のみ",
    "修正・書き込み・マージ・他者へのPR作成は行わない", "他repositoryへ横展開しない"]) assert.ok(text.includes(part), part);
  assert.ok(!text.includes("build (passed)"));
  assert.ok(!text.includes("waived (waived)"));
});

test("audit request handles missing fields without guessing revisions or latest source", () => {
  const text = buildAuditRequest();
  assert.ok(text.includes("台帳スナップショット: 不明"));
  assert.ok(text.includes("branch: 未記録\ncommit: 未記録"));
  assert.ok(text.includes("Repository URL: 未記録"));
  assert.ok(!/undefined|null|https:\/\//.test(text));
  const fixture = auditFixture();
  fixture.changes[0].tracking.board = {};
  assert.ok(!buildAuditRequest({ profile: fixture, changeId: "driver", repositoryId: "board" }).includes("not-a-recorded-target-branch"));
});

test("unknown repository does not reuse change source or another repository's evidence", () => {
  const text = buildAuditRequest({ profile: auditFixture(), changeId: "driver", repositoryId: "unknown" });
  assert.ok(text.includes("対象セルは未登録"));
  for (const forbidden of ["upstream/driver", "alice/board", "old-source-sha", "OTHER", "hardware (failed)"]) assert.ok(!text.includes(forbidden), forbidden);
});

test("audit request only includes the chosen action gates and variants", () => {
  const text = buildAuditRequest({ profile: auditFixture(), actionId: "check-right" });
  assert.ok(text.includes("Next action ID: check-right"));
  assert.ok(text.includes("hardware (failed)"));
  assert.ok(text.includes("variant right:"));
  assert.ok(!text.includes("ci (pending)"));
  assert.ok(!text.includes("variant left:"));
});

test("explicit repository never imports a mismatched action's metadata", () => {
  const fixture = auditFixture();
  fixture.next_actions[0].repository_url = "https://example.test/wrong-repository";
  const text = buildAuditRequest({ profile: fixture, repositoryId: "unknown", changeId: "driver", actionId: "check-right" });
  assert.ok(!text.includes("wrong-repository"));
  assert.ok(!text.includes("Next action ID"));
});

test("selected repository remains isolated even when another target is failed", () => {
  const text = buildAuditRequest({ profile: auditFixture(), changeId: "driver", repositoryId: "board" });
  for (const forbidden of ["OTHER", "alice/other", "upstream/driver"]) assert.ok(!text.includes(forbidden), forbidden);
});

test("prompt generation is deterministic and does not mutate a deeply frozen ledger", () => {
  const fixture = auditFixture();
  const before = JSON.stringify(fixture);
  function freeze(value) { Object.values(value).filter((item) => item && typeof item === "object").forEach(freeze); return Object.freeze(value); }
  freeze(fixture);
  const options = { profile: fixture, changeId: "driver", repositoryId: "board" };
  assert.equal(buildAuditRequest(options), buildAuditRequest(options));
  assert.equal(JSON.stringify(fixture), before);
});

test("free text is preserved as unverified plain text without losing the final scope boundary", () => {
  const details = '<script>alert("x")</script> & 100%\n実機確認: 未実施';
  const text = buildAuditRequest({ profile: auditFixture(), changeId: "driver", repositoryId: "board", details });
  assert.ok(text.includes(`利用者の対応メモ（未検証・参考情報）:\n${details}`));
  assert.ok(text.lastIndexOf("依頼範囲:") > text.indexOf(details));
});

test("long pending lists are bounded and explicitly disclose omissions", () => {
  const fixture = auditFixture();
  const target = fixture.changes[0].tracking.board;
  target.validation = Object.fromEntries(Array.from({ length: 12 }, (_, i) => [`gate${i}`, "pending"]));
  target.variants = Object.fromEntries(Array.from({ length: 6 }, (_, i) => [`variant${i}`, { status: "pending", validation: target.validation }]));
  const text = buildAuditRequest({ profile: fixture, changeId: "driver", repositoryId: "board" });
  assert.ok(text.includes("ほか4件（台帳で確認）"));
  assert.ok(text.includes("ほか8件（台帳で確認）"));
  assert.ok(text.includes("ほか2 variants"));
  assert.equal((text.match(/^variant /gm) ?? []).length, 4);
});

test("failed variants without validation fields remain visible", () => {
  const fixture = auditFixture();
  fixture.changes[0].tracking.board.variants = { failedSide: { status: "failed" } };
  const text = buildAuditRequest({ profile: fixture, changeId: "driver", repositoryId: "board" });
  assert.ok(text.includes("variant failedSide: failed（詳細未記録）"));
});

test("adjacent action without a change ID keeps its identity but rejects unsafe URLs", () => {
  const profile = { id: "alice", next_actions: [{ id: "adjacent", repository: "alice/module", action: "モジュールを確認", repository_url: "https://github.com/alice/module" }] };
  const options = { profile, actionId: "adjacent" };
  assert.ok(buildAuditRequest(options).includes("alice/moduleの「モジュールを確認」"));
  assert.ok(buildAuditRequest(options).includes("https://github.com/alice/module"));
  profile.next_actions[0].repository_url = "javascript:alert(1)";
  assert.ok(!buildAuditRequest(options).includes("javascript:"));
});

test("clipboard success awaits the actual write and preserves edited text", async () => {
  let finish;
  let copied;
  let done = false;
  const promise = copyAuditRequest("編集済み\n依頼文", { writeText(text) { copied = text; return new Promise((resolve) => { finish = resolve; }); } });
  promise.then(() => { done = true; });
  await Promise.resolve();
  assert.equal(done, false);
  finish();
  assert.equal(await promise, true);
  assert.equal(copied, "編集済み\n依頼文");
});

test("clipboard rejection and synchronous failure never report success", async () => {
  assert.equal(await copyAuditRequest("request", { writeText: async () => { throw new Error("denied"); } }), false);
  assert.equal(await copyAuditRequest("request", { writeText() { throw new Error("blocked"); } }), false);
});

test("unsupported clipboard never reports success", async () => {
  for (const clipboard of [undefined, null, {}, { writeText: true }]) assert.equal(await copyAuditRequest("request", clipboard), false);
});

test("evidence summary counts each displayed status accurately", () => {
  const statuses = ["failed", "pending", "passed", "waived", "failed", "pending", "info", "evidence"];
  assert.deepEqual(evidenceCounts(statuses.map((status) => ({ status }))), {
    total: 8, failed: 2, pending: 2, passed: 1, waived: 1, reference: 2,
  });
});

test("unknown evidence statuses are reference, never silently passed", () => {
  assert.deepEqual(evidenceCounts([{ status: "unknown" }, { status: "PASSED" }, { status: "__proto__" }]), {
    total: 3, failed: 0, pending: 0, passed: 0, waived: 0, reference: 3,
  });
});

test("missing evidence status matches the renderer's pending fallback", () => {
  assert.deepEqual(evidenceCounts([{}, { status: "" }, { status: null }]), {
    total: 3, failed: 0, pending: 3, passed: 0, waived: 0, reference: 0,
  });
});

test("empty or missing evidence lists have zero counts", () => {
  for (const entries of [[], undefined, null]) assert.deepEqual(evidenceCounts(entries), {
    total: 0, failed: 0, pending: 0, passed: 0, waived: 0, reference: 0,
  });
});

test("evidence counting does not mutate, drop or deduplicate displayed links", () => {
  const entries = Object.freeze([
    Object.freeze({ label: "CI", status: "passed", url: "https://example.test/ci" }),
    Object.freeze({ label: "CI", status: "passed", url: "https://example.test/ci" }),
    Object.freeze({ label: "Board log", status: "pending", url: "https://example.test/log" }),
  ]);
  const before = JSON.stringify(entries);
  const counts = evidenceCounts(entries);
  assert.equal(counts.total, 3);
  assert.equal(counts.passed, 2);
  assert.equal(JSON.stringify(entries), before);
  assert.deepEqual(entries.map((entry) => entry.url), ["https://example.test/ci", "https://example.test/ci", "https://example.test/log"]);
});
