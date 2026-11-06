"""`--fix` 模式：把能自动补的文件直接生成出来。

原则：只生成"没有争议的默认值"，不猜业务逻辑。
生成的每个文件都会告诉用户它是从哪来的。
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

MIT = """MIT License

Copyright (c) {year} {author}

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

GITIGNORE_PY = """__pycache__/
*.py[cod]
*.egg-info/
.venv/
venv/
.env
*.db
*.sqlite3
.pytest_cache/
.mypy_cache/
.DS_Store
"""

GITIGNORE_NODE = """node_modules/
dist/
build/
coverage/
.env
*.log
.DS_Store
"""

GITIGNORE_GENERIC = """.env
*.log
.DS_Store
Thumbs.db
"""

CI_PY = """name: tests

on:
  push:
    branches: [main]
  pull_request:

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      fail-fast: false
      matrix:
        python-version: ["3.10", "3.11", "3.12", "3.13"]

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python ${{ matrix.python-version }}
        uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          if [ -f requirements.txt ]; then pip install -r requirements.txt; fi

      - name: Run tests
        run: python -m unittest discover -s tests -v
"""

CI_NODE = """name: tests

on:
  push:
    branches: [main]
  pull_request:

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      fail-fast: false
      matrix:
        node-version: [18, 20, 22]

    steps:
      - uses: actions/checkout@v4

      - name: Set up Node ${{ matrix.node-version }}
        uses: actions/setup-node@v4
        with:
          node-version: ${{ matrix.node-version }}

      - name: Run tests
        run: npm test
"""

CONTRIBUTING = """# Contributing

感谢愿意花时间改进这个项目。

## 提 issue

- 先说清楚**你想做什么**，再说**现在发生了什么**
- 附上复现步骤和环境（系统、版本）
- 截图比文字有用

## 提 PR

1. Fork 并新建分支：`git checkout -b fix/短描述`
2. 改动尽量小，一个 PR 只做一件事
3. 补上对应的测试
4. 提交信息用 `feat:` / `fix:` / `docs:` / `test:` 前缀
5. 确保 CI 是绿的

## 代码风格

跟着现有代码走，不要顺手重构无关文件。
"""


def _author(snap: dict[str, Any]) -> str:
    full = snap.get("full_name") or "owner/repo"
    return full.split("/")[0]


def _lang(snap: dict[str, Any]) -> str:
    return (snap.get("language") or "").lower()


def plan(snap: dict[str, Any]) -> list[dict[str, str]]:
    """根据快照决定要生成哪些文件。返回 [{path, content, why}]。"""
    files = set(snap.get("files") or [])
    out: list[dict[str, str]] = []
    year = datetime.now(timezone.utc).year
    lang = _lang(snap)

    if not snap.get("license"):
        out.append({
            "path": "LICENSE",
            "content": MIT.format(year=year, author=_author(snap)),
            "why": "缺许可证，默认是「保留所有权利」",
        })

    if ".gitignore" not in files:
        if "python" in lang:
            body = GITIGNORE_PY
        elif lang in ("javascript", "typescript"):
            body = GITIGNORE_NODE
        else:
            body = GITIGNORE_GENERIC
        out.append({"path": ".gitignore", "content": body, "why": "避免把缓存和密钥提交上去"})

    has_ci = any(f.startswith(".github/workflows/") for f in files)
    if not has_ci:
        if "python" in lang:
            body = CI_PY
        elif lang in ("javascript", "typescript"):
            body = CI_NODE
        else:
            body = CI_PY
        out.append({"path": ".github/workflows/ci.yml", "content": body, "why": "缺 CI，加一个跑测试的工作流"})

    if "contributing.md" not in {f.lower() for f in files}:
        out.append({"path": "CONTRIBUTING.md", "content": CONTRIBUTING, "why": "缺协作规范"})

    return out


def write(files: list[dict[str, str]], outdir: Path | str) -> list[str]:
    """写到目标目录，返回实际写出的相对路径。已存在的文件不覆盖。"""
    root = Path(outdir)
    root.mkdir(parents=True, exist_ok=True)
    written: list[str] = []
    for f in files:
        target = root / f["path"]
        if target.exists():
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(f["content"], encoding="utf-8", newline="\n")
        written.append(f["path"])
    return written
