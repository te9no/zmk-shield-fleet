const state = { data: null, profile: null, filter: "all", search: "" };
const terminalStatuses = new Set(["applied", "merged", "not-applicable"]);
const acceptedValidationStatuses = new Set(["passed", "waived"]);

const escapeHtml = (value) => String(value ?? "")
  .replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;")
  .replaceAll('"', "&quot;").replaceAll("'", "&#039;");

function targetComplete(target) {
  if (target.status === "not-applicable") return true;
  const checks = Object.values(target.validation ?? {});
  return terminalStatuses.has(target.status) && checks.every((status) => acceptedValidationStatuses.has(status));
}

function counts(change) {
  const values = Object.values(change.tracking);
  const complete = values.filter(targetComplete).length;
  return { complete, total: values.length, pending: values.length - complete };
}

function currentProfile() {
  return state.data.profiles.find((profile) => profile.id === state.profile);
}

function renderStats(profile) {
  const pending = profile.changes.reduce((sum, change) => sum + counts(change).pending, 0);
  const revision = profile.changes.find((change) => change.id === "west-revision-pinning");
  const revisionFindings = revision?.metrics?.finding_total ?? Object.values(revision?.tracking ?? {})
    .reduce((sum, target) => sum + Number(target.findings ?? 0), 0);
  const stats = [
    [profile.repositories.length, "Repositories"],
    [profile.changes.length, "Tracked changes"],
    [pending, "Targets needing action"],
    [revisionFindings, "Revision findings"],
  ];
  document.querySelector("#stats").innerHTML = stats.map(([value, label]) =>
    `<div class="stat"><strong>${value}</strong><span>${label}</span></div>`).join("");
}

function renderChanges(profile) {
  const changes = profile.changes.filter((change) => {
    const progress = counts(change);
    if (state.filter === "pending") return progress.pending > 0;
    if (state.filter === "complete") return progress.pending === 0;
    return true;
  });
  const grid = document.querySelector("#change-grid");
  if (!changes.length) {
    grid.innerHTML = '<div class="empty">No changes match this filter.</div>';
    return;
  }
  grid.innerHTML = changes.map((change) => {
    const progress = counts(change);
    const percent = progress.total ? Math.round(progress.complete / progress.total * 100) : 0;
    const scope = change.scope?.module ? `module: ${change.scope.module}` : "all repositories";
    const sourceUrl = change.trigger?.change_url || change.source?.change_url;
    return `<article class="change-card">
      <div class="change-meta"><span>${escapeHtml(scope)}</span><span class="badge ${change.automated ? "" : "manual"}">${change.automated ? "PR ready" : "ledger only"}</span></div>
      <h3>${escapeHtml(change.title)}</h3>
      <p>${escapeHtml(change.description)}</p>
      <div class="progress-line" aria-label="${percent}% complete"><span style="width:${percent}%"></span></div>
      <div class="progress-copy"><strong>${progress.complete} / ${progress.total} accounted for</strong><span>${progress.pending} need action</span></div>
      ${sourceUrl ? `<a class="source-link" href="${escapeHtml(sourceUrl)}">View reference implementation ↗</a>` : ""}
    </article>`;
  }).join("");
}

function statusCell(change, repositoryId) {
  const target = change.tracking[repositoryId];
  if (!target) return '<span class="status na">not in scope</span>';
  const label = target.status === "not-applicable" ? "not applicable" : target.status;
  const css = target.status === "not-applicable" ? "na" : target.status;
  const status = target.pr
    ? `<a class="status ${escapeHtml(css)}" href="${escapeHtml(target.pr)}" target="_blank" rel="noopener">${escapeHtml(label)} ↗</a>`
    : `<span class="status ${escapeHtml(css)}">${escapeHtml(label)}</span>`;
  const validation = Object.entries(target.validation ?? {}).map(([name, status]) => {
    const symbol = status === "passed" ? "✓" : status === "waived" ? "—" : status === "failed" ? "×" : "…";
    const url = target.validation_urls?.[name];
    const content = `${escapeHtml(name)} ${symbol}${url ? " ↗" : ""}`;
    return url
      ? `<a class="validation ${escapeHtml(status)}" href="${escapeHtml(url)}" target="_blank" rel="noopener">${content}</a>`
      : `<span class="validation ${escapeHtml(status)}">${content}</span>`;
  }).join("");
  return `${status}${validation ? `<span class="validation-list">${validation}</span>` : ""}`;
}

function statusCellClass(change, repositoryId) {
  const status = change.tracking[repositoryId]?.status ?? "not-applicable";
  return `status-cell status-cell-${status === "not-applicable" ? "na" : status}`;
}

function renderMatrix(profile) {
  const query = state.search.toLowerCase();
  const repositories = profile.repositories.filter((repo) =>
    [repo.id, repo.architecture, ...repo.modules, ...repo.tags].join(" ").toLowerCase().includes(query))
    .sort((a, b) => (a.rollout_order ?? Number.MAX_SAFE_INTEGER) - (b.rollout_order ?? Number.MAX_SAFE_INTEGER));
  const table = document.querySelector("#matrix-table");
  table.querySelector("thead").innerHTML = `<tr><th>Repository</th><th>Rollout</th>${profile.changes.map((change) => `<th>${escapeHtml(change.id)}</th>`).join("")}</tr>`;
  table.querySelector("tbody").innerHTML = repositories.map((repo) => `<tr>
    <td><span class="repo-name">${escapeHtml(repo.id)}</span><span class="repo-sub">${escapeHtml(repo.architecture)} · ${escapeHtml(repo.modules.join(", "))}</span></td>
    <td>${repo.rollout_order ? `<span class="status ${repo.rollout_order >= 99 ? "na" : "pr-open"}">${repo.rollout_order >= 99 ? "lowest" : `#${repo.rollout_order}`}</span>` : '<span class="status na">—</span>'}</td>
    ${profile.changes.map((change) => `<td class="${statusCellClass(change, repo.id)}">${statusCell(change, repo.id)}</td>`).join("")}
  </tr>`).join("") || '<tr><td class="empty" colspan="99">No repositories match.</td></tr>';
}

function renderRevisions(profile) {
  const change = profile.changes.find((item) => item.id === "west-revision-pinning");
  const list = document.querySelector("#revision-list");
  if (!change) {
    list.innerHTML = '<div class="empty">No revision-pinning ledger entry.</div>';
    return;
  }
  const rows = Object.entries(change.tracking)
    .map(([id, target]) => ({ id, findings: Number(target.findings ?? 0), status: target.status }))
    .filter((item) => item.findings > 0 || !terminalStatuses.has(item.status))
    .sort((a, b) => b.findings - a.findings || a.id.localeCompare(b.id));
  list.innerHTML = rows.map((row) => `<div class="revision-row"><strong>${escapeHtml(row.id)}</strong><span>${row.findings || "review"} finding${row.findings === 1 ? "" : "s"}</span></div>`).join("") || '<div class="empty">All repositories are pinned.</div>';
}

function render() {
  const profile = currentProfile();
  renderStats(profile); renderChanges(profile); renderMatrix(profile); renderRevisions(profile);
  document.querySelector("#footer-profile").textContent = `Profile: ${profile.id} · Owner: ${profile.owner}`;
}

async function init() {
  try {
    const response = await fetch("data.json");
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    state.data = await response.json();
    if (!state.data.profiles.length) throw new Error("No fleet profiles found");
    state.profile = state.data.profiles[0].id;
    const select = document.querySelector("#profile-select");
    select.innerHTML = state.data.profiles.map((profile) => `<option value="${escapeHtml(profile.id)}">${escapeHtml(profile.id)}</option>`).join("");
    select.addEventListener("change", (event) => { state.profile = event.target.value; state.search = ""; document.querySelector("#repo-search").value = ""; render(); });
    document.querySelectorAll(".filter").forEach((button) => button.addEventListener("click", () => {
      state.filter = button.dataset.filter;
      document.querySelectorAll(".filter").forEach((item) => item.classList.toggle("active", item === button));
      renderChanges(currentProfile());
    }));
    document.querySelector("#repo-search").addEventListener("input", (event) => { state.search = event.target.value; renderMatrix(currentProfile()); });
    render();
  } catch (error) {
    document.querySelector("main").innerHTML = `<section class="section"><div class="empty">Dashboard data could not be loaded: ${escapeHtml(error.message)}</div></section>`;
  }
}

init();
