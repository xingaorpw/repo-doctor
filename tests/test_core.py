"""核心逻辑测试。跑法：python -m unittest discover -s tests -v"""

from __future__ import annotations

import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from repo_doctor import cli, fix, score  # noqa: E402
from repo_doctor.checks import run_checks  # noqa: E402


def now_iso(days_ago: int = 1) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()


def good_snapshot() -> dict:
    readme = (
        "# demo\n\n"
        "## 安装\n\n```bash\npip install demo\n```\n\n"
        "## 用法\n\n```bash\ndemo run\n```\n\n"
        "![screenshot](docs/shot.png)\n\n"
        + "这是一个演示项目，用来验证体检逻辑是否正常工作。" * 12
    )
    return {
        "full_name": "demo/perfect",
        "description": "一个只做一件事并解释为什么这样设计的小工具",
        "topics": ["python", "cli", "tooling"],
        "license": "MIT",
        "readme": readme,
        "files": [
            ".github/workflows/ci.yml",
            "tests/test_a.py",
            ".gitignore",
            "CONTRIBUTING.md",
            "src/a.py",
            "README.md",
        ],
        "releases": 2,
        "pushed_at": now_iso(3),
        "html_url": "https://github.com/demo/perfect",
    }


def empty_snapshot() -> dict:
    return {
        "full_name": "demo/empty",
        "description": None,
        "topics": [],
        "license": None,
        "readme": None,
        "files": [],
        "releases": 0,
        "pushed_at": now_iso(400),
    }


class TestChecks(unittest.TestCase):
    def test_perfect_snapshot_passes_everything(self):
        results = run_checks(good_snapshot())
        failed = [r.id for r in results if not r.passed]
        self.assertEqual(failed, [], f"这些项没通过：{failed}")
        self.assertEqual(score.total_score(results), 100)

    def test_empty_snapshot_fails_everything(self):
        results = run_checks(empty_snapshot())
        self.assertTrue(all(not r.passed for r in results))

    def test_topics_threshold(self):
        snap = good_snapshot()
        snap["topics"] = ["python", "cli"]
        result = next(r for r in run_checks(snap) if r.id == "topics")
        self.assertFalse(result.passed)

        snap["topics"] = ["python", "cli", "tooling"]
        result = next(r for r in run_checks(snap) if r.id == "topics")
        self.assertTrue(result.passed)

    def test_short_description_fails(self):
        snap = good_snapshot()
        snap["description"] = "太短"
        result = next(r for r in run_checks(snap) if r.id == "description")
        self.assertFalse(result.passed)

    def test_readme_without_install_section_fails(self):
        snap = good_snapshot()
        snap["readme"] = "# demo\n\n" + "只有正文没有章节。" * 40
        ids = {r.id: r for r in run_checks(snap)}
        self.assertFalse(ids["readme-install"].passed)
        self.assertFalse(ids["readme-usage"].passed)
        self.assertTrue(ids["readme"].passed)

    def test_missing_ci_and_tests(self):
        snap = good_snapshot()
        snap["files"] = ["README.md", "src/a.py"]
        ids = {r.id: r for r in run_checks(snap)}
        self.assertFalse(ids["ci"].passed)
        self.assertFalse(ids["tests"].passed)

    def test_stale_repo_fails_recent_push(self):
        snap = good_snapshot()
        snap["pushed_at"] = now_iso(400)
        ids = {r.id: r for r in run_checks(snap)}
        self.assertFalse(ids["recent-push"].passed)

    def test_no_license_is_error_level(self):
        snap = good_snapshot()
        snap["license"] = None
        result = next(r for r in run_checks(snap) if r.id == "license")
        self.assertEqual(result.level, "error")
        self.assertFalse(result.passed)


class TestScore(unittest.TestCase):
    def test_grade_boundaries(self):
        self.assertEqual(score.grade(100), "A")
        self.assertEqual(score.grade(90), "A")
        self.assertEqual(score.grade(89), "B")
        self.assertEqual(score.grade(75), "B")
        self.assertEqual(score.grade(74), "C")
        self.assertEqual(score.grade(60), "C")
        self.assertEqual(score.grade(59), "D")
        self.assertEqual(score.grade(40), "D")
        self.assertEqual(score.grade(39), "F")
        self.assertEqual(score.grade(0), "F")

    def test_summary_shape(self):
        summary = score.summarize(run_checks(empty_snapshot()))
        self.assertEqual(summary["score"], 0)
        self.assertEqual(summary["grade"], "F")
        self.assertEqual(summary["max"], 100)
        self.assertEqual(len(summary["results"]), 13)

    def test_next_actions_prefers_errors(self):
        nexts = score.next_actions(run_checks(empty_snapshot()))
        self.assertEqual(len(nexts), 3)
        self.assertEqual(nexts[0].level, "error")

    def test_next_actions_empty_when_perfect(self):
        self.assertEqual(score.next_actions(run_checks(good_snapshot())), [])


class TestFix(unittest.TestCase):
    def test_plan_generates_expected_files(self):
        planned = {f["path"] for f in fix.plan(empty_snapshot())}
        self.assertEqual(
            planned,
            {"LICENSE", ".gitignore", ".github/workflows/ci.yml", "CONTRIBUTING.md"},
        )

    def test_plan_skips_existing(self):
        planned = {f["path"] for f in fix.plan(good_snapshot())}
        self.assertEqual(planned, set())

    def test_write_creates_files_and_does_not_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            written = fix.write(fix.plan(empty_snapshot()), tmp)
            self.assertEqual(len(written), 4)
            lic = Path(tmp) / "LICENSE"
            self.assertIn("MIT License", lic.read_text(encoding="utf-8"))

            again = fix.write(fix.plan(empty_snapshot()), tmp)
            self.assertEqual(again, [])

    def test_python_language_gets_python_gitignore(self):
        snap = empty_snapshot()
        snap["language"] = "Python"
        files = {f["path"]: f["content"] for f in fix.plan(snap)}
        self.assertIn("__pycache__", files[".gitignore"])

    def test_node_language_gets_node_gitignore(self):
        snap = empty_snapshot()
        snap["language"] = "TypeScript"
        files = {f["path"]: f["content"] for f in fix.plan(snap)}
        self.assertIn("node_modules", files[".gitignore"])


class TestCli(unittest.TestCase):
    def test_parse_target_plain(self):
        self.assertEqual(cli.parse_target("owner/repo"), "owner/repo")

    def test_parse_target_url(self):
        self.assertEqual(
            cli.parse_target("https://github.com/owner/repo/"),
            "owner/repo",
        )

    def test_parse_target_url_with_git_suffix(self):
        self.assertEqual(
            cli.parse_target("https://github.com/owner/repo.git"),
            "owner/repo",
        )

    def test_parse_target_rejects_garbage(self):
        with self.assertRaises(ValueError):
            cli.parse_target("not-a-repo")

    def test_render_contains_score_and_marks(self):
        snap = good_snapshot()
        results = run_checks(snap)
        summary = score.summarize(results)
        text = cli.render(snap, results, summary, score.next_actions(results), color=False)
        self.assertIn("repo-doctor", text)
        self.assertIn("100 / 100", text)
        self.assertIn("✓", text)

    def test_main_returns_2_on_bad_target(self):
        self.assertEqual(cli.main(["not-a-repo", "--no-color"]), 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
