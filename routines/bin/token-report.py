#!/usr/bin/env python3
# sanitized template — 실제 값은 로컬 ROUTINE-CONFIG에서 주입된다.
"""루틴 세션의 토큰 사용량을 센다. codex와 Claude Code 양쪽을 본다.

usage: token-report.py [<시작> [<끝>]]
       시작·끝은 epoch 또는 'YYYY-MM-DD HH:MM'. 생략하면 전체·현재.

오케스트레이터와 워커를 `lock.sh acquire` 호출 여부로 가른다 — 워커는
ADO·Slack·state 쓰기가 금지돼 락을 쓸 일이 없다.

**구간은 양쪽 다 턴 단위로 가른다.** 세션 시작 시각이나 파일 mtime으로 가르면
세션 재사용이 그대로 오차가 된다 — 2026-09-17 08:43에 15시간짜리 세션 하나가
통째로 하루치로 잡혔다. codex는 `last_token_usage`(턴별 증분)를, Claude Code는
턴마다 남는 `usage`를 구간 안에서만 합산한다. `세션` 열은 구간 안에 턴이 하나
이상 있는 세션 수이고, 구간을 걸친 세션은 구간 안 턴만 실린다.

**Claude Code 세션은 워커 전용이 아니다.** 같은 프로젝트 디렉터리에 사람이 띄운
관측·작업 세션이 섞인다. 워커는 `pr-session.sh`가 보낸 리뷰 지시로 시작하므로
첫 사용자 입력이 `<프로젝트> 프로젝트의 <레포> 저장소 PR <번호>` 형태다. 대장
(`state/pr-sessions/`)은 `close`·`sweep`에서 지워져 사후 식별에 못 쓴다.

캐시 입력은 정가의 1/10로 과금된다는 가정을 쓰지 않는다. 요금표를 확인하지
않았으므로 입력합·정가·턴만 낸다.
"""
import datetime
import glob
import json
import os
import re
import sys

CODEX = os.path.expanduser("~/.codex/sessions/*/*/*/*.jsonl")
CLAUDE = os.path.expanduser("~/.claude/projects/-Users-<user>-work-orca-automations/*.jsonl")
WS = "orca-automations"
# `pr-session.sh ask`가 보내는 리뷰 지시의 첫 줄. 프롬프트의 `state/ask.*.md`
# 서두가 바뀌면 여기도 같이 고쳐야 한다.
WORKER_OPENER = re.compile(r"저장소 PR \d+")


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


def stamp_of(line):
    try:
        return datetime.datetime.fromisoformat(
            json.loads(line)["timestamp"].replace("Z", "+00:00")
        ).timestamp()
    except Exception:
        return None


def scan_codex(since, until, orchestrator, worker):
    for path in glob.glob(CODEX):
        if os.path.getmtime(path) < since:
            continue
        cwd = ""
        is_orchestrator = False
        turns = cache = fresh = output = 0
        at = None
        for line in open(path):
            if not cwd and '"cwd"' in line:
                try:
                    cwd = json.loads(line).get("payload", {}).get("cwd", "")
                except Exception:
                    pass
            if '"timestamp"' in line:
                at = stamp_of(line) or at
            if ORCHESTRATOR_MARK.search(line):
                is_orchestrator = True
            # 누계(`total_token_usage`)가 아니라 턴별 증분을 쓴다. 둘의 관계는
            # 실측으로 확인했다 — 증분의 합이 누계와 같다.
            if '"token_count"' in line and at is not None and since <= at < until:
                try:
                    last = json.loads(line)["payload"]["info"]["last_token_usage"]
                except Exception:
                    continue
                turns += 1
                cache += last["cached_input_tokens"]
                # `input_tokens`는 `cached_input_tokens`를 이미 포함한다
                # (`input_tokens + output_tokens == total_tokens`로 확인).
                fresh += last["input_tokens"] - last["cached_input_tokens"]
                output += last["output_tokens"]
        if WS not in cwd or not turns:
            continue
        add(orchestrator if is_orchestrator else worker, turns, fresh + cache, cache, fresh, output)


def first_user_text(entry):
    if entry.get("type") != "user":
        return None
    content = (entry.get("message") or {}).get("content")
    if isinstance(content, list):
        content = "".join(c.get("text", "") for c in content if isinstance(c, dict))
    if not isinstance(content, str):
        return None
    content = content.strip()
    # 도구 결과·시스템 주입은 사용자 입력이 아니다.
    return content if content and not content.startswith("<") else None


def scan_claude(since, until, worker, human):
    """Claude Code는 턴마다 usage를 남긴다. 세션 누계가 없으므로 합산한다.

    `cache_creation_input_tokens`는 캐시에 올리는 쓰기라 정가로 센다.
    """
    for path in glob.glob(CLAUDE):
        if os.path.getmtime(path) < since:
            continue
        opener = None
        turns = fresh = cache = output = 0
        for line in open(path):
            try:
                entry = json.loads(line)
            except Exception:
                continue
            if opener is None:
                opener = first_user_text(entry)
            if entry.get("type") != "assistant":
                continue
            at = stamp_of(line)
            if at is None or not (since <= at < until):
                continue
            usage = (entry.get("message") or {}).get("usage")
            if not usage:
                continue
            turns += 1
            fresh += usage.get("input_tokens", 0) + usage.get("cache_creation_input_tokens", 0)
            cache += usage.get("cache_read_input_tokens", 0)
            output += usage.get("output_tokens", 0)
        if not turns:
            continue
        bucket = worker if opener and WORKER_OPENER.search(opener) else human
        add(bucket, turns, fresh + cache, cache, fresh, output)


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
    orchestrator, codex_worker = blank(), blank()
    claude_worker, human = blank(), blank()
    scan_codex(since, until, orchestrator, codex_worker)
    scan_claude(since, until, claude_worker, human)
    start = datetime.datetime.fromtimestamp(since).strftime("%m-%d %H:%M") if since else "전체"
    end = datetime.datetime.fromtimestamp(until).strftime("%m-%d %H:%M") if until < 2.0e10 else "현재"
    render(
        f"{start} ~ {end}",
        [
            ("오케스트레이터", orchestrator),
            ("워커 codex", codex_worker),
            ("워커 claude", claude_worker),
            ("사람 claude", human),
        ],
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
