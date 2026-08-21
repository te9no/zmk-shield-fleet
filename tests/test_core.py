from __future__ import annotations

import json
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path

from zmk_shield_fleet.core import (
    FleetError,
    apply_campaign,
    audit_fleet,
    campaign_matrix,
    load_campaign,
    load_ledger_entry,
    load_manifest,
    mark_ledger_target,
    plan_campaign,
    resolve_workspace,
    select_repositories,
    sync_ledger_entry,
)


class FleetFixture:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.workspace = root / "workspace"
        self.workspace.mkdir()
        self.manifest_path = root / "fleet.toml"

    def write_manifest(self, *, mirror: bool = False) -> None:
        mirror_text = ""
        if mirror:
            mirror_text = textwrap.dedent(
                """
                [[mirrors]]
                id = "same-config"
                description = "test mirror"
                enforce = false
                members = [
                  { repository = "one", path = "config", include = ["**"], exclude = [] },
                  { repository = "two", path = "config", include = ["**"], exclude = [] },
                ]
                """
            )
        self.manifest_path.write_text(
            textwrap.dedent(
                f"""
                schema = 1

                [fleet]
                owner = "example"
                workspace = "workspace"

                [[repositories]]
                id = "one"
                checkout = "one"
                default_branch = "main"
                architecture = "snippets"
                modules = ["trackball"]
                tags = ["test"]
                required_globs = ["config/*.conf"]
                ci = false

                [[repositories]]
                id = "two"
                checkout = "two"
                default_branch = "main"
                architecture = "snippets"
                modules = ["trackball"]
                tags = ["test"]
                required_globs = ["config/*.conf"]
                ci = false

                {mirror_text}
                """
            ).strip()
            + "\n",
            encoding="utf-8",
        )

    def init_repositories(self, value: str = "VALUE=old\n") -> None:
        for name in ("one", "two"):
            root = self.workspace / name
            (root / "config").mkdir(parents=True)
            (root / "config" / "module.conf").write_text(value, encoding="utf-8")
            subprocess.run(
                ["git", "init", "-q", str(root)],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

    def write_campaign(self, *, expected_two: int = 1) -> Path:
        campaign = {
            "schema": 1,
            "id": "align-value",
            "enabled": True,
            "title": "Align test value",
            "description": "test",
            "repositories": ["one", "two"],
            "steps": [
                {
                    "id": "replace-value",
                    "repositories": ["one", "two"],
                    "paths": ["config/*.conf"],
                    "operation": "literal_replace",
                    "find": "VALUE=old",
                    "replace": "VALUE=new",
                    "expect": {"one": 1, "two": expected_two},
                }
            ],
        }
        path = self.root / "align-value.json"
        path.write_text(json.dumps(campaign), encoding="utf-8")
        return path

    def write_ledger(self, *, tracking: dict | None = None) -> Path:
        raw = json.loads(self.write_campaign().read_text(encoding="utf-8"))
        raw["source"] = {
            "repository": "example/driver",
            "from_revision": "old",
            "to_revision": "new",
            "change_url": "https://github.com/example/driver/compare/old...new",
            "notes": "test update",
        }
        raw["tracking"] = tracking or {
            "one": {"status": "pending", "pr": None, "commit": None, "notes": ""},
            "two": {"status": "pending", "pr": None, "commit": None, "notes": ""},
        }
        path = self.root / "align-value.json"
        path.write_text(json.dumps(raw), encoding="utf-8")
        return path


class ManifestTests(unittest.TestCase):
    def test_manifest_and_tag_selection(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = FleetFixture(Path(directory))
            fixture.write_manifest()
            manifest = load_manifest(fixture.manifest_path)
            self.assertEqual(fixture.workspace.resolve(), manifest.default_workspace)
            selected = select_repositories(manifest, tags=["test"])
            self.assertEqual(["one", "two"], [repo.id for repo in selected])

    def test_duplicate_repository_id_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = FleetFixture(Path(directory))
            fixture.write_manifest()
            text = fixture.manifest_path.read_text(encoding="utf-8")
            duplicate = text.replace('id = "two"', 'id = "one"')
            fixture.manifest_path.write_text(duplicate, encoding="utf-8")
            with self.assertRaisesRegex(FleetError, "duplicate repository id"):
                load_manifest(fixture.manifest_path)


class CampaignTests(unittest.TestCase):
    def test_one_change_can_update_west_overlay_and_conf(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = FleetFixture(Path(directory))
            fixture.write_manifest()
            fixture.init_repositories()
            for name in ("one", "two"):
                root = fixture.workspace / name
                (root / "config" / "west.yml").write_text("revision: old\n", encoding="utf-8")
                (root / "config" / "shield.overlay").write_text("old-binding\n", encoding="utf-8")
            raw = json.loads(fixture.write_campaign().read_text(encoding="utf-8"))
            raw["steps"] = [
                {"id": "west", "paths": ["config/west.yml"], "operation": "literal_replace",
                 "find": "revision: old", "replace": "revision: new", "expect": {"one": 1, "two": 1}},
                {"id": "overlay", "paths": ["**/*.overlay"], "operation": "literal_replace",
                 "find": "old-binding", "replace": "new-binding", "expect": {"one": 1, "two": 1}},
                {"id": "conf", "paths": ["**/*.conf"], "operation": "literal_replace",
                 "find": "VALUE=old", "replace": "VALUE=new", "expect": {"one": 1, "two": 1}},
            ]
            path = fixture.root / "align-value.json"
            path.write_text(json.dumps(raw), encoding="utf-8")
            manifest = load_manifest(fixture.manifest_path)
            plan = plan_campaign(manifest, fixture.workspace, load_campaign(manifest, path))
            self.assertEqual(6, len(plan.changes))

    def test_campaign_is_preflighted_applied_and_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = FleetFixture(Path(directory))
            fixture.write_manifest()
            fixture.init_repositories()
            campaign_path = fixture.write_campaign()
            manifest = load_manifest(fixture.manifest_path)
            campaign = load_campaign(manifest, campaign_path)
            workspace = resolve_workspace(manifest, None)

            plan = plan_campaign(manifest, workspace, campaign)
            self.assertEqual(2, len(plan.changes))
            self.assertEqual([1, 1], [result.pending for result in plan.results])

            apply_campaign(manifest, workspace, plan, allow_dirty=True)
            for name in ("one", "two"):
                self.assertEqual(
                    "VALUE=new\n",
                    (fixture.workspace / name / "config" / "module.conf").read_text(
                        encoding="utf-8"
                    ),
                )

            second_plan = plan_campaign(manifest, workspace, campaign)
            self.assertEqual(0, len(second_plan.changes))
            self.assertEqual([0, 0], [result.pending for result in second_plan.results])
            self.assertEqual([1, 1], [result.already for result in second_plan.results])

    def test_expectation_mismatch_prevents_all_writes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = FleetFixture(Path(directory))
            fixture.write_manifest()
            fixture.init_repositories()
            campaign_path = fixture.write_campaign(expected_two=2)
            manifest = load_manifest(fixture.manifest_path)
            campaign = load_campaign(manifest, campaign_path)

            with self.assertRaisesRegex(FleetError, "expected 2"):
                plan_campaign(manifest, fixture.workspace, campaign)
            for name in ("one", "two"):
                self.assertEqual(
                    "VALUE=old\n",
                    (fixture.workspace / name / "config" / "module.conf").read_text(
                        encoding="utf-8"
                    ),
                )

    def test_dirty_repositories_are_rejected_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = FleetFixture(Path(directory))
            fixture.write_manifest()
            fixture.init_repositories()
            manifest = load_manifest(fixture.manifest_path)
            campaign = load_campaign(manifest, fixture.write_campaign())
            plan = plan_campaign(manifest, fixture.workspace, campaign)
            with self.assertRaisesRegex(FleetError, "dirty repositories"):
                apply_campaign(manifest, fixture.workspace, plan)

    def test_github_matrix_contains_only_selected_targets(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = FleetFixture(Path(directory))
            fixture.write_manifest()
            text = fixture.manifest_path.read_text(encoding="utf-8")
            text = text.replace(
                'id = "one"\ncheckout = "one"',
                'id = "one"\ngithub = "example/one"\ncheckout = "one"',
            ).replace(
                'id = "two"\ncheckout = "two"',
                'id = "two"\ngithub = "example/two"\ncheckout = "two"',
            ).replace("ci = false", "ci = true")
            fixture.manifest_path.write_text(text, encoding="utf-8")
            manifest = load_manifest(fixture.manifest_path)
            campaign = load_campaign(manifest, fixture.write_campaign())
            matrix = campaign_matrix(manifest, campaign, ["two"], ci_only=True)
            self.assertEqual("two", matrix["include"][0]["id"])


class LedgerTests(unittest.TestCase):
    def test_record_only_entry_with_empty_steps_is_valid(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = FleetFixture(Path(directory))
            fixture.write_manifest()
            path = fixture.write_ledger()
            raw = json.loads(path.read_text(encoding="utf-8"))
            raw["scope"] = {"all": True}
            raw["steps"] = []
            path.write_text(json.dumps(raw), encoding="utf-8")
            entry = load_ledger_entry(load_manifest(fixture.manifest_path), path)
            self.assertTrue(entry.scope_all)
            self.assertEqual((), entry.campaign.steps)

    def test_module_scope_detects_an_omitted_consumer(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = FleetFixture(Path(directory))
            fixture.write_manifest()
            path = fixture.write_ledger()
            raw = json.loads(path.read_text(encoding="utf-8"))
            raw["scope"] = {"module": "trackball"}
            raw["repositories"] = ["one"]
            raw["tracking"] = {"one": raw["tracking"]["one"]}
            raw["steps"] = []
            path.write_text(json.dumps(raw), encoding="utf-8")
            with self.assertRaisesRegex(FleetError, "missing two"):
                load_ledger_entry(load_manifest(fixture.manifest_path), path)

    def test_tracking_must_cover_every_repository(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = FleetFixture(Path(directory))
            fixture.write_manifest()
            path = fixture.write_ledger(
                tracking={"one": {"status": "pending", "pr": None, "commit": None, "notes": ""}}
            )
            with self.assertRaisesRegex(FleetError, "keys must exactly match"):
                load_ledger_entry(load_manifest(fixture.manifest_path), path)

    def test_pr_states_are_synced_and_manual_state_can_be_marked(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = FleetFixture(Path(directory))
            fixture.write_manifest()
            text = fixture.manifest_path.read_text(encoding="utf-8")
            text = text.replace('checkout = "one"', 'github = "example/one"\ncheckout = "one"')
            text = text.replace('checkout = "two"', 'github = "example/two"\ncheckout = "two"')
            fixture.manifest_path.write_text(text, encoding="utf-8")
            manifest = load_manifest(fixture.manifest_path)
            path = fixture.write_ledger()
            entry = load_ledger_entry(manifest, path)

            def fake_fetch(repository: str, branch: str):
                self.assertEqual("fleet/align-value", branch)
                if repository.endswith("/one"):
                    return [{"state": "OPEN", "url": "https://example/pr/1", "updatedAt": "2"}]
                return [{"state": "MERGED", "mergedAt": "now", "url": "https://example/pr/2",
                         "mergeCommit": {"oid": "abc123"}, "updatedAt": "3"}]

            synced = sync_ledger_entry(manifest, entry, write=True, fetcher=fake_fetch)
            self.assertEqual("pr-open", synced["one"].status)
            self.assertEqual("merged", synced["two"].status)
            self.assertEqual("abc123", synced["two"].commit)

            reloaded = load_ledger_entry(manifest, path)
            self.assertEqual("https://example/pr/1", reloaded.tracking["one"].pr)
            mark_ledger_target(reloaded, "one", "applied", commit="def456")
            self.assertEqual("applied", load_ledger_entry(manifest, path).tracking["one"].status)


class AuditTests(unittest.TestCase):
    def test_mirror_drift_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = FleetFixture(Path(directory))
            fixture.write_manifest(mirror=True)
            fixture.init_repositories()
            manifest = load_manifest(fixture.manifest_path)
            repositories = select_repositories(manifest)

            initial = audit_fleet(manifest, fixture.workspace, repositories)
            self.assertFalse(any(issue.subject == "same-config" for issue in initial))

            (fixture.workspace / "two" / "config" / "module.conf").write_text(
                "VALUE=different\n", encoding="utf-8"
            )
            changed = audit_fleet(manifest, fixture.workspace, repositories)
            mirror_issues = [issue for issue in changed if issue.subject == "same-config"]
            self.assertEqual(1, len(mirror_issues))
            self.assertEqual("warning", mirror_issues[0].level)


if __name__ == "__main__":
    unittest.main()
