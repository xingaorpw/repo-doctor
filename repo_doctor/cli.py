"""命令行界面。render() 是纯函数，方便测试。"""

from __future__ import annotations

import argparse
import json
import sys
import unicodedata
from pathlib import Path
from typing import Any

from . import fix, github, score
from .checks import CheckResult, run_checks

RESET = "\033[0m"
GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
DIM = "\033[2m"
BOLD = "\033[1m"


def _utf8() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        except (AttributeError, ValueError):
            pass


def _width(text: str) -> int:
    """终端显示宽度：CJK 算两格。"""
    return sum(2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1 for ch in text)


def _pad(text: str, width: int) -> str:
    return text + " " * max(0, width - _width(text))


def _c(text: str, color: str, enabled: bool) -> str:
    return f"{color}{text}{RESET}" if enabled else text


def parse_target(raw: str) -> str:
    """接受 owner/repo 或完整 URL。"""
    raw = raw.strip().rstrip("/")
    if raw.startswith("http"):
        parts = [p for p in raw.split("/") if p and ":" not in p]
        if len(parts) >= 3:
            return f"{parts[1]}/{parts[2]}".removesuffix(".git")
        raise ValueError(f"看不懂这个地址：{raw}")
    if raw.count("/") != 1:
        raise ValueError(f"要的是 owner/repo，收到：{raw}")
    return raw


def render(
    snap: dict[str, Any],
    results: list[CheckResult],
    summary: dict[str, Any],
    nexts: list[CheckResult],
    color: bool = True,
) -> str:
    lines: list[str] = []
    lines.append(
        _c("repo-doctor", BOLD, color) + _c(f" · {snap.get('full_name')}", DIM, color)
    )
    if snap.get("html_url"):
        lines.append(_c(snap["html_url"], DIM, color))
    lines.append("")

    for r in results:
        mark = _c("✓", GREEN, color) if r.passed else _c("✗", RED if r.level == "error" else YELLOW, color)
        pts = _c(f"+{r.weight}" if r.passed else "+0", DIM, color)
        lines.append(
            f"  {mark}  {_pad(r.title, 14)} {_pad(r.detail, 34)} {pts:>4}"
        )
        if not r.passed and r.hint:
            lines.append(_c(f"       ↳ {r.hint}", DIM, color))

    lines.append("")
    lines.append(_c("─" * 62, DIM, color))
    score_line = f"  {summary['score']} / {summary['max']}   {summary['grade']}    通过 {summary['passed']} / {len(results)}"
    lines.append(_c(score_line, BOLD, color))
    if nexts:
        todo = "、".join(f"{r.title}（{r.weight} 分）" for r in nexts)
        lines.append(_c(f"  下一步：{todo}", DIM, color))
    return "\n".join(lines)


def build_snapshot(target: str, token: str | None) -> dict[str, Any]:
    client = github.GitHubClient(token=token)
    return client.snapshot(target)


def main(argv: list[str] | None = None) -> int:
    _utf8()
    parser = argparse.ArgumentParser(
        prog="repo-doctor",
        description="给 GitHub 仓库做发布体检：缺什么、值多少分、怎么补",
    )
    parser.add_argument("repo", help="owner/repo 或完整仓库地址")
    parser.add_argument("--json", action="store_true", help="输出机器可读的 JSON")
    parser.add_argument("--fix", metavar="DIR", help="把缺失的文件生成到指定目录")
    parser.add_argument("--min-score", type=int, default=None, help="低于该分数时退出码为 1")
    parser.add_argument("--no-color", action="store_true", help="关闭颜色")
    parser.add_argument("--token", default=None, help="GitHub token，不填则读 GITHUB_TOKEN")
    args = parser.parse_args(argv)

    try:
        target = parse_target(args.repo)
    except ValueError as exc:
        print(f"参数错误：{exc}", file=sys.stderr)
        return 2

    try:
        snap = build_snapshot(target, args.token)
    except github.GitHubError as exc:
        print(f"抓取失败：{exc}", file=sys.stderr)
        return 1

    results = run_checks(snap)
    summary = score.summarize(results)
    nexts = score.next_actions(results)

    if args.json:
        payload = {"repo": snap.get("full_name"), "snapshot": {
            "description": snap.get("description"),
            "topics": snap.get("topics"),
            "license": snap.get("license"),
            "stars": snap.get("stars"),
            "language": snap.get("language"),
        }, **summary}
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        color = not args.no_color and sys.stdout.isatty()
        print(render(snap, results, summary, nexts, color=color))

    if args.fix:
        files = fix.plan(snap)
        written = fix.write(files, Path(args.fix))
        print()
        if written:
            print(f"已生成 {len(written)} 个文件到 {args.fix}：")
            for p in written:
                print(f"  + {p}")
        else:
            print("没有需要生成的文件（或目标已存在）。")

    if args.min_score is not None and summary["score"] < args.min_score:
        print(f"\n分数 {summary['score']} 低于阈值 {args.min_score}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
