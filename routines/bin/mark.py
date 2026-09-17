#!/usr/bin/env python3
# sanitized template — 실제 값은 로컬 ROUTINE-CONFIG에서 주입된다.
"""mark.py <automation> <lastRunTs> [<reviewedPrs JSON 배열>]

marks 파일의 read-modify-write를 세션 밖에서 한다. 세션은 `lastRunTs` 숫자 하나가
필요한데 그것을 얻으려고 reviewedPrs 279건(51KB, 12,519토큰)을 읽고, 회차 끝에는
LLM 안에서 500건 컷을 하며 다시 썼다(2026-09-17 07:20 실측). 읽기는 precheck가
맥락의 `marks.lastRunTs`로 대신하고, 쓰기는 이 스크립트가 한다.

`lastRunTs`는 전진만 한다 — 프롬프트 상태 기록 절의 불변식이다. 다른 키는 그대로
둔다. 외부 쓰기이므로 guarded.sh run 으로 부른다.
"""
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(os.environ.get("ROUTINE_STATE_ROOT") or Path(__file__).resolve().parent.parent / "state")
KEEP = 500  # 프롬프트 상태 기록 절의 기존 상한


def main(argv):
    if len(argv) not in (2, 3):
        print("usage: mark.py <automation> <lastRunTs> [<reviewedPrs JSON array>]", file=sys.stderr)
        return 2
    automation, last = argv[0], int(argv[1])
    path = ROOT / "marks" / f"{automation}.json"
    data = json.loads(path.read_text()) if path.exists() else {}
    if not isinstance(data, dict):
        data = {}
    previous = data.get("lastRunTs")
    data["lastRunTs"] = max(last, previous) if isinstance(previous, int) else last
    if len(argv) == 3:
        added = json.loads(argv[2])
        if not isinstance(added, list):
            print("mark: reviewedPrs must be a JSON array", file=sys.stderr)
            return 2
        data["reviewedPrs"] = ((data.get("reviewedPrs") or []) + added)[-KEEP:]
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{automation}.", suffix=".tmp")
    with os.fdopen(fd, "w") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)
        file.write("\n")
    os.replace(tmp, path)
    print(json.dumps({"lastRunTs": data["lastRunTs"], "reviewedPrs": len(data.get("reviewedPrs") or [])}))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
