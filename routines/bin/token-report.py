#!/usr/bin/env python3
# sanitized template — 실제 값은 로컬 ROUTINE-CONFIG에서 주입된다.
"""루틴 세션의 토큰 사용량을 센다. codex와 Claude Code 양쪽을 본다.

usage: token-report.py [<시작> [<끝>]]
       시작·끝은 epoch 또는 'YYYY-MM-DD HH:MM'. 생략하면 전체·현재.

회차·워커·사람 셋으로 가른다. 회차는 `round.py begin`(또는 옛 `lock.sh acquire`)을
**실행한** 세션이다 — 워커는 ADO·Slack·state 쓰기가 금지돼 락을 쓸 일이 없다.

**구간은 양쪽 다 턴 단위로 가른다.** 세션 시작 시각이나 파일 mtime으로 가르면
세션 재사용이 그대로 오차가 된다 — 2026-09-17 08:43에 15시간짜리 세션 하나가
통째로 하루치로 잡혔다. codex는 `last_token_usage`(턴별 증분)를, Claude Code는
턴마다 남는 `usage`를 구간 안에서만 합산한다. `세션` 열은 구간 안에 턴이 하나
이상 있는 세션 수이고, 구간을 걸친 세션은 구간 안 턴만 실린다.

**어느 쪽도 루틴 전용이 아니다.** 같은 디렉터리에 사람이 띄운 관측·작업 세션이
양쪽 다 섞인다. 워커는 `pr-session.sh ask`가 보낸 지시를 받으므로 그 본문에 치환된
결과 경로(`review-result.…`)가 있다. 대장(`state/pr-sessions/`)은 `close`·`sweep`에서
지워져 사후 식별에 못 쓴다. codex 쪽에는 워커 갈래가 없다 — `ensure`가 워커를
`claude`로만 띄운다.

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
# cwd는 정확히 대조한다. 부분 일치로 고르면 같은 레포의 다른 워크트리 세션이
# 섞인다 — `git worktree list`에 `~/orca/workspaces/orca-automations/window-start`가
# 있고 그 경로에도 이 문자열이 들어 있다. 세 도구가 같은 기준을 쓴다.
ROOT = "~/work/orca-automations"
# `ask`가 보내는 지시의 공통 표식이다. 본문 형태는 둘이고 서로 겹치는 문구가
# 없다 — intake는 `<레포> 저장소 PR <번호>를 정적 검토하라`로 시작하고 resolve의
# 해소 검증은 `# PR review comment resolution verification`으로 시작한다. 둘 다
# `{{RESULT_PATH}}`를 하나씩 갖고 `ask`가 보내는 시점에 실제 결과 경로로 치환하므로
# 그 경로가 양쪽에 반드시 실린다. 문구로 가르면 resolve 워커가 사람으로 잡힌다.
WORKER_OPENER = re.compile(r"review-result\.")
# 회차는 시작 명령을 **실행한** 세션이다. 도구호출 인자 전체를 보면 안 된다 —
# 파일 쓰기도 같은 도구의 인자로 오므로, 그 명령줄이 본문에 든 패치를 적용한
# 개발 세션이 회차가 된다(2026-09-10 12:22·12:27 두 세션이 그렇게 잡혔고 그날
# 실제 RUN은 0건이다). 셸 명령만 꺼내 **명령 경계**에서 대조한다. `round.py begin`이
# `lock.sh acquire`를 서브프로세스로 감추므로(c11be27) 둘 다 본다.
# 실행된 셸 입력은 두 자리로 온다 — 단발 실행의 `cmd`와 영속 셸에 보내는
# `write_stdin`의 `chars`다(영속 셸은 커밋 `15d75f4`가 들였다). `chars`를 빼면
# 영속 셸을 쓰는 회차가 통째로 빠진다(09-17 08:50 deploy 회차 실측). 키는
# `{"cmd":"…"}`(JSON)과 `cmd: "…"`(다중행) 두 표기로 오고, 앞의 것은 키가
# 따옴표에 싸여 있어 리터럴 `cmd:`로는 안 잡힌다.
SHELL_INPUT = re.compile(r'"?(?:cmd|chars)"?\s*:\s*"((?:[^"\\]|\\.)*)"')
# 명령 경계에서만 대조한다 — 따옴표 안에 든 `grep "bin/round.py begin" prompts/`
# 같은 것이 걸리지 않게. 영속 셸 입력은 `if <명령>; then …` 형태로도 오므로
# 그 앞자리도 경계로 본다.
ROUND_CALL = re.compile(
    r"(?:^|[;&|(]\s*|\b(?:if|then|else|do)\s+)"
    r"(?:(?:python3?|bash|sh)\s+)?bin/(?:round\.py begin|lock\.sh acquire)\s+([a-z-]+)",
    re.M,
)


def is_round_call(payload):
    """이 도구호출이 회차 시작 명령을 **실행**했는가."""
    if payload.get("type") not in ("function_call", "custom_tool_call"):
        return False
    arguments = str(payload.get("arguments") or payload.get("input") or "")
    return any(ROUND_CALL.search(c) for c in SHELL_INPUT.findall(arguments))


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


def stamp_of(entry):
    try:
        return datetime.datetime.fromisoformat(
            entry["timestamp"].replace("Z", "+00:00")
        ).timestamp()
    except Exception:
        return None


def scan_codex(since, until, orchestrator, human):
    """codex 세션을 회차와 사람으로 가른다.

    워커 갈래를 두지 않는다 — `bin/pr-session.sh`의 `ensure`가 워커를 `claude`
    명령으로만 띄우므로 루틴이 만드는 codex 워커가 없다. 갈래를 남기면 PR 번호가
    섞인 사람 세션만 거기 들어가 사람 비용이 워커로 계상된다.
    """
    for path in glob.glob(CODEX):
        if os.path.getmtime(path) < since:
            continue
        cwd = None
        is_round = False
        turns = cache = fresh = output = 0
        at = None
        for line in open(path):
            try:
                entry = json.loads(line)
            except Exception:
                continue
            payload = entry.get("payload", {})
            if cwd is None and payload.get("cwd"):
                cwd = payload["cwd"]
            kind = payload.get("type")
            # 역할 식별은 구간 밖에서도 본다. 금액만 구간 안으로 자른다.
            if not is_round:
                is_round = is_round_call(payload)
            at = stamp_of(entry) or at
            # 누계(`total_token_usage`)가 아니라 턴별 증분을 쓴다. 둘의 관계는
            # 실측으로 확인했다 — 증분의 합이 누계와 같다.
            if kind != "token_count" or at is None or not (since <= at < until):
                continue
            try:
                last = payload["info"]["last_token_usage"]
            except Exception:
                continue
            turns += 1
            cache += last["cached_input_tokens"]
            # `input_tokens`는 `cached_input_tokens`를 이미 포함한다
            # (`input_tokens + output_tokens == total_tokens`로 확인).
            fresh += last["input_tokens"] - last["cached_input_tokens"]
            output += last["output_tokens"]
        if cwd != ROOT or not turns:
            continue
        add(orchestrator if is_round else human, turns, fresh + cache, cache, fresh, output)


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
            at = stamp_of(entry)
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
    orchestrator, codex_human = blank(), blank()
    claude_worker, claude_human = blank(), blank()
    scan_codex(since, until, orchestrator, codex_human)
    scan_claude(since, until, claude_worker, claude_human)
    start = datetime.datetime.fromtimestamp(since).strftime("%m-%d %H:%M") if since else "전체"
    end = datetime.datetime.fromtimestamp(until).strftime("%m-%d %H:%M") if until < 2.0e10 else "현재"
    render(
        f"{start} ~ {end}",
        [
            ("오케스트레이터", orchestrator),
            ("워커 claude", claude_worker),
            ("사람 codex", codex_human),
            ("사람 claude", claude_human),
        ],
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
