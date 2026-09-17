#!/usr/bin/env python3
# sanitized template — 실제 값은 로컬 ROUTINE-CONFIG에서 주입된다.
"""prior-review.py <project> <repository> <pullRequestId>

한 PR의 이전 리뷰 기록을 세 원장에서 걸러 준다. deploy-approve-intake가 PR 하나
때문에 review-findings.jsonl 88KB와 reviewedPrs 52KB를 통째로 읽었다(2026-09-17
실측). 세션은 이 출력만 본다.

  summary   pr-review-summary.jsonl 에서 그 PR의 가장 늦은 줄 (없으면 null)
  reviewed  marks/pr-review-intake.json 의 reviewedPrs 중 그 PR의 가장 늦은 항목
  findings  review-findings.jsonl 중 그 PR의 줄 전부
"""
import json
import os
import sys
from pathlib import Path

ROOT = Path(os.environ.get("ROUTINE_STATE_ROOT") or Path(__file__).resolve().parent.parent / "state")


def lines(path):
    if not path.exists():
        return
    for raw in path.read_text().splitlines():
        raw = raw.strip()
        if not raw:
            continue
        try:
            yield json.loads(raw)
        except json.JSONDecodeError:
            continue


def main(argv):
    if len(argv) != 3:
        print("usage: prior-review.py <project> <repository> <pullRequestId>", file=sys.stderr)
        return 2
    project, repository, pr_id = argv
    key = f"{project}/{repository}#{pr_id}"

    def matches(item):
        if item.get("key") == key:
            return True
        return (item.get("project") == project and item.get("repository") == repository
                and str(item.get("pullRequestId")) == str(pr_id))

    summary = None
    for item in lines(ROOT / "pr-review-summary.jsonl"):
        if matches(item):
            summary = item
    marks = {}
    try:
        marks = json.loads((ROOT / "marks" / "pr-review-intake.json").read_text())
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        pass
    reviewed = None
    for item in (marks.get("reviewedPrs") or []) if isinstance(marks, dict) else []:
        if matches(item):
            reviewed = item
    findings = [item for item in lines(ROOT / "review-findings.jsonl") if matches(item)]
    print(json.dumps({"summary": summary, "reviewed": reviewed, "findings": findings}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
