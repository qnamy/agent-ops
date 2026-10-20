#!/usr/bin/env python3
# sanitized template — 실제 값은 로컬 ROUTINE-CONFIG에서 주입된다.
"""reap-run-terminals.py — 종료된 automation run의 터미널을 회수한다.

run이 끝나도 그 devin 세션 터미널은 프롬프트 대기 상태로 살아 남는다 — Orca가
회수하지 않고 dispatch_failed조차 터미널을 남긴다(2026-09-18 관측: 완료된 run의
pty가 한 시간 뒤에도 live, 회차당 하나씩 무한 누적, 40분에 19→26개).

회수 대상의 식별자는 run 기록의 terminalPtyId다 — run 기록에 없는 터미널(수동
세션 등)은 이 집합에 없어 안 건드린다. 본 ptyId는
state/run-terminals.jsonl에 append해 둔다 — `automations runs` 목록 창(최근 수십
건)을 벗어난 오래된 누수도 원장이 기억해 회수한다. 원장은 append-only다 —
automation별 락이 따로라 두 회차가 동시에 이 스크립트를 돌릴 수 있고, 단일 JSON
read-modify-replace면 서로의 기록을 덮어쓴다(R-10과 같은 사고).

종료 상태는 관측된 것만 인정한다 — 2026-09-18 실측으로 pty를 남기고 끝나는 것은
`completed`·`dispatch_failed` 둘이고 `dispatched`는 진행 중이다. 관측되지 않은
상태를 종료로 세면 진행 중인 run의 터미널을 닫을 수 있다 — 모르는 상태는 그대로
두는 쪽이 낫다.

두 번째 축은 고아(orphaned) 터미널이다 — 탭이 파괴돼 어느 화면에서도 닿을 수 없는
채 pty만 살아 남은 세션이다(2026-10-13 관측: 앱 재시작·워크트리 제거로 누적된
고아 pty 125개, 그중 devin 에이전트 4개가 13~24일째 생존). run 기록이 없는 수동
세션·워커의 잔여는 원장 경로가 못 잡으므로 이 축에서 회수한다. 단, 원장이 종료를
증명하지 못한 pty(dispatched 등)는 보호한다 — 재시작으로 탭을 잃은 진행 중 회차를
죽이지 않기 위해서다.
"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

BIN = Path(__file__).resolve().parent
ROOT = Path(os.environ.get("ROUTINE_STATE_ROOT") or BIN.parent / "state")
LEDGER = ROOT / "run-terminals.jsonl"
ENDED = {"completed", "dispatch_failed"}


def sh(*args, timeout=60):
    return subprocess.run([str(a) for a in args], capture_output=True, text=True,
                          timeout=timeout, check=False)


def orca_json(*args):
    p = sh("orca", *args, "--json")
    if p.returncode != 0:
        return None
    try:
        return json.loads(p.stdout)
    except json.JSONDecodeError:
        return None


def collect_sightings():
    """automation별 최근 run에서 ptyId → status를 모은다."""
    autos = orca_json("automations", "list")
    items = ((autos or {}).get("result") or {}).get("automations") or []
    out = {}
    for a in items:
        aid = a.get("id")
        if not aid:
            continue
        runs = orca_json("automations", "runs", "--id", aid)
        for r in ((runs or {}).get("result") or {}).get("runs") or []:
            pty, status = r.get("terminalPtyId"), r.get("status")
            if pty and status:
                out[pty] = {"status": status, "runId": r.get("id"), "automationId": aid}
    return out


def fold_ledger():
    folded = {}
    if LEDGER.exists():
        for line in LEDGER.read_text().splitlines():
            try:
                e = json.loads(line)
            except json.JSONDecodeError:
                continue
            if e.get("ptyId") and e.get("status"):
                folded[e["ptyId"]] = e["status"]
    return folded


def append_ledger(sightings, folded):
    appends = []
    for pty, s in sightings.items():
        if folded.get(pty) != s["status"]:
            appends.append({"ts": int(time.time()), "ptyId": pty, "status": s["status"],
                            "runId": s["runId"], "automationId": s["automationId"]})
            folded[pty] = s["status"]
    if appends:
        with LEDGER.open("a") as f:
            for e in appends:
                f.write(json.dumps(e, ensure_ascii=False) + "\n")
    return len(appends)


def close(handle):
    return sh("orca", "terminal", "close", "--terminal", handle, "--tab").returncode == 0


def main():
    sightings = collect_sightings()
    folded = fold_ledger()
    recorded = append_ledger(sightings, folded)
    ended_ptys = {p for p, s in folded.items() if s in ENDED}

    # `terminal list`는 살아 있는 것만 낸다 — 목록에 없는 pty는 이미 죽은 것이다.
    tl = orca_json("terminal", "list")
    terms = ((tl or {}).get("result") or {}).get("terminals") or []
    pty_to_handle = {t["ptyId"]: t["handle"]
                     for t in terms if t.get("handle") and t.get("ptyId")}

    protected = {p for p, s in folded.items() if s not in ENDED}
    orphan_handles = [t["handle"] for t in terms
                      if t.get("orphaned") and t.get("ptyId") not in protected
                      and t.get("ptyId") not in ended_ptys]

    closed, failed = [], []
    for h in sorted({pty_to_handle[p] for p in ended_ptys & set(pty_to_handle)}
                    | set(orphan_handles)):
        (closed if close(h) else failed).append(h)

    print(json.dumps({"recorded": recorded, "ended": len(ended_ptys),
                      "orphaned": len(orphan_handles),
                      "closed": len(closed), "failed": failed}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
