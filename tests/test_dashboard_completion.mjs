import assert from "node:assert/strict";
import test from "node:test";

import { targetComplete, targetNeedsAction } from "../site/model.js";

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
