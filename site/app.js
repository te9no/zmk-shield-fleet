import {
  actionEvidence,
  branchSummary,
  buildAuditRequest,
  changeCounts,
  copyAuditRequest,
  evidenceCounts,
  scopeLabel,
  selectStartAction,
  sortedActions,
  targetComplete,
  targetNeedsAction,
  targetVariants,
} from "./model.js?v=20260827-evidence";

// Completion lives in model.js; its accepted-check predicate remains:
// checks.every((status) => status === "passed" || status === "waived")

const state = { data: null, profile: null, actionFilter: "all", filter: "all", matrixFilter: "all", search: "" };
const actionStates = {
  active: { label: "今進める", detail: "Actionable now" },
  waiting: { label: "実機/外部待ち", detail: "Waiting" },
  later: { label: "後回し/対象外", detail: "Later / out of scope" },
};
const validationSymbols = { passed: "✓", pending: "…", failed: "×", waived: "—" };

const escapeHtml = (value) => String(value ?? "")
  .replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;")
  .replaceAll('"', "&quot;").replaceAll("'", "&#039;");

const externalLink = (url, label, className = "") => url
  ? `<a${className ? ` class="${className}"` : ""} href="${escapeHtml(url)}" target="_blank" rel="noopener">${label}</a>`
  : "";

function currentProfile() {
  return state.data.profiles.find((profile) => profile.id === state.profile);
}

function repositoryFor(profile, id) {
  return profile.repositories.find((repository) => repository.id === id) ?? null;
}

function changeFor(profile, id) {
  return profile.changes.find((change) => change.id === id) ?? null;
}

function humanize(value) {
  return String(value ?? "").replaceAll("-", " ");
}

function renderProjectMetadata() {
  const project = state.data.project ?? {};
  const projectLink = document.querySelector("#project-link");
  const setupLink = document.querySelector("#setup-guide-link");
  const exampleLink = document.querySelector("#profile-example-link");
  const name = project.name || "ZMK Shield Fleet";
  document.querySelector("#brand-name").textContent = name;
  document.title = name;
  document.querySelector('meta[property="og:title"]').content = name;
  if (project.url) {
    projectLink.href = project.url;
    setupLink.href = `${project.url}#create-a-profile`;
    exampleLink.href = `${project.url}/blob/main/examples/fleet.toml`;
  } else {
    projectLink.hidden = true;
  }
  if (project.site_url) {
    document.querySelector('meta[property="og:url"]').content = project.site_url;
    document.querySelector('meta[property="og:image"]').content = `${project.site_url}og.png`;
    document.querySelector('meta[name="twitter:image"]').content = `${project.site_url}og.png`;
  }
}

function renderStats(profile) {
  const incomplete = profile.changes.reduce((sum, change) => sum + changeCounts(change).incomplete, 0);
  const revision = changeFor(profile, "west-revision-pinning");
  const revisionFindings = revision?.metrics?.finding_total ?? Object.values(revision?.tracking ?? {})
    .reduce((sum, target) => sum + Number(target.findings ?? 0), 0);
  const stats = [
    [profile.repositories.length, "Repositories", "Repositories declared in this profile"],
    [profile.changes.length, "Tracked changes", "Enabled, schema-validated change ledgers"],
    [incomplete, "Incomplete ledger cells", "Repository × change records not yet fully accepted"],
    [revisionFindings, "Revision findings", "Moving revisions and abbreviated commit identifiers"],
  ];
  document.querySelector("#stats").innerHTML = stats.map(([value, label, description]) =>
    `<div class="stat"><strong>${value}</strong><span>${label}</span><small>${description}</small></div>`).join("");
}

function actionTarget(profile, action) {
  return changeFor(profile, action.change_id)?.tracking?.[action.repository] ?? null;
}

function actionBranch(profile, action) {
  const repository = repositoryFor(profile, action.repository);
  const target = actionTarget(profile, action);
  if (target) return branchSummary(repository, target);
  if (!repository) return null;
  return branchSummary(repository, {
    branch: repository.maintenance_branch,
    base_branch: repository.maintenance_branch,
  });
}

function renderEvidence(items, emptyLabel = "") {
  if (!items.length) return emptyLabel ? `<p class="evidence-empty">${escapeHtml(emptyLabel)}</p>` : "";
  return `<ul class="evidence-list">${items.map((item) => {
    const status = item.status || "pending";
    const text = `<span class="evidence-symbol" aria-hidden="true">${validationSymbols[status] ?? "•"}</span><span>${escapeHtml(item.label)}</span><small>${escapeHtml(status)}</small>`;
    return `<li class="evidence-item ${escapeHtml(status)}">${item.url ? externalLink(item.url, text) : `<span>${text}</span>`}</li>`;
  }).join("")}</ul>`;
}

function renderBranch(summary) {
  if (!summary) return "";
  const values = [
    summary.branch ? `<span><strong>Head</strong> ${escapeHtml(summary.branch)}</span>` : "",
    summary.base ? `<span><strong>Base</strong> ${escapeHtml(summary.base)}</span>` : "",
    summary.stable ? `<span><strong>Stable</strong> ${escapeHtml(summary.stable)}</span>` : "",
  ].filter(Boolean).join("");
  return `<div class="branch-summary${summary.stableUnreflected ? " stable-unreflected" : ""}">${values}${summary.stableUnreflected ? "<em>Stable branch not updated</em>" : ""}</div>`;
}

function repositoryMarkup(profile, action) {
  const known = repositoryFor(profile, action.repository);
  const href = action.repository_url || (known ? `#repo-${encodeURIComponent(action.repository)}` : null);
  const external = Boolean(action.repository_url) || !known;
  return href
    ? `<a href="${escapeHtml(href)}"${external ? ' target="_blank" rel="noopener"' : ""}>${escapeHtml(action.repository)}</a>`
    : escapeHtml(action.repository);
}

function auditRequestButton(changeId, repositoryId = "", actionId = "") {
  return `<button type="button" class="audit-request-button" data-audit-request data-change-id="${escapeHtml(changeId)}" data-repository-id="${escapeHtml(repositoryId)}" data-action-id="${escapeHtml(actionId)}">対応したので確認を依頼</button>`;
}

function actionCard(profile, action) {
  const stateMeta = actionStates[action.state];
  const blocker = action.blocker || "No blocker — ready to proceed.";
  const evidence = actionEvidence(profile, action);
  const counts = evidenceCounts(evidence);
  const evidenceSummary = [`Evidence / 証跡 ${counts.total}件`,
    counts.failed ? `失敗 ${counts.failed}件` : "",
    counts.pending ? `未確認 ${counts.pending}件` : "",
    counts.reference ? `参考 ${counts.reference}件` : ""].filter(Boolean).join(" · ");
  const variants = action.variant_ids ?? [];
  return `<article class="action-card ${escapeHtml(action.state)}" id="action-${escapeHtml(action.id)}" aria-labelledby="action-title-${escapeHtml(action.id)}">
    <div class="action-card-head">
      <span class="action-state ${escapeHtml(action.state)}">${escapeHtml(stateMeta.label)}</span>
      <a class="action-anchor" href="#action-${escapeHtml(action.id)}" aria-label="Link to ${escapeHtml(action.repository)} next action">#</a>
    </div>
    <div class="action-order"><span class="priority-badge ${escapeHtml(action.priority)}">${escapeHtml(action.priority)} priority</span><span>Order #${escapeHtml(action.order)}</span></div>
    <h3 id="action-title-${escapeHtml(action.id)}">${repositoryMarkup(profile, action)}</h3>
    <p class="action-task">${escapeHtml(action.action)}</p>
    ${auditRequestButton(action.change_id, action.repository, action.id)}
    ${renderBranch(actionBranch(profile, action))}
    ${variants.length ? `<p class="variant-list"><strong>Variants</strong> ${variants.map(escapeHtml).join(", ")}</p>` : ""}
    <dl class="action-details">
      <div><dt>Done when / 完了条件</dt><dd>${escapeHtml(action.completion)}</dd></div>
      <div class="blocker"><dt>Blocker / 保留理由</dt><dd>${escapeHtml(blocker)}</dd></div>
    </dl>
    ${evidence.length ? `<details class="action-evidence"><summary>${escapeHtml(evidenceSummary)}</summary><div class="action-evidence-scroll" tabindex="0" role="region" aria-label="${escapeHtml(action.repository)}の証跡一覧">${renderEvidence(evidence)}</div></details>` : ""}
    <div class="action-footer"><span>${escapeHtml(stateMeta.detail)}</span>${action.pr ? externalLink(action.pr, "Related PR ↗") : ""}</div>
  </article>`;
}

function renderStartHere(profile) {
  const action = selectStartAction(profile.next_actions);
  const container = document.querySelector("#start-here");
  if (!action) {
    container.innerHTML = '<p class="start-empty"><strong>No actionable item right now.</strong> Review the waiting queue and blockers below.</p>';
    return;
  }
  container.innerHTML = `<div><span class="start-label">Start here / まずこれ</span><strong>${escapeHtml(action.repository)}</strong><p>${escapeHtml(action.action)}</p></div><a href="#action-${escapeHtml(action.id)}">Open action <span aria-hidden="true">↓</span></a>`;
}

function renderActions(profile) {
  const allActions = sortedActions(profile.next_actions ?? []);
  const visible = allActions.filter((action) => state.actionFilter === "all" || action.state === state.actionFilter);
  const totals = Object.fromEntries(Object.keys(actionStates)
    .map((key) => [key, allActions.filter((action) => action.state === key).length]));
  document.querySelector("#action-summary").textContent = allActions.length
    ? `${totals.active} actionable now · ${totals.waiting} waiting · ${totals.later} later`
    : "No explicit next actions in this profile";
  document.querySelector("#action-grid").innerHTML = visible.length
    ? visible.map((action) => actionCard(profile, action)).join("")
    : '<div class="empty">No next actions match this filter.</div>';
}

function shortChangeLabel(change) {
  return change.dashboard_label ?? humanize(change.id);
}

function renderChanges(profile) {
  const changes = profile.changes.filter((change) => {
    const progress = changeCounts(change);
    if (state.filter === "pending") return progress.incomplete > 0;
    if (state.filter === "complete") return progress.incomplete === 0;
    return true;
  });
  document.querySelector("#change-grid").innerHTML = changes.length ? changes.map((change) => {
    const progress = changeCounts(change);
    const percent = progress.total ? Math.round(progress.complete / progress.total * 100) : 0;
    const sourceUrl = change.trigger?.change_url || change.source?.change_url;
    return `<article class="change-card">
      <div class="change-meta"><span>${escapeHtml(scopeLabel(change.scope))}</span><span class="badge ${change.automated ? "" : "manual"}">${change.automated ? "PR ready" : "ledger only"}</span></div>
      <h3>${escapeHtml(change.title)}</h3><p>${escapeHtml(change.description)}</p>
      ${Object.keys(change.tracking ?? {}).length ? auditRequestButton(change.id) : ""}
      <div class="progress-line" role="progressbar" aria-label="${escapeHtml(change.title)} completion" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${percent}"><span style="width:${percent}%"></span></div>
      <div class="progress-copy"><strong>${progress.complete} / ${progress.total} accounted for</strong><span>${progress.incomplete} incomplete</span></div>
      ${sourceUrl ? externalLink(sourceUrl, "View reference implementation ↗", "source-link") : ""}
    </article>`;
  }).join("") : '<div class="empty">No changes match this filter.</div>';
}

function statusMarkup(target) {
  if (!target) return '<span class="status na">not in scope</span>';
  const label = target.status === "not-applicable" ? "not applicable" : target.status;
  const css = target.status === "not-applicable" ? "na" : target.status;
  return target.pr
    ? externalLink(target.pr, `${escapeHtml(label)} ↗`, `status ${escapeHtml(css)}`)
    : `<span class="status ${escapeHtml(css)}">${escapeHtml(label)}</span>`;
}

function validationEvidence(target) {
  return Object.entries(target?.validation ?? {}).map(([label, status]) => ({
    label, status, url: target.validation_urls?.[label] ?? null,
  }));
}

function variantEvidence(variant) {
  const checks = Object.entries(variant.validation ?? {}).map(([label, status]) => ({ label, status, url: null }));
  const links = (variant.evidence ?? []).map((item, index) => typeof item === "string"
    ? { label: `${variant.id || "variant"} evidence ${index + 1}`, status: variant.status || "evidence", url: item }
    : { status: variant.status || "evidence", ...item });
  return [...checks, ...links];
}

function renderVariants(variants) {
  if (!variants.length) return "";
  return `<div class="variant-details"><strong>Variants</strong><ul>${variants.map((variant) => `<li><div><code>${escapeHtml(variant.id ?? variant.name ?? "unnamed")}</code><span class="variant-status ${escapeHtml(variant.status ?? "pending")}">${escapeHtml(variant.status ?? "pending")}</span></div>${renderEvidence(variantEvidence(variant), "No variant validation recorded.")}</li>`).join("")}</ul></div>`;
}

function targetDetailBody(repository, target, changeId) {
  if (!target) return "";
  const summary = branchSummary(repository, target);
  const variants = targetVariants(target);
  const commit = target.commit ? `<p><strong>Commit</strong> <code>${escapeHtml(target.commit)}</code></p>` : "";
  return `${auditRequestButton(changeId, repository.id)}
    ${renderEvidence(validationEvidence(target), "No validation checks recorded.")}
    ${renderBranch(summary)}
    ${renderVariants(variants)}
    ${commit}<p class="target-notes">${escapeHtml(target.notes || "No notes recorded.")}</p>
  `;
}

function targetDetails(repository, target, changeId) {
  if (!target) return "";
  return `<details class="target-details"><summary>Evidence &amp; notes</summary>${targetDetailBody(repository, target, changeId)}</details>`;
}

function statusCellClass(target) {
  if (!target || target.status === "not-applicable") return "status-cell status-cell-na";
  if (target.status === "pr-open") return "status-cell status-cell-pr-open";
  if (target.status === "blocked" || target.status === "closed") return "status-cell status-cell-failed";
  if (!targetComplete(target)) return "status-cell status-cell-pending";
  return "status-cell status-cell-complete";
}

function filteredRepositories(profile) {
  const query = state.search.toLowerCase();
  return profile.repositories.filter((repository) => {
    const searchMatch = [repository.id, repository.architecture, ...repository.modules, ...repository.tags].join(" ").toLowerCase().includes(query);
    const targets = profile.changes.map((change) => change.tracking[repository.id]).filter(Boolean);
    const viewMatch = state.matrixFilter === "pending" ? (repository.rollout_order ?? 50) < 99 && targets.some(targetNeedsAction)
      : state.matrixFilter === "pr-open" ? targets.some((target) => target.status === "pr-open") : true;
    return searchMatch && viewMatch;
  }).sort((a, b) => (a.rollout_order ?? Number.MAX_SAFE_INTEGER) - (b.rollout_order ?? Number.MAX_SAFE_INTEGER));
}

function renderMatrix(profile) {
  const repositories = filteredRepositories(profile);
  const table = document.querySelector("#matrix-table");
  table.querySelector("thead").innerHTML = `<tr><th scope="col">Repository</th><th scope="col">Rollout</th>${profile.changes.map((change) => `<th scope="col"><abbr title="${escapeHtml(change.title)}">${escapeHtml(shortChangeLabel(change))}</abbr></th>`).join("")}</tr>`;
  table.querySelector("tbody").innerHTML = repositories.map((repository) => `<tr id="repo-${escapeHtml(repository.id)}">
    <th scope="row"><span class="repo-name">${escapeHtml(repository.id)}</span><span class="repo-sub">${escapeHtml(repository.architecture)} · ${escapeHtml(repository.modules.join(", "))}</span><span class="repo-branches">maint: ${escapeHtml(repository.maintenance_branch)} · stable: ${escapeHtml(repository.default_branch)}</span></th>
    <td>${repository.rollout_order ? `<span class="status ${repository.rollout_order >= 99 ? "na" : "pr-open"}">${repository.rollout_order >= 99 ? "lowest" : `#${repository.rollout_order}`}</span>` : '<span class="status na">—</span>'}</td>
    ${profile.changes.map((change) => { const target = change.tracking[repository.id]; return `<td class="${statusCellClass(target)}">${statusMarkup(target)}${targetDetails(repository, target, change.id)}</td>`; }).join("")}
  </tr>`).join("") || '<tr><td class="empty" colspan="99">No repositories match.</td></tr>';

  document.querySelector("#matrix-cards").innerHTML = repositories.map((repository) => `<article class="matrix-card" id="mobile-repo-${escapeHtml(repository.id)}">
    <header><div><h3>${escapeHtml(repository.id)}</h3><p>${escapeHtml(repository.architecture)} · ${escapeHtml(repository.modules.join(", "))}</p></div><span class="status ${repository.rollout_order >= 99 ? "na" : "pr-open"}">${repository.rollout_order >= 99 ? "lowest" : `#${repository.rollout_order ?? "—"}`}</span></header>
    <p class="repo-branches">Maintenance: ${escapeHtml(repository.maintenance_branch)} · Stable: ${escapeHtml(repository.default_branch)}</p>
    <div class="mobile-change-list">${profile.changes.filter((change) => change.tracking[repository.id]).map((change) => {
      const target = change.tracking[repository.id];
      return `<details class="mobile-change ${statusCellClass(target)}"><summary><span>${escapeHtml(shortChangeLabel(change))}</span>${statusMarkup(target)}</summary><div class="mobile-target-details">${targetDetailBody(repository, target, change.id)}</div></details>`;
    }).join("")}</div>
  </article>`).join("") || '<div class="empty">No repositories match.</div>';
}

function renderRevisions(profile) {
  const change = changeFor(profile, "west-revision-pinning");
  const list = document.querySelector("#revision-list");
  if (!change) { list.innerHTML = '<div class="empty">No revision-pinning ledger entry.</div>'; return; }
  const rows = Object.entries(change.tracking)
    .map(([id, target]) => ({ id, findings: Number(target.findings ?? 0), status: target.status }))
    .filter((item) => item.findings > 0 || !["applied", "merged", "not-applicable"].includes(item.status))
    .sort((a, b) => b.findings - a.findings || a.id.localeCompare(b.id));
  list.innerHTML = rows.map((row) => `<div class="revision-row"><strong>${escapeHtml(row.id)}</strong><span>${row.findings || "review"} finding${row.findings === 1 ? "" : "s"}</span></div>`).join("") || '<div class="empty">All repositories are pinned.</div>';
}

function render() {
  const profile = currentProfile();
  document.documentElement.lang = profile.locale || state.data.locale || "en";
  renderStats(profile); renderStartHere(profile); renderActions(profile); renderChanges(profile); renderMatrix(profile); renderRevisions(profile);
  document.querySelector("#footer-profile").textContent = `Profile: ${profile.id} · Owner: ${profile.owner}`;
  const generated = state.data.generated_at ? new Date(state.data.generated_at).toLocaleString(profile.locale || undefined) : "unknown";
  const commit = state.data.source_commit ? state.data.source_commit.slice(0, 12) : "unknown";
  document.querySelector("#footer-source").textContent = `Generated ${generated} · source ${commit}`;
}

function updatePressed(selector, active) {
  document.querySelectorAll(selector).forEach((item) => {
    const selected = item === active;
    item.classList.toggle("active", selected);
    item.setAttribute("aria-pressed", String(selected));
  });
}

function initAuditRequest() {
  const dialog = document.querySelector("#audit-request-dialog");
  const repository = document.querySelector("#audit-repository");
  const notes = document.querySelector("#audit-notes");
  const prompt = document.querySelector("#audit-prompt");
  const copy = document.querySelector("#audit-copy");
  const regenerate = document.querySelector("#audit-regenerate");
  const status = document.querySelector("#audit-status");
  let context = null;
  let trigger = null;
  let manualEdited = false;
  let stale = false;
  let copying = false;

  function updateCopy() {
    copy.disabled = !repository.value || !prompt.value.trim() || stale || copying;
  }

  function generate() {
    manualEdited = false;
    stale = false;
    regenerate.hidden = true;
    prompt.value = repository.value ? buildAuditRequest({
      ...context, repositoryId: repository.value, details: notes.value,
    }) : "";
    status.textContent = repository.value ? "依頼文をコピーして、この会話へ貼り付けてください。" : "対象リポジトリを選んでください。";
    updateCopy();
  }

  function inputsChanged() {
    if (!manualEdited) { generate(); return; }
    // Preserve hand edits until the user explicitly replaces them; never copy a stale target.
    stale = true;
    regenerate.hidden = false;
    regenerate.disabled = !repository.value;
    status.textContent = "編集済みの依頼文を保持しています。変更した対象・メモを反映するには「依頼文を作り直す」を押してください。";
    updateCopy();
  }

  document.addEventListener("click", (event) => {
    const button = event.target.closest?.("[data-audit-request]");
    if (!button || dialog.open) return;
    trigger = button;
    const profile = currentProfile();
    const { changeId, repositoryId, actionId } = button.dataset;
    const change = changeFor(profile, changeId);
    const action = (profile.next_actions ?? []).find((item) => item.id === actionId);
    context = { profile, changeId, actionId, sourceCommit: state.data.source_commit, generatedAt: state.data.generated_at };
    document.querySelector("#audit-target").textContent = change?.title || action?.action || changeId || "対象項目";
    const choices = repositoryId ? [repositoryId] : Object.keys(change?.tracking ?? {});
    repository.replaceChildren();
    if (choices.length !== 1) repository.add(new Option("対象リポジトリを選択", ""));
    for (const id of choices) repository.add(new Option(id, id));
    repository.disabled = Boolean(repositoryId) || choices.length === 1;
    notes.value = "";
    copying = false;
    generate();
    dialog.showModal();
  });

  repository.addEventListener("change", inputsChanged);
  notes.addEventListener("input", inputsChanged);
  prompt.addEventListener("input", () => {
    manualEdited = true;
    if (!stale) status.textContent = "編集した依頼文をそのままコピーします。送信や台帳変更はしません。";
    updateCopy();
  });
  regenerate.addEventListener("click", generate);
  document.querySelector("#audit-close").addEventListener("click", () => dialog.close());
  dialog.addEventListener("close", () => {
    context = null;
    if (trigger?.isConnected) trigger.focus();
    trigger = null;
  });
  copy.addEventListener("click", async () => {
    if (copy.disabled) return;
    const session = context;
    const text = prompt.value;
    copying = true;
    status.textContent = "コピーしています…";
    updateCopy();
    const copied = await copyAuditRequest(text, navigator.clipboard);
    if (context !== session || !dialog.open) return;
    copying = false;
    updateCopy();
    if (prompt.value !== text || stale) {
      status.textContent = "文面が変更されました。現在の依頼文を確認して、もう一度コピーしてください。";
      return;
    }
    if (copied) {
      status.textContent = "依頼文をコピーしました。この会話へ貼り付けて送信してください。台帳は変更していません。";
    } else {
      prompt.focus();
      prompt.select();
      status.textContent = "自動コピーできませんでした。選択した依頼文を Ctrl+C / ⌘C（スマホは長押し）でコピーしてください。";
    }
  });
}

async function init() {
  try {
    const response = await fetch("data.json", { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    state.data = await response.json();
    if (!state.data.profiles?.length) throw new Error("No fleet profiles found");
    renderProjectMetadata();
    state.profile = state.data.profiles[0].id;
    const select = document.querySelector("#profile-select");
    select.innerHTML = state.data.profiles.map((profile) => `<option value="${escapeHtml(profile.id)}">${escapeHtml(profile.id)}</option>`).join("");
    document.querySelector("#profile-control").hidden = state.data.profiles.length === 1;
    select.addEventListener("change", (event) => {
      state.profile = event.target.value; state.actionFilter = "all"; state.search = ""; state.matrixFilter = "all";
      document.querySelector("#repo-search").value = "";
      updatePressed(".matrix-filter", document.querySelector('[data-matrix-filter="all"]'));
      updatePressed(".action-filter", document.querySelector('[data-action-filter="all"]'));
      render();
    });
    document.querySelectorAll(".action-filter").forEach((button) => button.addEventListener("click", () => {
      state.actionFilter = button.dataset.actionFilter; updatePressed(".action-filter", button); renderActions(currentProfile());
    }));
    document.querySelectorAll(".filter").forEach((button) => button.addEventListener("click", () => {
      state.filter = button.dataset.filter; updatePressed(".filter", button); renderChanges(currentProfile());
    }));
    document.querySelectorAll(".matrix-filter").forEach((button) => button.addEventListener("click", () => {
      state.matrixFilter = button.dataset.matrixFilter; updatePressed(".matrix-filter", button); renderMatrix(currentProfile());
    }));
    document.querySelector("#repo-search").addEventListener("input", (event) => { state.search = event.target.value; renderMatrix(currentProfile()); });
    initAuditRequest();
    render();
  } catch (error) {
    document.querySelector("main").innerHTML = `<section class="section"><div class="empty" role="alert">Dashboard data could not be loaded: ${escapeHtml(error.message)}</div></section>`;
  }
}

init();
