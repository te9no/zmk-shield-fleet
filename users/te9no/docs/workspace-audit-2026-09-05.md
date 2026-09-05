# Workspace audit follow-up — 2026-09-05

## Implemented and pushed

- Workspace main: `7e056814` consolidates existing build/flash/path safety work.
- Workspace main: `5a5ef7df` adds firmware provenance and rejects stale CI publication.
- Python regression suite: 66 tests passed locally; just formatting check passed.
- Workspace CI also passed: https://github.com/te9no/zmk-workspace/actions/runs/33973134022
- `just.sh build cornix_tps43_production` succeeded, including provenance export.
  Artifact SHA-256: `e16baac95ca3f69d13cd949d386c4a9989c59a1bcd0e7673cbe866e3916b2c27`.
- Cornix Layout Shift fix: `ef5e507`, published with existing CI artifacts retained
  at `5be6917` on `feature/madula-right-encoder-scroll`.

Local build profile: `madula-lpps-validation`; source checkout:
`work/cornix-madula-studio-keys`. Initial full compilation succeeded; subsequent
provenance validation used an incremental build. This was not a clean committed
rebuild: the sidecar explicitly records dirty build inputs.

## Not claimed complete

- No flashing, new hardware validation, or firmware main merge in this audit.
- Cornix/Madula Layout Shift and encoder/layer-1 scrolling require user testing.
- Remote CI publication with the new provenance checks is not yet verified.
- Older canonical checkouts must not be treated as current without checking refs.
- Historical dirty worktrees and about 44 GiB of managed build/cache data remain;
  nothing was deleted. A later retention review must preserve uncommitted work.

The older workspace-hygiene ledger retains its historical validation results;
they do not certify the new provenance workflow or every current checkout.
