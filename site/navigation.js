// View state only: ledger completion and audit permissions stay in model.js.
export const PAGE_SIZE = 6;
export const VIEWS = ["next-actions", "changes", "coverage", "revisions", "create-your-fleet"];

export function routeForHash(hash) {
  let id;
  try { id = decodeURIComponent(hash.replace(/^#/, "")); } catch { id = ""; }
  if (id.startsWith("action-")) return { view: "next-actions", actionId: id.slice(7), targetId: id };
  if (id.startsWith("mobile-repo-") || id.startsWith("repo-")) {
    const repositoryId = id.replace(/^(mobile-)?repo-/, "");
    return { view: "coverage", repositoryId, targetId: `repo-${repositoryId}` };
  }
  return { view: VIEWS.includes(id) ? id : "next-actions" };
}

export function paginate(items, requestedPage, size = PAGE_SIZE) {
  const pages = Math.max(1, Math.ceil(items.length / size));
  const page = Math.max(0, Math.min(pages - 1, Math.trunc(requestedPage) || 0));
  return { items: items.slice(page * size, (page + 1) * size), page, pages, total: items.length };
}
