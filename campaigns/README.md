# Campaigns

A campaign is a reviewable, deterministic text migration across explicitly
listed repositories. Files are never created or deleted by a campaign.

Copy `../examples/campaign.json.disabled`, rename it to `<id>.json`, then set:

- `enabled` to `true`;
- the exact repository IDs;
- one or more file globs per step;
- a literal or regular-expression replacement;
- an expected old-or-new occurrence count for every repository.

Always run `shield-fleet campaign plan <id> --diff` before `apply`.
