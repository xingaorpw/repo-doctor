"""检查项定义。

设计原则：每一项都必须能回答"为什么这很重要"，而不是为了凑数。
权重加起来正好 100 分。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable

INSTALL_WORDS = (
    "install", "installation", "quickstart", "quick start",
    "getting started", "setup", "安装", "快速开始", "上手", "开始使用",
)
USAGE_WORDS = ("usage", "example", "how to use", "用法", "使用", "示例", "怎么用")
IMAGE_RE = re.compile(r"!\[[^\]]*\]\([^)]+\)|<img\s", re.IGNORECASE)
HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$", re.MULTILINE)


@dataclass
class CheckResult:
    id: str
    title: str
    level: str  # error / warn / info
    weight: int
    passed: bool
    detail: str
    hint: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "level": self.level,
            "weight": self.weight,
            "passed": self.passed,
            "detail": self.detail,
            "hint": self.hint,
        }


def _readme_headings(readme: str | None) -> list[str]:
    if not readme:
        return []
    return [m.group(2).strip().lower() for m in HEADING_RE.finditer(readme)]


def _has_word(text: str, words: tuple[str, ...]) -> bool:
    return any(w in text for w in words)


def _days_since(ts: str | None) -> float:
    if not ts:
        return 9999.0
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return 9999.0
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - dt).total_seconds() / 86400.0


# --------------------------------------------------------------------------
# 各项检查：返回 (是否通过, 说明, 修复建议)
# --------------------------------------------------------------------------
def check_license(snap: dict) -> tuple[bool, str, str]:
    if snap.get("license"):
        return True, f"已声明 {snap['license']}", ""
    return False, "没有 LICENSE 文件", "没许可证 = 保留所有权利，别人不能合法复用。加一个 MIT"


def check_description(snap: dict) -> tuple[bool, str, str]:
    desc = (snap.get("description") or "").strip()
    if not desc:
        return False, "仓库描述为空", "一句话说清「给谁解决什么问题」，搜索和推荐都靠它"
    if len(desc) < 20:
        return False, f"描述过短（{len(desc)} 字符）", "至少补到 20 字符，说明使用场景"
    return True, f"{len(desc)} 字符", ""


def check_topics(snap: dict) -> tuple[bool, str, str]:
    topics = snap.get("topics") or []
    if len(topics) >= 3:
        return True, f"{len(topics)} 个 topic", ""
    if topics:
        return False, f"只有 {len(topics)} 个 topic", "补到 5–10 个，GitHub 搜索和探索页靠它分类"
    return False, "没有 topic", "右上角 About → ⚙️ → Topics，填 5–10 个"


def check_readme(snap: dict) -> tuple[bool, str, str]:
    readme = snap.get("readme")
    if not readme:
        return False, "没有 README", "README 是仓库的门面，没有它几乎没人会 star"
    if len(readme) < 300:
        return False, f"README 只有 {len(readme)} 字符", "至少包含：是什么、怎么装、怎么用、限制"
    return True, f"{len(readme)} 字符", ""


def check_readme_install(snap: dict) -> tuple[bool, str, str]:
    headings = " ".join(_readme_headings(snap.get("readme")))
    if _has_word(headings, INSTALL_WORDS):
        return True, "有安装/快速开始章节", ""
    return False, "README 里找不到安装说明", "加一个 `## 安装` 或 `## Quick Start`，给出可直接复制的命令"


def check_readme_usage(snap: dict) -> tuple[bool, str, str]:
    headings = " ".join(_readme_headings(snap.get("readme")))
    if _has_word(headings, USAGE_WORDS):
        return True, "有用法/示例章节", ""
    return False, "README 里找不到用法示例", "加一个 `## 用法`，贴一段真实运行输出"


def check_readme_image(snap: dict) -> tuple[bool, str, str]:
    readme = snap.get("readme") or ""
    if IMAGE_RE.search(readme):
        return True, "含图片/截图", ""
    return False, "README 里没有图片", "放一张截图或 GIF，转化率比纯文字高很多"


def check_ci(snap: dict) -> tuple[bool, str, str]:
    files = snap.get("files") or []
    has = any(f.startswith(".github/workflows/") and f.endswith((".yml", ".yaml")) for f in files)
    if has:
        return True, "有 CI 工作流", ""
    return False, "没有 CI", "加一个跑测试的 workflow，README 挂个绿色徽章，可信度立刻不一样"


def check_tests(snap: dict) -> tuple[bool, str, str]:
    files = snap.get("files") or []
    patterns = ("test_", "_test.", "/tests/", "/test/", "spec.")
    hits = [f for f in files if any(p in f.lower() for p in patterns)]
    if hits:
        return True, f"{len(hits)} 个测试文件", ""
    return False, "找不到测试", "哪怕只有 3 个用例，也能证明代码是跑得通的"


def check_gitignore(snap: dict) -> tuple[bool, str, str]:
    files = snap.get("files") or []
    if ".gitignore" in files:
        return True, "有 .gitignore", ""
    return False, "没有 .gitignore", "避免把 __pycache__、.env、*.db 提交上去"


def check_contributing(snap: dict) -> tuple[bool, str, str]:
    files = snap.get("files") or []
    names = {"contributing.md", "code_of_conduct.md", "security.md"}
    hit = [f for f in files if f.lower() in names]
    if hit:
        return True, "有协作规范文件", ""
    return False, "没有 CONTRIBUTING", "可选，但有了会显得项目更正规"


def check_recent_push(snap: dict) -> tuple[bool, str, str]:
    days = _days_since(snap.get("pushed_at"))
    if days <= 180:
        return True, f"{int(days)} 天内有提交", ""
    if days > 9000:
        return False, "没有提交时间", ""
    return False, f"已经 {int(days)} 天没更新", "长期不更新会被认为已废弃；哪怕修个错别字也好"


def check_releases(snap: dict) -> tuple[bool, str, str]:
    n = int(snap.get("releases") or 0)
    if n >= 1:
        return True, f"{n} 个 release", ""
    return False, "没有 release", "打个 v0.1.0 tag，别人就知道该用哪个版本"


CHECKS: list[tuple[str, str, str, int, Callable[[dict], tuple[bool, str, str]]]] = [
    ("license", "许可证", "error", 10, check_license),
    ("description", "仓库描述", "warn", 8, check_description),
    ("topics", "Topics", "warn", 8, check_topics),
    ("readme", "README", "error", 12, check_readme),
    ("readme-install", "安装说明", "warn", 6, check_readme_install),
    ("readme-usage", "用法示例", "warn", 6, check_readme_usage),
    ("readme-image", "截图/图片", "info", 4, check_readme_image),
    ("ci", "持续集成", "warn", 10, check_ci),
    ("tests", "测试", "warn", 10, check_tests),
    ("gitignore", ".gitignore", "info", 4, check_gitignore),
    ("contributing", "协作规范", "info", 4, check_contributing),
    ("recent-push", "近期活跃", "warn", 12, check_recent_push),
    ("releases", "发布版本", "info", 6, check_releases),
]


def run_checks(snap: dict) -> list[CheckResult]:
    results = []
    for cid, title, level, weight, fn in CHECKS:
        passed, detail, hint = fn(snap)
        results.append(
            CheckResult(
                id=cid, title=title, level=level, weight=weight,
                passed=passed, detail=detail, hint=hint,
            )
        )
    return results
