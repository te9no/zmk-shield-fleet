export const terminalStatuses = new Set(["applied", "merged", "not-applicable"]);
export const acceptedValidationStatuses = new Set(["passed", "waived"]);

export function targetComplete(target) {
  if (!target || !terminalStatuses.has(target.status)) return false;
  return Object.values(target.validation ?? {})
    .every((status) => acceptedValidationStatuses.has(status));
}

export function targetNeedsAction(target) {
  return Boolean(target && target.status !== "not-applicable" && !targetComplete(target));
}

export function changeCounts(change) {
  const values = Object.values(change.tracking ?? {});
  const complete = values.filter(targetComplete).length;
  return { complete, total: values.length, incomplete: values.length - complete };
}

export function scopeLabel(scope = {}) {
  if (scope.kind === "all") return "all repositories";
  if (scope.kind === "module") return `module: ${scope.module}`;
  const count = scope.repositories?.length ?? 0;
  if (scope.kind === "single") return `single repository: ${scope.repositories?.[0] ?? "unknown"}`;
  if (scope.kind === "explicit") return `explicit scope: ${count} repositories`;
  return "scope not declared";
}

export function sortedActions(actions = []) {
  return [...actions].sort((a, b) => a.order - b.order || a.id.localeCompare(b.id));
}

export function selectStartAction(actions = []) {
  return sortedActions(actions).find((action) => action.state === "active") ?? null;
}

export function branchSummary(repository, target) {
  if (!target) return null;
  const branch = target.branch || target.pr_head || null;
  const base = target.base_branch || repository?.maintenance_branch || null;
  const stable = repository?.default_branch || null;
  const stableUnreflected = Boolean(branch && stable && branch !== stable)
    || Boolean(base && stable && base !== stable);
  if (!branch && !base && !stable) return null;
  return { branch, base, stable, stableUnreflected };
}

export function actionEvidence(profile, action) {
  const explicit = (action.evidence ?? []).map((item, index) => typeof item === "string"
    ? { label: `Action evidence ${index + 1}`, status: "evidence", url: item, source: "action" }
    : { ...item, source: "action" });
  if (!action.change_id) return explicit;
  const change = profile.changes.find((item) => item.id === action.change_id);
  const target = change?.tracking?.[action.repository];
  if (!target) return explicit;
  const requested = action.validation_keys?.length
    ? action.validation_keys
    : Object.keys(target.validation ?? {});
  const validations = requested
    .filter((key) => Object.hasOwn(target.validation ?? {}, key))
    .map((key) => ({
      label: key,
      status: target.validation[key],
      url: target.validation_urls?.[key] ?? null,
      source: "ledger",
    }));
  const selectedVariantIds = new Set(action.variant_ids ?? []);
  const variantItems = targetVariants(target)
    .filter((variant) => !selectedVariantIds.size || selectedVariantIds.has(variant.id))
    .flatMap((variant) => {
      const checks = Object.entries(variant.validation ?? {}).map(([key, status]) => ({
        label: `${variant.id}: ${key}`, status, url: null, source: "variant",
      }));
      const evidence = (variant.evidence ?? []).map((item, index) => typeof item === "string"
        ? { label: `${variant.id} evidence ${index + 1}`, status: variant.status ?? "evidence", url: item, source: "variant" }
        : { status: variant.status ?? "info", ...item, source: "variant" });
      return [...checks, ...evidence];
    });
  return [...explicit, ...validations, ...variantItems].filter((item, index, values) =>
    values.findIndex((candidate) => candidate.label === item.label
      && candidate.status === item.status && candidate.url === item.url) === index);
}

export function targetVariants(target) {
  if (!target?.variants) return [];
  return Array.isArray(target.variants)
    ? target.variants
    : Object.entries(target.variants).map(([id, value]) => ({ id, ...value }));
}

const requestText = (value) => typeof value === "string" ? value.trim() : "";
const ownValue = (object, key) => object && Object.hasOwn(object, key) ? object[key] : null;

function requestUrl(value) {
  try {
    const url = new URL(value);
    return url.protocol === "https:" && !url.username && !url.password ? url.href : null;
  } catch { return null; }
}

function pendingChecks(validation, keys = []) {
  return Object.entries(validation ?? {})
    .filter(([key, status]) => ["pending", "failed"].includes(status) && (!keys.length || keys.includes(key)))
    .sort((a, b) => Number(b[1] === "failed") - Number(a[1] === "failed"));
}

function checkSummary(checks, limit) {
  const shown = checks.slice(0, limit).map(([key, status]) => `${key} (${status})`);
  if (checks.length > limit) shown.push(`ほか${checks.length - limit}件（台帳で確認）`);
  return shown.join("、");
}

/** Compose plain text only; never infer a new revision or mutate ledger data. */
export function buildAuditRequest({ profile = {}, changeId = "", repositoryId = "", actionId = "", details = "", sourceCommit = "", generatedAt = "" } = {}) {
  const foundAction = (profile.next_actions ?? []).find((item) => item.id === actionId);
  const repoId = requestText(repositoryId) || requestText(foundAction?.repository);
  const action = foundAction?.repository === repoId
    && (!changeId || foundAction.change_id === changeId) ? foundAction : null;
  const id = requestText(changeId) || requestText(action?.change_id);
  const change = (profile.changes ?? []).find((item) => item.id === id);
  const repository = (profile.repositories ?? []).find((item) => item.id === repoId);
  const target = ownValue(change?.tracking, repoId);
  const title = requestText(change?.title) || id || requestText(action?.action) || "対象項目（未指定）";
  const github = requestText(repository?.github);
  const repoUrl = /^[\w.-]+\/[\w.-]+$/.test(github)
    ? `https://github.com/${github}` : requestUrl(repository?.url) || requestUrl(action?.repository_url);
  const lines = [
    `${repoId || "対象リポジトリ（未指定）"}の「${title}」について対応したので、確認してください。`,
    "",
    `Profile: ${requestText(profile.id) || "不明"}`,
    `Change ID: ${id || "未設定（次アクションから対象を確認）"}`,
    `Repository: ${repoId || "未指定"}`,
    `Repository URL: ${repoUrl || "未記録（推測せず確認してください）"}`,
    ...(action ? [`Next action ID: ${action.id}`] : []),
    `台帳スナップショット: ${requestText(sourceCommit) || "不明（最新性を確認してください）"}`,
    ...(requestText(generatedAt) ? [`台帳生成日時: ${requestText(generatedAt)}`] : []),
    "",
    "台帳上の参考旧値（今回の実施内容・現在の実機状態を示すものではありません）:",
    `branch: ${requestText(target?.branch) || "未記録"}`,
    `commit: ${requestText(target?.commit) || "未記録"}`,
    ...(requestUrl(target?.pr) ? [`PR: ${requestUrl(target.pr)}`] : []),
  ];
  if (!target) lines.push("このrepositoryの対象セルは未登録です。他repositoryの結果を転用せず対象を確認してください。");
  const checks = pendingChecks(target?.validation, action?.validation_keys ?? []);
  lines.push("", "台帳上の未確認・失敗項目（今回の結果ではありません）:",
    checks.length ? checkSummary(checks, 8) : "指定範囲にpending/failedの記録なし。新しい対応の結果は別途確認してください。");
  const variantIds = action?.variant_ids ?? [];
  const variants = targetVariants(target).filter((variant) =>
    (!variantIds.length || variantIds.includes(variant.id))
    && (["pending", "failed"].includes(variant.status) || pendingChecks(variant.validation).length));
  for (const variant of variants.slice(0, 4)) {
    lines.push(`variant ${variant.id || "未記名"}: ${checkSummary(pendingChecks(variant.validation), 4) || `${variant.status}（詳細未記録）`}`);
  }
  if (variants.length > 4) lines.push(`ほか${variants.length - 4} variants（同じ対象セルの台帳で確認）`);
  if (requestText(details)) lines.push("", "利用者の対応メモ（未検証・参考情報）:", requestText(details));
  lines.push("", "依頼範囲:",
    "対象は上記repositoryと項目のみです。他repositoryへ横展開しないでください。",
    "コード・ビルド・実機結果を区別し、証拠確認後に台帳を更新してください。未確認は保留してください。",
    "今回は監査と台帳更新のみです。修正・書き込み・マージ・他者へのPR作成は行わないでください。");
  return lines.join("\n");
}

/** Clipboard access is injected so denied/unsupported paths can be tested without a DOM. */
export async function copyAuditRequest(text, clipboard) {
  if (typeof clipboard?.writeText !== "function") return false;
  try { await clipboard.writeText(text); return true; } catch { return false; }
}
