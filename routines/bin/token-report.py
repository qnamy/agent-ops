#!/usr/bin/env python3
# sanitized template — 실제 값은 로컬 ROUTINE-CONFIG에서 주입된다.
"""루틴 세션의 토큰 사용량을 센다. codex와 Claude Code 양쪽을 본다.

usage: token-report.py [<시작> [<끝>]]
       시작·끝은 epoch 또는 'YYYY-MM-DD HH:MM'. 생략하면 전체·현재.

오케스트레이터와 워커를 `lock.sh acquire` 호출 여부로 가른다 — 워커는
ADO·Slack·state 쓰기가 금지돼 락을 쓸 일이 없다. Claude Code 세션은 워커
전용이므로 그 구분이 필요 없다.

캐시 입력은 정가의 1/10로 과금된다는 가정을 쓰지 않는다. 요금표를 확인하지
않았으므로 입력합·정가·턴만 낸다.
"""
import datetime
import glob
import json
import os
import sys

CODEX = os.path.expanduser("~/.codex/sessions/*/*/*/*.jsonl")
CLAUDE = os.path.expanduser("~/.claude/projects/-Users-<user>-work-orca-automations/*.jsonl")
WS = "orca-automations"


def moment(raw, default):
    if raw is None:
        return default
    if str(raw).isdigit():
        return float(raw)
    return datetime.datetime.strptime(raw, "%Y-%m-%d %H:%M").timestamp()


def blank():
    return {"n": 0, "turns": 0, "input": 0, "cache": 0, "fresh": 0, "output": 0}


def add(bucket, turns, input_tokens, cache, fresh, output):
    bucket["n"] += 1
    bucket["turns"] += turns
    bucket["input"] += input_tokens
    bucket["cache"] += cache
    bucket["fresh"] += fresh
    bucket["output"] += output


def scan_codex(since, until, orchestrator, worker):
    for path in glob.glob(CODEX):
        if os.path.getmtime(path) < since:
            continue
        cwd = ""
        started = None
        is_orchestrator = False
        total = None
        turns = 0
        for line in open(path):
            if not cwd and '"cwd"' in line:
                try:
                    cwd = json.loads(line).get("payload", {}).get("cwd", "")
                except Exception:
                    pass
            if started is None and '"timestamp"' in line:
                try:
                    stamp = json.loads(line)["timestamp"].replace("Z", "+00:00")
                    started = datetime.datetime.fromisoformat(stamp).timestamp()
                except Exception:
                    pass
            if "lock.sh acquire" in line:
                is_orchestrator = True
            if '"token_count"' in line:
                try:
                    total = json.loads(line)["payload"]["info"]["total_token_usage"]
                    turns += 1
                except Exception:
                    pass
        if WS not in cwd or not total or started is None:
            continue
        if not (since <= started < until):
            continue
        cached = total["cached_input_tokens"]
        add(
            orchestrator if is_orchestrator else worker,
            turns, total["input_tokens"], cached,
            total["input_tokens"] - cached, total["output_tokens"],
        )


def scan_claude(since, until, worker):
    """Claude Code는 턴마다 usage를 남긴다. 세션 누계가 없으므로 합산한다.

    `cache_creation_input_tokens`는 캐시에 올리는 쓰기라 정가로 센다.
    """
    for path in glob.glob(CLAUDE):
        changed = os.path.getmtime(path)
        if not (since <= changed < until):
            continue
        turns = fresh = cache = output = 0
        for line in open(path):
            if '"usage"' not in line:
                continue
            try:
                usage = (json.loads(line).get("message") or {}).get("usage")
            except Exception:
                continue
            if not usage:
                continue
            turns += 1
            fresh += usage.get("input_tokens", 0) + usage.get("cache_creation_input_tokens", 0)
            cache += usage.get("cache_read_input_tokens", 0)
            output += usage.get("output_tokens", 0)
        if turns:
            add(worker, turns, fresh + cache, cache, fresh, output)


def render(label, buckets):
    print(f"\n{label}")
    print(f"  {'구분':16}{'세션':>5}{'평균턴':>7}{'입력합':>14}{'정가':>11}{'세션당':>12}")
    for name, bucket in buckets:
        if not bucket["n"]:
            continue
        print(
            f"  {name:16}{bucket['n']:>5}{bucket['turns'] / bucket['n']:>7.1f}"
            f"{bucket['input']:>14,}{bucket['fresh']:>11,}{bucket['input'] // bucket['n']:>12,}"
        )


def main(argv):
    since = moment(argv[1] if len(argv) > 1 else None, 0.0)
    until = moment(argv[2] if len(argv) > 2 else None, 2.0e10)
    orchestrator, codex_worker, claude_worker = blank(), blank(), blank()
    scan_codex(since, until, orchestrator, codex_worker)
    scan_claude(since, until, claude_worker)
    start = datetime.datetime.fromtimestamp(since).strftime("%m-%d %H:%M") if since else "전체"
    end = datetime.datetime.fromtimestamp(until).strftime("%m-%d %H:%M") if until < 2.0e10 else "현재"
    render(
        f"{start} ~ {end}",
        [("오케스트레이터", orchestrator), ("워커 codex", codex_worker), ("워커 claude", claude_worker)],
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
