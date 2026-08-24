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
