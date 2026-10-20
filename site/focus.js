import { sortedActions, targetComplete } from "./model.js";

// Group presentation only. Explicit next actions and ledger acceptance remain independent.
export function repositoryGroups(profile, filter = "next") {
  const groups = new Map();
  const get = (id) => {
    if (!groups.has(id)) groups.set(id, { repository: id, actions: [], records: [] });
    return groups.get(id);
  };
  for (const action of sortedActions(profile.next_actions ?? [])) {
    if (filter === "all" || action.state === filter
      || (filter === "next" && ["active", "waiting"].includes(action.state))) {
      get(action.repository).actions.push(action);
    }
  }
  for (const change of profile.changes ?? []) {
    for (const [id, target] of Object.entries(change.tracking ?? {})) {
      // Keep out-of-scope separate from completed work.
      const complete = target.status !== "not-applicable" && targetComplete(target);
      if (filter === "all" || (filter === "complete" && complete)) get(id);
      if (groups.has(id) && (filter !== "complete" || complete)) {
        get(id).records.push({ change, target });
      }
    }
  }
  return [...groups.values()].sort((a, b) =>
    (a.actions[0]?.order ?? Infinity) - (b.actions[0]?.order ?? Infinity)
    || a.repository.localeCompare(b.repository));
}
