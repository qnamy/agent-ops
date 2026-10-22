#!/usr/bin/env python3
# sanitized template — 실제 값은 로컬 ROUTINE-CONFIG에서 주입된다.
"""회차 세션의 도구호출을 유형별로 갈라 턴 수와 입력을 귀속시킨다.

usage: token-breakdown.py [<시작> [<끝>]]
       시작·끝은 epoch 또는 'YYYY-MM-DD HH:MM'. 생략하면 전체·현재.

`token-report.py`는 세션 단위 총량만 낸다. 어디를 줄일지 정하려면 그 총량이
어느 도구호출에 붙는지가 필요하다. 모델은 상태가 없어 매 턴 컨텍스트 전체를
다시 받으므로, **비용을 정하는 축은 호출 수**다 — 호출 하나가 턴 하나다.

입력 귀속은 턴의 입력을 그 턴의 도구호출에 붙이는 방식이다. codex는
`token_count`의 `last_token_usage`(턴별 증분)를 직전 도구호출에 붙이고,
`input_tokens`는 `cached_input_tokens`를 이미 포함한다
(`input_tokens + output_tokens == total_tokens`로 확인) — 둘을 더하면 2배가 된다.
Devin은 스텝 `metrics.prompt_tokens`를 그 스텝의 첫 `tool_calls`에 붙인다 —
한 스텝에 호출이 둘 이상인 경우는 전체의 0.2%라 나누지 않는다.

세션 선별에서 **cwd는 정확히 대조한다.** 파일 본문에 경로가 있는지로 고르면
같은 레포를 작업하는 다른 워크트리 세션이 섞인다. codex는 엔트리의 `cwd`를,
Devin은 system 스텝의 `Current workspace directories:`를 본다. 회차 식별도
다르다 — codex는 `round.py begin` 실행으로, Devin은 트리거 첫 입력으로 잡는다
(`token-report.py`의 `TRIGGER`와 같은 정규식).

합계는 **도구호출에 귀속된 입력만**이다. 도구호출 없는 턴은 어느 유형에도 붙지
않아 빠지므로, 이 출력의 `입력`은 `token-report.py`의 오케스트레이터 입력보다
작다. 절감처는 비중으로 읽고 총량은 그쪽 보고에서 읽는다.
"""
import collections
import datetime
import glob
import json
import os
import re
import sys

CODEX = os.path.expanduser("~/.codex/sessions/*/*/*/*.jsonl")
CODEX_ARCHIVED = os.path.expanduser("~/.codex/archived_sessions/*.jsonl")
DEVIN = os.path.expanduser("~/.local/share/devin/cli/transcripts/*.json")
ROOT = "~/work/orca-automations"
# 회차는 시작 명령을 **실행한** 세션이다. 도구호출 인자 전체를 보면 안 된다 —
# 파일 쓰기도 같은 도구의 인자로 오므로, 그 명령줄이 본문에 든 패치를 적용한
# 개발 세션이 회차가 된다(2026-09-10 12:22·12:27 두 세션이 그렇게 잡혔고 그날
# 실제 RUN은 0건이다). 셸 명령만 꺼내 **명령 경계**에서 대조한다. 세 도구가 같은
# 정규식과 같은 cwd 대조를 쓴다 — 한쪽만 고치면 세 보고의 세션 수가 어긋난다.
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
# Devin 회차를 여는 트리거 문장이다 — `token-report.py`와 같은 정규식이다.
TRIGGER = re.compile(r"prompts/([a-z0-9-]+)\.md 를 읽고 그 지시를 지금 그대로 수행하라")
# Devin 전사(ATIF)의 system 스텝에 뜨는 작업 디렉터리다.
DEVIN_CWD = re.compile(r"^  (\S+) \(cwd\)\s*$", re.M)


def is_round_call(payload):
    """이 도구호출이 회차 시작 명령을 **실행**했는가."""
    if payload.get("type") not in ("function_call", "custom_tool_call"):
        return False
    arguments = str(payload.get("arguments") or payload.get("input") or "")
    return any(ROUND_CALL.search(c) for c in SHELL_INPUT.findall(arguments))

# 분류는 위에서부터 처음 맞는 것으로 정한다. 순서가 곧 우선순위다.
# 시그니처는 (도구이름, 명령, 인자원문) — codex 도구호출은 이름이 비어 온다.
RULES = [
    # 빈 폴링은 `{"chars":""}`와 `chars: ""` 두 표기로 나온다. 하나만 보면
    # 2026-09-17에 466건 중 315건을 놓쳤다. Devin의 대응물은 `write_to_process`의
    # 빈 `text_input`·`bytes_input`이다.
    ("워커대기 빈폴링", lambda t, c, a: (
        ("write_stdin" in a and re.search(r'"?chars"?:\s*""', a))
        or (t == "write_to_process" and re.search(r'"(?:text_input|bytes_input)":\s*""', a))
    )),
    ("워커대기 wait셀", lambda t, c, a: "cell_id" in a),
    # Devin의 `get_output`은 백그라운드로 띄운 `ask`·`sleep`의 결과를 읽는다.
    ("워커대기 폴링", lambda t, c, a: t == "get_output"),
    ("round.py begin", lambda t, c, a: "round.py begin" in c),
    ("round.py finish", lambda t, c, a: "round.py finish" in c),
    ("guarded.sh 쓰기", lambda t, c, a: "guarded.sh" in c),
    ("lock check 단독", lambda t, c, a: "lock.sh check" in c),
    ("파일도구 쓰기", lambda t, c, a: (
        "Begin Patch" in a or "apply_patch" in a or t in ("edit", "write", "notebook_edit")
    )),
    ("pr-session ask", lambda t, c, a: "pr-session.sh ask" in c),
    ("pr-session 기타", lambda t, c, a: "pr-session.sh" in c),
    ("자기지시 적재", lambda t, c, a: "memories" in c or "SKILL.md" in c),
    # codex는 `cat prompts/…`로, Devin은 `read` 도구로 같은 파일을 다시 읽는다.
    ("프롬프트 재읽기", lambda t, c, a: "prompts/" in c and (
        t in ("read", "grep")
        or re.search(r"(?<![\w-])(?:sed|awk|cat|head|tail|grep|ls|wc|open)\b", c)
    )),
    ("잘림출력 읽기", lambda t, c, a: "devin-overflows" in c),
    # 회차가 사고 조사로 다른 세션의 전사를 직접 여는 호출과, digest 회차가
    # 원장을 읽고 쓰는 호출이다 — 둘 다 규칙 없이 `기타`로 빠졌다(09-24·09-25).
    ("전사 직접 스캔", lambda t, c, a: re.search(
        r"transcripts/|\.codex/sessions|\.claude/projects", c)),
    ("원장(handoff)", lambda t, c, a: "handoff/" in c),
    ("ROUTINE-CONFIG 읽기", lambda t, c, a: "ROUTINE-CONFIG" in c),
    ("회사 PR 절차 읽기", lambda t, c, a: "PR-ADO.md" in c),
    ("prior-review.py", lambda t, c, a: "prior-review.py" in c),
    # `.*`에 re.S를 켠다 — `python3 - <<'EOF' … open('state/…')`처럼 heredoc
    # 본문 뒤쪽 줄에 state/가 오는 호출이 빠졌다(09-25 code-convention-digest).
    ("state 읽기", lambda t, c, a: (
        re.search(r"(?<![\w-])(?:sed|cat|head|tail|grep|awk|ls|wc|python3?|test|find|rg)\b.*state/", c, re.S)
        or (t in ("read", "grep", "find_file_by_name") and "state/" in c)
    )),
    ("slack", lambda t, c, a: "slack_" in a or (t == "mcp_list_tools" and "slack" in a)),
    ("jira(atlassian)", lambda t, c, a: "atlassian" in a),
    ("ado(az) 읽기", lambda t, c, a: "bin/az" in c),
    ("lock 기타", lambda t, c, a: "lock.sh" in c),
    # 범용 규칙은 마지막에 둔다 — `git 조회`는 인자 어디든 `git` 낱말이 있으면
    # 걸리므로(grep 인자의 "diff --git" 포함), 그보다 구체적인 유형을 앞에 둔다.
    ("스킬 적재", lambda t, c, a: t == "skill"),
    ("검색", lambda t, c, a: t in ("grep", "find_file_by_name")),
    ("루틴코드 읽기", lambda t, c, a: (
        (t == "read" and "/bin/" in c)
        or re.search(r"(?<![\w-])(?:cat|sed|awk|head|tail|grep|rg|ls|wc)\b.*\bbin/", c)
    )),
    ("관측도구 실행", lambda t, c, a: re.search(r"\bbin/token-", c)),
    ("git 조회", lambda t, c, a: re.search(r"\bgit\b", c)),
    # `date`는 명령 경계에서만 본다 — `git log --date=…`의 `--date`는 앞글자가
    # `-`라 여기 걸리지 않고, 걸리더라도 위의 `git 조회`가 먼저 잡는다.
    ("date 조회", lambda t, c, a: re.search(r"(?:^|[;&|(]\s*)date\b", c)),
]


def moment(raw, default):
    if raw is None:
        return default
    if str(raw).isdigit():
        return float(raw)
    return datetime.datetime.strptime(raw, "%Y-%m-%d %H:%M").timestamp()


def classify(tool, command, arguments):
    for name, test in RULES:
        if test(tool, command, arguments):
            return name
    return "기타"


def command_of(payload):
    """도구호출 인자에서 실제 셸 명령을 꺼낸다. 못 꺼내면 인자 원문을 쓴다."""
    arguments = payload.get("arguments") or payload.get("input") or ""
    found = re.search(r'cmd:\s*"((?:[^"\\]|\\.)*)"', arguments)
    return (found.group(1) if found else arguments), arguments


def devin_call_of(tool_call):
    """Devin 도구호출을 (도구이름, 명령, 인자원문)으로 펼친다."""
    tool = tool_call.get("function_name") or ""
    args = tool_call.get("arguments")
    arguments = json.dumps(args, ensure_ascii=False) if isinstance(args, dict) else str(args)
    if not isinstance(args, dict):
        return tool, arguments, arguments
    for key in ("command", "file_path", "text_input", "bytes_input"):
        if isinstance(args.get(key), str):
            return tool, args[key], arguments
    return tool, arguments, arguments


def session_cwd(path):
    for line in open(path):
        if '"cwd"' not in line:
            continue
        try:
            cwd = json.loads(line).get("payload", {}).get("cwd")
        except Exception:
            cwd = None
        if cwd:
            return cwd
    return None


def stamp_of(entry):
    try:
        return datetime.datetime.fromisoformat(
            entry["timestamp"].replace("Z", "+00:00")
        ).timestamp()
    except Exception:
        return None


def matched(pattern, label):
    """스캔 대상을 돌려준다. 하나도 없으면 조용한 0 대신 경고를 낸다."""
    paths = glob.glob(pattern)
    if not paths:
        print(f"경고: {label} 전사 glob이 0건이다 — {pattern}", file=sys.stderr)
    return paths


def codex_paths():
    """codex는 끝난 세션을 `archived_sessions/`로 옮긴다. 옮기는 도중 양쪽에 같은
    파일명이 보이면 `sessions/` 쪽 하나만 센다."""
    paths = {}
    for path in matched(CODEX_ARCHIVED, "codex 보관") + matched(CODEX, "codex"):
        paths[os.path.basename(path)] = path
    return list(paths.values())


def devin_text(message):
    """Devin 스텝 본문. 텍스트+이미지 입력은 파트 리스트로 남는다."""
    if isinstance(message, list):
        return "\n".join(p.get("text", "") for p in message if isinstance(p, dict))
    return message or ""


def devin_opener_and_cwd(steps):
    """첫 user 스텝의 본문과, system 스텝에 뜬 작업 디렉터리."""
    opener = cwd = None
    for step in steps:
        if opener is None and step.get("source") == "user" and step.get("message"):
            opener = devin_text(step["message"]).strip()
        if cwd is None and step.get("source") == "system":
            found = DEVIN_CWD.search(devin_text(step.get("message")))
            if found:
                cwd = found.group(1)
        if opener is not None and cwd is not None:
            break
    return opener, cwd


def scan_codex(since, until, calls, tokens):
    sessions = 0
    for path in sorted(codex_paths()):
        if os.path.getmtime(path) < since:
            continue
        if session_cwd(path) != ROOT:
            continue
        # 세션이 회차인지는 끝까지 읽어야 알 수 있다. 세션별로 모으고 회차로
        # 판명될 때만 합친다 — 본문 문자열로 가르면 프롬프트를 읽거나 이 저장소를
        # 고치는 개발 세션이 회차로 잡힌다(2026-09-17 실측 intake 8건 대 9건).
        is_round = False
        mine_calls = collections.Counter()
        mine_tokens = collections.Counter()
        pending = None
        counted = False
        at = None
        for line in open(path):
            try:
                entry = json.loads(line)
            except Exception:
                continue
            if entry.get("timestamp"):
                try:
                    at = datetime.datetime.fromisoformat(
                        entry["timestamp"].replace("Z", "+00:00")
                    ).timestamp()
                except Exception:
                    pass
            payload = entry.get("payload", {})
            kind = payload.get("type")
            # 회차 식별은 구간 밖에서도 본다 — 자정을 넘긴 회차의 시작 명령이
            # 구간 앞에 있어도 그 세션은 회차다. 금액만 구간 안으로 자른다.
            if not is_round:
                is_round = is_round_call(payload)
            if at is None or not (since <= at < until):
                continue
            if kind in ("function_call", "custom_tool_call"):
                pending = classify("", *command_of(payload))
            elif kind == "token_count" and pending:
                try:
                    last = payload["info"]["last_token_usage"]
                except Exception:
                    continue
                mine_calls[pending] += 1
                mine_tokens[pending] += last["input_tokens"]
                pending = None
                counted = True
        if not is_round:
            continue
        calls.update(mine_calls)
        tokens.update(mine_tokens)
        if counted:
            sessions += 1
    return sessions


def scan_devin(since, until, calls, tokens):
    sessions = 0
    for path in sorted(matched(DEVIN, "devin")):
        if os.path.getmtime(path) < since:
            continue
        try:
            transcript = json.load(open(path))
        except Exception:
            continue
        steps = transcript.get("steps") or []
        opener, cwd = devin_opener_and_cwd(steps)
        if cwd != ROOT or not TRIGGER.search(opener or ""):
            continue
        counted = False
        for step in steps:
            metrics = step.get("metrics")
            tool_calls = step.get("tool_calls") or []
            if not metrics or not tool_calls:
                continue
            at = stamp_of(step)
            if at is None or not (since <= at < until):
                continue
            for tool_call in tool_calls:
                calls[classify(*devin_call_of(tool_call))] += 1
            # 입력은 턴 단위 하나다 — 첫 호출의 유형에만 붙여 두 번 세지 않는다.
            tokens[classify(*devin_call_of(tool_calls[0]))] += metrics.get("prompt_tokens", 0)
            counted = True
        if counted:
            sessions += 1
    return sessions


def main(argv):
    since = moment(argv[1] if len(argv) > 1 else None, 0.0)
    until = moment(argv[2] if len(argv) > 2 else None, 2.0e10)
    calls = collections.Counter()
    tokens = collections.Counter()
    sessions = scan_codex(since, until, calls, tokens)
    sessions += scan_devin(since, until, calls, tokens)
    if not sessions:
        print("구간 안에 회차 세션이 없다.")
        return 0
    total_calls = sum(calls.values())
    total_tokens = sum(tokens.values())
    start = datetime.datetime.fromtimestamp(since).strftime("%m-%d %H:%M") if since else "전체"
    end = datetime.datetime.fromtimestamp(until).strftime("%m-%d %H:%M") if until < 2.0e10 else "현재"
    print(f"\n{start} ~ {end}  회차 {sessions}세션  호출 {total_calls}  입력 {total_tokens:,}")
    print(f"  {'유형':20}{'호출':>6}{'세션당':>8}{'입력':>13}{'비중':>7}")
    for name, count in calls.most_common():
        share = 100 * tokens[name] / total_tokens if total_tokens else 0
        print(f"  {name:20}{count:>6}{count / sessions:>8.2f}{tokens[name]:>13,}{share:>6.1f}%")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
