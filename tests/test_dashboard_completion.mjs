import assert from "node:assert/strict";
import fs from "node:fs";
import test from "node:test";
import vm from "node:vm";

const source = fs.readFileSync(new URL("../site/app.js", import.meta.url), "utf8");
const start = source.indexOf("const terminalStatuses");
const end = source.indexOf("function shortChangeLabel");
assert.notEqual(start, -1, "terminal status declaration must remain discoverable");
assert.notEqual(end, -1, "completion logic boundary must remain discoverable");

const context = {};
vm.runInNewContext(
  `${source.slice(start, end)}\nthis.targetComplete = targetComplete; this.targetNeedsAction = targetNeedsAction;`,
  context,
);

test("actual dashboard completion logic gates terminal targets on validation", () => {
  assert.equal(context.targetComplete({ status: "applied", validation: { ci: "passed" } }), true);
  assert.equal(context.targetComplete({ status: "applied", validation: { hardware: "pending" } }), false);
  assert.equal(context.targetComplete({ status: "merged", validation: { ci: "failed" } }), false);
  assert.equal(context.targetComplete({ status: "pending", validation: { ci: "passed" } }), false);
});

test("not-applicable targets never appear as actionable", () => {
  const target = { status: "not-applicable", validation: {} };
  assert.equal(context.targetComplete(target), true);
  assert.equal(context.targetNeedsAction(target), false);
});

