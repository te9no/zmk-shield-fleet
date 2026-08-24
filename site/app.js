const state = { data: null, profile: null, actionFilter: "all", filter: "all", matrixFilter: "all", search: "" };
const terminalStatuses = new Set(["applied", "merged", "not-applicable"]);
const actionStates = {
  active: { label: "今進める", detail: "Actionable now" },
  waiting: { label: "実機/外部待ち", detail: "Waiting" },
  later: { label: "後回し/対象外", detail: "Later / out of scope" },
};

const escapeHtml = (value) => String(value ?? "")
  .replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;")
  .replaceAll('"', "&quot;").replaceAll("'", "&#039;");

function targetComplete(target) {
  const checks = Object.values(target.validation ?? {});
  return terminalStatuses.has(target.status)
    && checks.every((status) => status === "passed" || status === "waived");
}

function targetNeedsAction(target) {
  return target && target.status !== "not-applicable" && !targetComplete(target);
}

function shortChangeLabel(change) {
  return change.dashboard_label ?? change.id.replaceAll("-", " ");
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

function renderActions(profile) {
  const allActions = [...(profile.next_actions ?? [])]
    .sort((a, b) => a.order - b.order || a.id.localeCompare(b.id));
  const visible = allActions.filter((action) => state.actionFilter === "all" || action.state === state.actionFilter);
  const totals = Object.fromEntries(Object.keys(actionStates)
    .map((key) => [key, allActions.filter((action) => action.state === key).length]));
  const grid = document.querySelector("#action-grid");
  document.querySelector("#action-summary").textContent = allActions.length
    ? `${totals.active} actionable now · ${totals.waiting} waiting · ${totals.later} later`
    : "No explicit next actions in this profile";

  if (!visible.length) {
    grid.innerHTML = '<div class="empty">No next actions match this filter.</div>';
    return;
  }

  grid.innerHTML = visible.map((action) => {
    const knownRepository = profile.repositories.some((repo) => repo.id === action.repository);
    const repositoryHref = action.repository_url
      || (knownRepository ? `#repo-${encodeURIComponent(action.repository)}` : null);
    const externalRepositoryLink = Boolean(action.repository_url) || !knownRepository;
    const repository = repositoryHref
      ? `<a href="${escapeHtml(repositoryHref)}"${externalRepositoryLink ? ' target="_blank" rel="noopener"' : ""}>${escapeHtml(action.repository)}</a>`
      : escapeHtml(action.repository);
    const stateMeta = actionStates[action.state];
    const blocker = action.blocker || "No blocker — ready to proceed.";
    return `<article class="action-card ${escapeHtml(action.state)}" id="action-${escapeHtml(action.id)}" aria-labelledby="action-title-${escapeHtml(action.id)}">
      <div class="action-card-head">
        <span class="action-state ${escapeHtml(action.state)}">${escapeHtml(stateMeta.label)}</span>
        <a class="action-anchor" href="#action-${escapeHtml(action.id)}" aria-label="Link to ${escapeHtml(action.repository)} next action">#</a>
      </div>
      <div class="action-order"><span class="priority-badge ${escapeHtml(action.priority)}">${escapeHtml(action.priority)} priority</span><span>Order #${escapeHtml(action.order)}</span></div>
      <h3 id="action-title-${escapeHtml(action.id)}">${repository}</h3>
      <p class="action-task">${escapeHtml(action.action)}</p>
      <dl class="action-details">
        <div><dt>Done when / 完了条件</dt><dd>${escapeHtml(action.completion)}</dd></div>
        <div class="blocker"><dt>Blocker / 保留理由</dt><dd>${escapeHtml(blocker)}</dd></div>
      </dl>
      <div class="action-footer"><span>${escapeHtml(stateMeta.detail)}</span>${action.pr ? `<a href="${escapeHtml(action.pr)}" target="_blank" rel="noopener">Related PR ↗</a>` : ""}</div>
    </article>`;
  }).join("");
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
  const validationEntries = Object.entries(target.validation ?? {});
  const validation = ["passed", "pending", "failed", "waived"].flatMap((validationStatus) => {
    const matches = validationEntries.filter(([, status]) => status === validationStatus);
    if (!matches.length) return [];
    const symbol = validationStatus === "passed" ? "✓" : validationStatus === "waived" ? "—" : validationStatus === "failed" ? "×" : "…";
    const names = matches.map(([name]) => name).join(", ");
    const url = matches.map(([name]) => target.validation_urls?.[name]).find(Boolean);
    const content = `${symbol} ${matches.length}`;
    const title = `${validationStatus}: ${names}`;
    return [url
      ? `<a class="validation ${validationStatus}" href="${escapeHtml(url)}" target="_blank" rel="noopener" title="${escapeHtml(title)}" aria-label="${escapeHtml(title)}">${content} ↗</a>`
      : `<span class="validation ${validationStatus}" title="${escapeHtml(title)}" aria-label="${escapeHtml(title)}">${content}</span>`];
  }).join("");
  return `${status}${validation ? `<span class="validation-list">${validation}</span>` : ""}`;
}

function statusCellClass(change, repositoryId) {
  const target = change.tracking[repositoryId];
  if (!target || target.status === "not-applicable") return "status-cell status-cell-na";
  if (target.status === "pr-open") return "status-cell status-cell-pr-open";
  if (target.status === "blocked" || target.status === "closed") return "status-cell status-cell-failed";
  if (!targetComplete(target)) return "status-cell status-cell-pending";
  return "status-cell status-cell-complete";
}

function renderMatrix(profile) {
  const query = state.search.toLowerCase();
  const repositories = profile.repositories.filter((repo) => {
    const searchMatch = [repo.id, repo.architecture, ...repo.modules, ...repo.tags].join(" ").toLowerCase().includes(query);
    const targets = profile.changes.map((change) => change.tracking[repo.id]).filter(Boolean);
    const viewMatch = state.matrixFilter === "pending" ? (repo.rollout_order ?? 50) < 99 && targets.some(targetNeedsAction)
      : state.matrixFilter === "pr-open" ? targets.some((target) => target.status === "pr-open")
      : true;
    return searchMatch && viewMatch;
  })
    .sort((a, b) => (a.rollout_order ?? Number.MAX_SAFE_INTEGER) - (b.rollout_order ?? Number.MAX_SAFE_INTEGER));
  const table = document.querySelector("#matrix-table");
  table.querySelector("thead").innerHTML = `<tr><th>Repository</th><th>Rollout</th>${profile.changes.map((change) => `<th><abbr title="${escapeHtml(change.title)}">${escapeHtml(shortChangeLabel(change))}</abbr></th>`).join("")}</tr>`;
  table.querySelector("tbody").innerHTML = repositories.map((repo) => `<tr id="repo-${escapeHtml(repo.id)}">
    <td><span class="repo-name">${escapeHtml(repo.id)}</span><span class="repo-sub">${escapeHtml(repo.architecture)} · ${escapeHtml(repo.modules.join(", "))}</span></td>
    <td>${repo.rollout_order ? `<span class="status ${repo.rollout_order >= 99 ? "na" : "pr-open"}">${repo.rollout_order >= 99 ? "lowest" : `#${repo.rollout_order}`}</span>` : '<span class="status na">—</span>'}</td>
    ${profile.changes.map((change) => {
      const notes = change.tracking[repo.id]?.notes ?? "Not in scope";
      return `<td class="${statusCellClass(change, repo.id)}" title="${escapeHtml(notes)}">${statusCell(change, repo.id)}</td>`;
    }).join("")}
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
  renderStats(profile); renderActions(profile); renderChanges(profile); renderMatrix(profile); renderRevisions(profile);
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
    select.addEventListener("change", (event) => {
      state.profile = event.target.value;
      state.actionFilter = "all";
      state.search = "";
      state.matrixFilter = "all";
      document.querySelector("#repo-search").value = "";
      document.querySelectorAll(".matrix-filter").forEach((item) => item.classList.toggle("active", item.dataset.matrixFilter === "all"));
      document.querySelectorAll(".action-filter").forEach((item) => {
        const active = item.dataset.actionFilter === "all";
        item.classList.toggle("active", active);
        item.setAttribute("aria-pressed", String(active));
      });
      render();
    });
    document.querySelectorAll(".action-filter").forEach((button) => button.addEventListener("click", () => {
      state.actionFilter = button.dataset.actionFilter;
      document.querySelectorAll(".action-filter").forEach((item) => {
        const active = item === button;
        item.classList.toggle("active", active);
        item.setAttribute("aria-pressed", String(active));
      });
      renderActions(currentProfile());
    }));
    document.querySelectorAll(".filter").forEach((button) => button.addEventListener("click", () => {
      state.filter = button.dataset.filter;
      document.querySelectorAll(".filter").forEach((item) => item.classList.toggle("active", item === button));
      renderChanges(currentProfile());
    }));
    document.querySelectorAll(".matrix-filter").forEach((button) => button.addEventListener("click", () => {
      state.matrixFilter = button.dataset.matrixFilter;
      document.querySelectorAll(".matrix-filter").forEach((item) => item.classList.toggle("active", item === button));
      renderMatrix(currentProfile());
    }));
    document.querySelector("#repo-search").addEventListener("input", (event) => { state.search = event.target.value; renderMatrix(currentProfile()); });
    render();
  } catch (error) {
    document.querySelector("main").innerHTML = `<section class="section"><div class="empty">Dashboard data could not be loaded: ${escapeHtml(error.message)}</div></section>`;
  }
}

init();
