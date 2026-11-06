"""打分与分级。规则简单到可以手算——这是刻意的，分数必须能被解释。"""

from __future__ import annotations

from typing import Any

from .checks import CheckResult

GRADES = ((90, "A"), (75, "B"), (60, "C"), (40, "D"))


def total_score(results: list[CheckResult]) -> int:
    """通过项的权重之和，0–100。"""
    return sum(r.weight for r in results if r.passed)


def max_score(results: list[CheckResult]) -> int:
    return sum(r.weight for r in results)


def grade(score: int) -> str:
    for threshold, letter in GRADES:
        if score >= threshold:
            return letter
    return "F"


def summarize(results: list[CheckResult]) -> dict[str, Any]:
    score = total_score(results)
    passed = [r for r in results if r.passed]
    failed = [r for r in results if not r.passed]
    by_level: dict[str, int] = {"error": 0, "warn": 0, "info": 0}
    for r in failed:
        by_level[r.level] = by_level.get(r.level, 0) + 1

    return {
        "score": score,
        "max": max_score(results),
        "grade": grade(score),
        "passed": len(passed),
        "failed": len(failed),
        "missing_by_level": by_level,
        "results": [r.to_dict() for r in results],
    }


def next_actions(results: list[CheckResult], limit: int = 3) -> list[CheckResult]:
    """按「严重程度 + 分值」排序，给出最该补的几项。"""
    order = {"error": 0, "warn": 1, "info": 2}
    failed = [r for r in results if not r.passed]
    failed.sort(key=lambda r: (order.get(r.level, 9), -r.weight))
    return failed[:limit]
