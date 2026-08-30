import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";

import { targetComplete, targetNeedsAction } from "../site/model.js";
import { PAGE_SIZE, VIEWS, paginate, routeForHash } from "../site/navigation.js";

test("dashboard views default to the queue and preserve all section links", () => {
  assert.deepEqual(routeForHash(""), { view: "next-actions" });
  assert.deepEqual(routeForHash("#top"), { view: "next-actions" });
  assert.deepEqual(routeForHash("#%invalid"), { view: "next-actions" });
  for (const view of VIEWS) assert.equal(routeForHash(`#${view}`).view, view);
});

test("each navigation destination has a matching accessible view in the HTML", () => {
  const html = readFileSync(new URL("../site/index.html", import.meta.url), "utf8");
  for (const view of VIEWS) {
    assert.ok(html.includes(`href="#${view}" data-view-link="${view}"`));
    assert.match(html, new RegExp(`id="${view}" data-view="${view}" aria-labelledby="[^"]+"`));
  }
  assert.ok(html.includes('data-action-filter="active" aria-pressed="true"'));
});

test("existing action and desktop/mobile repository deep links resolve", () => {
  assert.deepEqual(routeForHash("#action-cornix-madula-test"), {
    view: "next-actions", actionId: "cornix-madula-test", targetId: "action-cornix-madula-test",
  });
  for (const hash of ["#repo-cornix", "#mobile-repo-cornix"]) {
    assert.deepEqual(routeForHash(hash), { view: "coverage", repositoryId: "cornix", targetId: "repo-cornix" });
  }
});

test("compact pages never omit or duplicate records", () => {
  const items = Array.from({ length: 20 }, (_, i) => i);
  const collected = [];
  for (let page = 0; page < 4; page++) {
    const result = paginate(items, page);
    assert.equal(result.pages, 4);
    assert.equal(result.total, 20);
    assert.ok(result.items.length <= PAGE_SIZE);
    collected.push(...result.items);
  }
  assert.deepEqual(collected, items);
});

test("pagination handles empty results and clamps a stale page after filtering", () => {
  assert.deepEqual(paginate([], 99), { items: [], page: 0, pages: 1, total: 0 });
  assert.equal(paginate([1, 2], 99).page, 0);
  assert.equal(paginate([1, 2], -1).page, 0);
});

const completionCases = [
  ["applied with passed validation", { status: "applied", validation: { ci: "passed" } }, true],
  ["merged with waived validation", { status: "merged", validation: { hardware: "waived" } }, true],
  ["applied with pending validation", { status: "applied", validation: { hardware: "pending" } }, false],
  ["merged with failed validation", { status: "merged", validation: { ci: "failed" } }, false],
  ["non-terminal with passed validation", { status: "pending", validation: { ci: "passed" } }, false],
  ["not-applicable without validation", { status: "not-applicable", validation: {} }, true],
  ["missing target", null, false],
];

for (const [name, target, expected] of completionCases) {
  test(`targetComplete: ${name}`, () => {
    assert.equal(targetComplete(target), expected);
  });
}

const actionCases = [
  ["pending target", { status: "pending", validation: {} }, true],
  ["terminal target with pending gate", { status: "applied", validation: { hardware: "pending" } }, true],
  ["completed target", { status: "applied", validation: { hardware: "passed" } }, false],
  ["not-applicable target", { status: "not-applicable", validation: {} }, false],
  ["missing target", null, false],
];

for (const [name, target, expected] of actionCases) {
  test(`targetNeedsAction: ${name}`, () => {
    assert.equal(targetNeedsAction(target), expected);
  });
}
