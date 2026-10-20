import test from "node:test";
import assert from "node:assert/strict";
import { repositoryGroups } from "./focus.js";

const profile = {
  next_actions: [
    { id: "a2", repository: "a", state: "active", order: 3 },
    { id: "b1", repository: "b", state: "active", order: 1 },
    { id: "a1", repository: "a", state: "active", order: 2 },
    { id: "a3", repository: "a", state: "waiting", order: 4 },
    { id: "c1", repository: "c", state: "later", order: 5 },
  ],
  changes: [{
    id: "change", tracking: {
      a: {status: "applied", validation: {hardware: "pending"}},
      b: {status: "merged", validation: {hardware: "passed"}},
      c: {status: "not-applicable"},
      d: {status: "applied", validation: {ci: "failed"}},
    },
  }],
};
test("one next action per repository, ordered with all related actions retained", () => {
  const before = JSON.stringify(profile);
  const groups = repositoryGroups(profile);
  assert.deepEqual(groups.map(g => g.repository), ["b", "a"]);
  assert.deepEqual(groups[1].actions.map(a => a.id), ["a1", "a2", "a3"]);
  assert.equal(groups[1].records.length, 1);
  assert.equal(JSON.stringify(profile), before);
});
test("waiting, later and accepted history are distinct", () => {
  assert.deepEqual(repositoryGroups(profile, "waiting").map(g => g.actions[0].id), ["a3"]);
  assert.deepEqual(repositoryGroups(profile, "later").map(g => g.repository), ["c"]);
  assert.deepEqual(repositoryGroups(profile, "complete").map(g => g.repository), ["b"]);
  assert.equal(repositoryGroups(profile, "complete")[0].actions.length, 0);
});
test("all view retains every action and record including repositories without next actions", () => {
  const groups = repositoryGroups(profile, "all");
  assert.equal(groups.flatMap(g => g.actions).length, 5);
  assert.equal(groups.flatMap(g => g.records).length, 4);
  assert.deepEqual(repositoryGroups({}), []);
});
