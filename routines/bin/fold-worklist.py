#!/usr/bin/env python3
# sanitized template — 실제 값은 로컬 ROUTINE-CONFIG에서 주입된다.
"""Append-only worklist 이벤트를 파일 순서대로 활성 집합으로 접는다."""

import json
import sys
from pathlib import Path


def fold(path: Path) -> list[dict]:
    active: dict[str, dict] = {}

    try:
        lines = path.read_text().splitlines()
    except FileNotFoundError:
        return []

    for line_no, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError as error:
            raise ValueError(f"invalid JSON at line {line_no}") from error
        if not isinstance(event, dict):
            raise ValueError(f"event at line {line_no} is not an object")

        key = event.get("key")
        op = event.get("op")
        if not isinstance(key, str) or not key:
            raise ValueError(f"event at line {line_no} has no key")

        fields = {name: value for name, value in event.items() if name != "op"}
        if op == "add":
            # add는 항목 전체를 다시 기록한다. 같은 key의 재등록도 이 경로다.
            active[key] = fields
        elif op == "update":
            # update는 그때까지의 add/update 필드 위에 바뀐 필드만 덮는다.
            active[key] = {**active.get(key, {"key": key}), **fields}
        elif op == "close":
            active.pop(key, None)
        else:
            raise ValueError(f"event at line {line_no} has unknown op")

    return list(active.values())


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: fold-worklist.py <worklist-file>", file=sys.stderr)
        return 2
    print(json.dumps(fold(Path(sys.argv[1])), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
