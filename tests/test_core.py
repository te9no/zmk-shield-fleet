from __future__ import annotations

import json
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest import mock

from scripts.build_dashboard import build_profile
from zmk_shield_fleet.core import (
    FleetError,
    apply_campaign,
    audit_fleet,
    campaign_matrix,
    evidence_audit,
    load_campaign,
    load_ledger_entry,
    load_manifest,
    mark_ledger_target,
    plan_campaign,
    resolve_workspace,
    revision_baseline_issues,
    revision_findings,
    select_repositories,
    sync_ledger_entry,
    target_validation_complete,
    validate_next_action_references,
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
                maintenance_branch = "validation"
                architecture = "snippets"
                modules = ["trackball"]
                tags = ["test"]
                required_globs = ["config/*.conf"]
                ci = false

                [[repositories]]
                id = "two"
                checkout = "two"
                default_branch = "main"
                maintenance_branch = "validation"
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
                ["git", "init", "-q", "-b", "validation", str(root)],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            subprocess.run(["git", "-C", str(root), "add", "."], check=True)
            subprocess.run(
                [
                    "git", "-C", str(root), "-c", "user.name=Fleet Test",
                    "-c", "user.email=fleet@example.invalid", "commit", "-qm", "fixture",
                ],
                check=True,
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

    def test_unknown_keys_and_http_urls_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = FleetFixture(Path(directory))
            fixture.write_manifest()
            text = fixture.manifest_path.read_text(encoding="utf-8")
            fixture.manifest_path.write_text(
                text.replace('id = "one"', 'id = "one"\nrolluot_enabled = true', 1),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(FleetError, "unknown key.*rolluot_enabled"):
                load_manifest(fixture.manifest_path)

            fixture.write_manifest()
            with fixture.manifest_path.open("a", encoding="utf-8") as handle:
                handle.write(textwrap.dedent("""

                    [[next_actions]]
                    id = "unsafe-url"
                    state = "active"
                    priority = "high"
                    order = 1
                    repository = "one"
                    action = "Inspect"
                    completion = "Done"
                    blocker = ""
                    pr = "http://github.com/example/one/pull/1"
                """))
            with self.assertRaisesRegex(FleetError, "public HTTPS URL"):
                load_manifest(fixture.manifest_path)

    def test_rollout_requires_explicit_nondefault_owned_branch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = FleetFixture(Path(directory))
            fixture.write_manifest()
            text = fixture.manifest_path.read_text(encoding="utf-8")
            text = text.replace(
                'id = "one"\ncheckout = "one"',
                'id = "one"\ngithub = "outside/one"\nrollout_enabled = true\ncheckout = "one"',
            )
            fixture.manifest_path.write_text(text, encoding="utf-8")
            with self.assertRaisesRegex(FleetError, "allow_external"):
                load_manifest(fixture.manifest_path)

            text = text.replace('github = "outside/one"', 'github = "example/one"')
            text = text.replace('maintenance_branch = "validation"', 'maintenance_branch = "main"', 1)
            fixture.manifest_path.write_text(text, encoding="utf-8")
            with self.assertRaisesRegex(FleetError, "must differ"):
                load_manifest(fixture.manifest_path)

    def test_next_actions_are_validated_and_sorted(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = FleetFixture(Path(directory))
            fixture.write_manifest()
            with fixture.manifest_path.open("a", encoding="utf-8") as manifest_file:
                manifest_file.write(
                    textwrap.dedent(
                        """

                        [[next_actions]]
                        id = "hardware-wait"
                        state = "waiting"
                        priority = "high"
                        order = 2
                        repository = "one"
                        action = "Validate hardware"
                        completion = "Hardware passes"
                        blocker = "Waiting for hardware"
                        pr = "https://github.com/example/one/pull/1"

                        [[next_actions]]
                        id = "fix-ci"
                        state = "active"
                        priority = "medium"
                        order = 1
                        repository = "external-module"
                        repository_url = "https://github.com/example/external-module"
                        action = "Repair CI"
                        completion = "CI passes"
                        blocker = ""
                        """
                    )
                )
            manifest = load_manifest(fixture.manifest_path)
            self.assertEqual(["fix-ci", "hardware-wait"], [item.id for item in manifest.next_actions])
            self.assertEqual("external-module", manifest.next_actions[0].repository)
            self.assertEqual("https://github.com/example/one/pull/1", manifest.next_actions[1].pr)
            dashboard_profile = build_profile(fixture.manifest_path)
            self.assertEqual("fix-ci", dashboard_profile["next_actions"][0]["id"])
            self.assertEqual("waiting", dashboard_profile["next_actions"][1]["state"])

    def test_invalid_next_action_state_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = FleetFixture(Path(directory))
            fixture.write_manifest()
            with fixture.manifest_path.open("a", encoding="utf-8") as manifest_file:
                manifest_file.write(
                    textwrap.dedent(
                        """

                        [[next_actions]]
                        id = "bad-state"
                        state = "soon"
                        priority = "high"
                        order = 1
                        repository = "one"
                        action = "Do work"
                        completion = "Done"
                        blocker = ""
                        """
                    )
                )
            with self.assertRaisesRegex(FleetError, "state must be one of"):
                load_manifest(fixture.manifest_path)


class CampaignTests(unittest.TestCase):
    def test_unknown_step_key_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = FleetFixture(Path(directory))
            fixture.write_manifest()
            raw = json.loads(fixture.write_campaign().read_text(encoding="utf-8"))
            raw["steps"][0]["already_patterns"] = "VALUE=new"
            path = fixture.root / "align-value.json"
            path.write_text(json.dumps(raw), encoding="utf-8")
            with self.assertRaisesRegex(FleetError, "unknown key.*already_patterns"):
                load_campaign(load_manifest(fixture.manifest_path), path)

    def test_default_branch_requires_explicit_override(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = FleetFixture(Path(directory))
            fixture.write_manifest()
            fixture.init_repositories()
            text = fixture.manifest_path.read_text(encoding="utf-8").replace(
                'maintenance_branch = "validation"', 'maintenance_branch = "main"'
            )
            fixture.manifest_path.write_text(text, encoding="utf-8")
            for name in ("one", "two"):
                subprocess.run(
                    ["git", "-C", str(fixture.workspace / name), "branch", "-m", "main"],
                    check=True,
                )
            manifest = load_manifest(fixture.manifest_path)
            campaign = load_campaign(manifest, fixture.write_campaign())
            with self.assertRaisesRegex(FleetError, "stable/default"):
                plan_campaign(manifest, fixture.workspace, campaign)
            plan = plan_campaign(
                manifest, fixture.workspace, campaign, allow_default_branch=True
            )
            self.assertEqual(2, len(plan.changes))

    def test_apply_rechecks_files_and_rolls_back_partial_failure(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = FleetFixture(Path(directory))
            fixture.write_manifest()
            fixture.init_repositories()
            manifest = load_manifest(fixture.manifest_path)
            campaign = load_campaign(manifest, fixture.write_campaign())
            plan = plan_campaign(manifest, fixture.workspace, campaign)

            first = fixture.workspace / "one" / "config" / "module.conf"
            first.write_text("VALUE=changed-after-plan\n", encoding="utf-8")
            with self.assertRaisesRegex(FleetError, "changed after planning"):
                apply_campaign(manifest, fixture.workspace, plan, allow_dirty=True)
            first.write_text("VALUE=old\n", encoding="utf-8")

            real_replace = __import__("os").replace
            failed = False

            def flaky_replace(source, destination):
                nonlocal failed
                if (
                    not failed
                    and str(source).endswith(".fleet-tmp")
                    and Path(destination).parts[-3:] == ("two", "config", "module.conf")
                ):
                    failed = True
                    raise OSError("injected replacement failure")
                return real_replace(source, destination)

            with mock.patch("zmk_shield_fleet.core.os.replace", side_effect=flaky_replace):
                with self.assertRaisesRegex(FleetError, "rolled back"):
                    apply_campaign(manifest, fixture.workspace, plan, allow_dirty=True)
            for name in ("one", "two"):
                self.assertEqual(
                    "VALUE=old\n",
                    (fixture.workspace / name / "config" / "module.conf").read_text(
                        encoding="utf-8"
                    ),
                )

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
            (fixture.workspace / "one" / "unrelated.tmp").write_text("dirty", encoding="utf-8")
            with self.assertRaisesRegex(FleetError, "dirty repositories"):
                apply_campaign(manifest, fixture.workspace, plan)

    def test_github_matrix_contains_only_selected_targets(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = FleetFixture(Path(directory))
            fixture.write_manifest()
            text = fixture.manifest_path.read_text(encoding="utf-8")
            text = text.replace(
                'id = "one"\ncheckout = "one"',
                'id = "one"\ngithub = "example/one"\nrollout_enabled = true\ncheckout = "one"',
            ).replace(
                'id = "two"\ncheckout = "two"',
                'id = "two"\ngithub = "example/two"\nrollout_enabled = true\ncheckout = "two"',
            ).replace("ci = false", "ci = true")
            fixture.manifest_path.write_text(text, encoding="utf-8")
            manifest = load_manifest(fixture.manifest_path)
            campaign = load_campaign(manifest, fixture.write_campaign())
            matrix = campaign_matrix(manifest, campaign, ["two"], ci_only=True)
            self.assertEqual("two", matrix["include"][0]["id"])


class LedgerTests(unittest.TestCase):
    def test_next_action_references_typed_ledger_fields(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = FleetFixture(Path(directory))
            fixture.write_manifest()
            with fixture.manifest_path.open("a", encoding="utf-8") as handle:
                handle.write(textwrap.dedent("""

                    [[next_actions]]
                    id = "validate-left"
                    state = "active"
                    priority = "high"
                    order = 1
                    repository = "one"
                    action = "Validate left"
                    completion = "Hardware passes"
                    blocker = ""
                    change_id = "align-value"
                    validation_keys = ["hardware"]
                    variant_ids = ["left"]
                    evidence = [
                      { label = "Hardware log", status = "pending", url = "https://github.com/example/one/actions/runs/1" },
                    ]
                """))
            path = fixture.write_ledger()
            raw = json.loads(path.read_text(encoding="utf-8"))
            raw["tracking"]["one"]["variants"] = [
                {"id": "left", "status": "pending", "validation": {"hardware": "pending"}}
            ]
            path.write_text(json.dumps(raw), encoding="utf-8")
            manifest = load_manifest(fixture.manifest_path)
            entry = load_ledger_entry(manifest, path)
            validate_next_action_references(manifest, [entry])
            raw["tracking"]["one"]["variants"] = []
            path.write_text(json.dumps(raw), encoding="utf-8")
            with self.assertRaisesRegex(FleetError, "unknown validation"):
                validate_next_action_references(
                    manifest, [load_ledger_entry(manifest, path)]
                )

    def test_not_applicable_validation_contradiction_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = FleetFixture(Path(directory))
            fixture.write_manifest()
            path = fixture.write_ledger()
            raw = json.loads(path.read_text(encoding="utf-8"))
            raw["tracking"]["one"].update(
                {"status": "not-applicable", "validation": {"hardware": "waived"}}
            )
            path.write_text(json.dumps(raw), encoding="utf-8")
            with self.assertRaisesRegex(FleetError, "not-applicable.*validation"):
                load_ledger_entry(load_manifest(fixture.manifest_path), path)

    def test_variant_validation_is_typed_and_required_for_completion(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = FleetFixture(Path(directory))
            fixture.write_manifest()
            path = fixture.write_ledger()
            raw = json.loads(path.read_text(encoding="utf-8"))
            raw["tracking"]["one"].update(
                {
                    "status": "applied",
                    "validation": {"ci": "passed"},
                    "required_validation": ["ci"],
                    "branch": "zmk-0.4",
                    "base_branch": "validation",
                    "pr_head": "a" * 40,
                    "variants": [
                        {
                            "id": "left",
                            "status": "pending",
                            "validation": {"hardware": "pending"},
                        }
                    ],
                }
            )
            path.write_text(json.dumps(raw), encoding="utf-8")
            target = load_ledger_entry(load_manifest(fixture.manifest_path), path).tracking["one"]
            self.assertFalse(target_validation_complete(target))
            raw["tracking"]["one"]["variants"][0]["status"] = "passed"
            raw["tracking"]["one"]["variants"][0]["validation"]["hardware"] = "passed"
            path.write_text(json.dumps(raw), encoding="utf-8")
            target = load_ledger_entry(load_manifest(fixture.manifest_path), path).tracking["one"]
            self.assertTrue(target_validation_complete(target))

    def test_terminal_without_validation_is_not_complete(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = FleetFixture(Path(directory))
            fixture.write_manifest()
            path = fixture.write_ledger()
            raw = json.loads(path.read_text(encoding="utf-8"))
            raw["tracking"]["one"]["status"] = "applied"
            path.write_text(json.dumps(raw), encoding="utf-8")
            target = load_ledger_entry(load_manifest(fixture.manifest_path), path).tracking["one"]
            self.assertFalse(target_validation_complete(target))

    def test_applied_can_retain_pending_hardware_validation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = FleetFixture(Path(directory))
            fixture.write_manifest()
            path = fixture.write_ledger()
            raw = json.loads(path.read_text(encoding="utf-8"))
            raw["tracking"]["one"].update(
                {"status": "applied", "validation": {"ci": "passed", "hardware": "pending"}}
            )
            path.write_text(json.dumps(raw), encoding="utf-8")
            entry = load_ledger_entry(load_manifest(fixture.manifest_path), path)
            self.assertEqual("applied", entry.tracking["one"].status)
            self.assertEqual("pending", entry.tracking["one"].validation["hardware"])

    def test_mark_updates_validation_independently_from_applied_status(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = FleetFixture(Path(directory))
            fixture.write_manifest()
            path = fixture.write_ledger()
            raw = json.loads(path.read_text(encoding="utf-8"))
            raw["tracking"]["one"]["validation"] = {"ci": "passed", "hardware": "pending"}
            path.write_text(json.dumps(raw), encoding="utf-8")
            manifest = load_manifest(fixture.manifest_path)
            entry = load_ledger_entry(manifest, path)

            mark_ledger_target(entry, "one", "applied")
            self.assertEqual(
                "pending",
                load_ledger_entry(manifest, path).tracking["one"].validation["hardware"],
            )
            mark_ledger_target(
                entry,
                "one",
                "applied",
                validation={"hardware": "passed"},
                validation_urls={"hardware": "https://example.com/checklist"},
            )
            reloaded = load_ledger_entry(load_manifest(fixture.manifest_path), path)
            self.assertEqual("applied", reloaded.tracking["one"].status)
            self.assertEqual("passed", reloaded.tracking["one"].validation["hardware"])
            self.assertEqual(
                "https://example.com/checklist",
                reloaded.tracking["one"].validation_urls["hardware"],
            )

    def test_dashboard_build_rejects_an_invalid_ledger(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = FleetFixture(Path(directory))
            fixture.write_manifest()
            raw = json.loads(fixture.write_ledger().read_text(encoding="utf-8"))
            raw["tracking"]["one"]["validation"] = {"ci": "unknown"}
            changes = fixture.root / "changes"
            changes.mkdir()
            (changes / "align-value.json").write_text(json.dumps(raw), encoding="utf-8")

            with self.assertRaisesRegex(FleetError, "validation.ci must be one of"):
                build_profile(fixture.manifest_path)

    def test_dashboard_completion_requires_passed_or_waived_validation(self) -> None:
        app_js = (Path(__file__).resolve().parents[1] / "site" / "app.js").read_text(
            encoding="utf-8"
        )
        self.assertIn(
            'checks.every((status) => status === "passed" || status === "waived")',
            app_js,
        )
        self.assertNotIn('if (target.status === "not-applicable") return true;', app_js)
        self.assertIn("action.repository_url", app_js)

    def test_validation_url_requires_a_matching_check(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = FleetFixture(Path(directory))
            fixture.write_manifest()
            path = fixture.write_ledger()
            raw = json.loads(path.read_text(encoding="utf-8"))
            raw["tracking"]["one"]["validation_urls"] = {
                "hardware": "https://example.com/checklist"
            }
            path.write_text(json.dumps(raw), encoding="utf-8")
            with self.assertRaisesRegex(FleetError, "no matching validation check"):
                load_ledger_entry(load_manifest(fixture.manifest_path), path)

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

            def fake_fetch(repository: str, branch: str, base_branch: str):
                self.assertEqual("fleet/align-value", branch)
                self.assertEqual("validation", base_branch)
                if repository.endswith("/one"):
                    return [{"state": "OPEN", "url": "https://example/pr/1", "updatedAt": "2"}]
                return [{"state": "MERGED", "mergedAt": "now", "url": "https://example/pr/2",
                         "mergeCommit": {"oid": "a" * 40}, "updatedAt": "3"}]

            synced = sync_ledger_entry(manifest, entry, write=True, fetcher=fake_fetch)
            self.assertEqual("pr-open", synced["one"].status)
            self.assertEqual("merged", synced["two"].status)
            self.assertEqual("a" * 40, synced["two"].commit)

            reloaded = load_ledger_entry(manifest, path)
            self.assertEqual("https://example/pr/1", reloaded.tracking["one"].pr)
            mark_ledger_target(reloaded, "one", "applied", commit="d" * 40)
            self.assertEqual("applied", load_ledger_entry(manifest, path).tracking["one"].status)

    def test_sync_stops_when_multiple_prs_match(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = FleetFixture(Path(directory))
            fixture.write_manifest()
            text = fixture.manifest_path.read_text(encoding="utf-8")
            text = text.replace('checkout = "one"', 'github = "example/one"\ncheckout = "one"')
            text = text.replace('checkout = "two"', 'github = "example/two"\ncheckout = "two"')
            fixture.manifest_path.write_text(text, encoding="utf-8")
            manifest = load_manifest(fixture.manifest_path)
            entry = load_ledger_entry(manifest, fixture.write_ledger())
            candidates = [
                {"number": 1, "url": "https://github.com/example/one/pull/1"},
                {"number": 2, "url": "https://github.com/example/one/pull/2"},
            ]
            with self.assertRaisesRegex(FleetError, "multiple PR candidates"):
                sync_ledger_entry(
                    manifest, entry, fetcher=lambda repository, head, base: candidates
                )

    def test_sync_stops_when_pr_head_sha_disagrees(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = FleetFixture(Path(directory))
            fixture.write_manifest()
            text = fixture.manifest_path.read_text(encoding="utf-8")
            text = text.replace('checkout = "one"', 'github = "example/one"\ncheckout = "one"')
            fixture.manifest_path.write_text(text, encoding="utf-8")
            path = fixture.write_ledger()
            raw = json.loads(path.read_text(encoding="utf-8"))
            raw["tracking"]["one"].update(
                {"branch": "fleet/align-value", "base_branch": "validation", "pr_head": "a" * 40}
            )
            raw["tracking"]["two"]["status"] = "not-applicable"
            path.write_text(json.dumps(raw), encoding="utf-8")
            manifest = load_manifest(fixture.manifest_path)
            entry = load_ledger_entry(manifest, path)
            candidate = [{
                "state": "OPEN",
                "url": "https://github.com/example/one/pull/1",
                "headRefName": "fleet/align-value",
                "baseRefName": "validation",
                "headRefOid": "b" * 40,
            }]
            with self.assertRaisesRegex(FleetError, "head SHA mismatch"):
                sync_ledger_entry(
                    manifest, entry, fetcher=lambda repository, head, base: candidate
                )


class AuditTests(unittest.TestCase):
    def test_revision_baseline_detects_increase(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = FleetFixture(Path(directory))
            fixture.write_manifest()
            path = fixture.write_ledger()
            raw = json.loads(path.read_text(encoding="utf-8"))
            raw["tracking"]["one"]["findings"] = 0
            raw["tracking"]["two"]["findings"] = 0
            path.write_text(json.dumps(raw), encoding="utf-8")
            manifest = load_manifest(fixture.manifest_path)
            entry = load_ledger_entry(manifest, path)
            finding = type("Finding", (), {"repository": "one"})()
            issues = revision_baseline_issues(
                entry, [finding], select_repositories(manifest)
            )
            self.assertEqual("error", issues[0].level)
            self.assertIn("increased", issues[0].message)

    def test_remote_evidence_compares_pr_state_base_head_and_ci(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = FleetFixture(Path(directory))
            fixture.write_manifest()
            text = fixture.manifest_path.read_text(encoding="utf-8").replace(
                'checkout = "one"', 'github = "example/one"\ncheckout = "one"'
            )
            fixture.manifest_path.write_text(text, encoding="utf-8")
            path = fixture.write_ledger()
            raw = json.loads(path.read_text(encoding="utf-8"))
            raw["tracking"]["one"].update(
                {
                    "status": "pr-open",
                    "pr": "https://github.com/example/one/pull/1",
                    "base_branch": "validation",
                    "branch": "fleet/align-value",
                    "pr_head": "a" * 40,
                    "validation": {"ci": "passed"},
                }
            )
            path.write_text(json.dumps(raw), encoding="utf-8")
            manifest = load_manifest(fixture.manifest_path)
            entry = load_ledger_entry(manifest, path)
            issues = evidence_audit(
                manifest,
                [entry],
                fetcher=lambda url: {
                    "url": url,
                    "state": "OPEN",
                    "baseRefName": "validation",
                    "headRefName": "fleet/align-value",
                    "headRefOid": "a" * 40,
                    "statusCheckRollup": [{"conclusion": "FAILURE"}],
                },
                branch_fetcher=lambda repository, branch: {"commit": {"sha": "a" * 40}},
            )
            self.assertEqual(1, len(issues))
            self.assertIn("marks CI passed", issues[0].message)

    def test_revision_audit_finds_moving_refs_and_short_shas(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = FleetFixture(Path(directory))
            fixture.write_manifest()
            fixture.init_repositories()
            (fixture.workspace / "one" / "config" / "west.yml").write_text(
                "revision: main\nrevision: abc1234\nrevision: v1.2.3\n", encoding="utf-8"
            )
            manifest = load_manifest(fixture.manifest_path)
            findings = revision_findings(
                fixture.workspace, select_repositories(manifest, ["one"])
            )
            self.assertEqual(["moving-ref", "short-sha"], [item.kind for item in findings])
            strict = revision_findings(
                fixture.workspace, select_repositories(manifest, ["one"]), strict_sha=True
            )
            self.assertEqual(3, len(strict))

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
