#!/usr/bin/env python3
# sanitized template — 실제 값은 로컬 ROUTINE-CONFIG에서 주입된다.
"""구간 안 회차의 사고 신호와 한도 상태를 한 번에 낸다.

usage: token-incidents.py [<시작> [<끝>]]
       시작·끝은 epoch 또는 'YYYY-MM-DD HH:MM'. 생략하면 전체·현재.

세 가지를 본다.

- **회차 목록** — 시각·automation·턴·입력. 턴이 비정상으로 적으면 죽은 회차다.
- **실패 신호** — 회차 출력에 뜬 문자열을 센다. `pr-session.sh`의 종료 사유
  (`timeout`·`no-session`·`send-failed`·`boot-timeout`)와 셸 실패다. 신호마다
  그 신호가 처음 뜬 회차(시각·automation·전사 파일)를 같이 낸다.
- **워커 거절과 한도** — Devin 워커가 세션 한도로 즉시 거절한 건수, codex 주간
  한도와 크레딧 잔액·구간 소모.

2026-09-17에 이 셋이 동시에 터졌다. 회차 하나가 `bin/round.py`를 bash로 불러
죽었고(`command not found`), Devin 워커가 2시간 동안 전부 거절했고, 그 거절을
`ask`가 20분씩 기다려 회차 입력의 절반을 썼다. 하나만 봐서는 원인이 안 보인다.
"""
import collections
import datetime
import glob
import json
import os
import re
import sys

CODEX = os.path.expanduser("~/.codex/sessions/*/*/*/*.jsonl")
CLAUDE = os.path.expanduser("~/.claude/projects/-Users-<user>-work-orca-automations/*.jsonl")
DEVIN = os.path.expanduser("~/.local/share/devin/cli/transcripts/*.json")
ROOT = "~/work/orca-automations"
# 회차를 여는 트리거 문장이다. 파일명이 automation 이름이다. Claude·Devin 회차는
# 이 첫 입력으로 잡는다 — codex의 `round.py begin` 실행 대조와 같은 역할이다.
TRIGGER = re.compile(r"prompts/([a-z0-9-]+)\.md 를 읽고 그 지시를 지금 그대로 수행하라")
# 회차는 시작 명령을 **실행한** 세션이다. 도구호출 인자 전체를 보면 안 된다 —
# 파일 쓰기도 같은 도구의 인자로 오므로, 그 명령줄이 본문에 든 패치를 적용한
# 개발 세션이 회차가 된다(2026-09-10 12:22·12:27 두 세션이 그렇게 잡혔고 그날
# 실제 RUN은 0건이다). 셸 명령만 꺼내 **명령 경계**에서 대조한다 — 따옴표 안에
# 든 `grep "bin/round.py begin" prompts/` 같은 것은 걸리지 않는다.
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
# Devin 전사(ATIF)의 system 스텝에 뜨는 작업 디렉터리다.
DEVIN_CWD = re.compile(r"^  (\S+) \(cwd\)\s*$", re.M)

# `pr-session.sh`가 내는 종료 사유와, 셸이 내는 실패다. 앞의 넷은 그 스크립트가
# `echo`로 한 줄에 내는 값이라 **줄 전체가 그 낱말일 때만** 센다 — 부분 일치로
# 세면 스크립트 본문을 `cat`한 출력이나 `PR_SESSION_TIMEOUT_MS` 같은 이름이
# 그대로 사고로 잡힌다. 스크립트의 `echo`를 고치면 여기도 같이 고쳐야 한다.
FAILURES = [
    ("ask timeout", re.compile(r"^timeout$", re.M)),
    ("ask no-session", re.compile(r"^no-session$", re.M)),
    ("ask send-failed", re.compile(r"^send-failed$", re.M)),
    ("ask boot-timeout", re.compile(r"^boot-timeout$", re.M)),
    ("command not found", re.compile(r"command not found$", re.M)),
    ("lock 상실(exit 3)", re.compile(r"^guarded: lock lost", re.M)),
]
LIMIT_REFUSAL = re.compile(r"hit your (session|usage) limit")
# `ask`가 보내는 지시의 공통 표식이다. 본문 형태는 둘이고 서로 겹치는 문구가
# 없다 — intake는 `<레포> 저장소 PR <번호>를 정적 검토하라`로 시작하고 resolve의
# 해소 검증은 `# PR review comment resolution verification`으로 시작한다. 둘 다
# `{{RESULT_PATH}}`를 하나씩 갖고 `ask`가 보내는 시점에 실제 결과 경로로 치환하므로
# 그 경로가 양쪽에 반드시 실린다. 헤더 형태도 같이 본다.
WORKER_OPENER = re.compile(
    r"review-result\.|저장소 PR \d|# PR (리뷰|코드 리뷰|코드 판정)|# 배포 승인|# (?:스레드 )?해소 검증"
)


def moment(raw, default):
    if raw is None:
        return default
    if str(raw).isdigit():
        return float(raw)
    return datetime.datetime.strptime(raw, "%Y-%m-%d %H:%M").timestamp()


def stamp_of(entry):
    raw = entry.get("timestamp")
    if not raw:
        return None
    try:
        return datetime.datetime.fromisoformat(raw.replace("Z", "+00:00")).timestamp()
    except Exception:
        return None


def matched(pattern, label):
    """스캔 대상을 돌려준다. 하나도 없으면 조용한 0 대신 경고를 낸다."""
    paths = glob.glob(pattern)
    if not paths:
        print(f"경고: {label} 전사 glob이 0건이다 — {pattern}", file=sys.stderr)
    return paths


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


def output_text(output):
    """도구 결과에서 실제 출력 문자열을 꺼낸다.

    결과는 `[{"type": "input_text", "text": ...}, …]`이거나 문자열이다. 리스트를
    `str()`로 찍으면 줄바꿈이 `\\n` 표기로 남아 줄 단위 대조가 전부 빗나간다.
    """
    if isinstance(output, list):
        return "\n".join(
            part.get("text", "") for part in output if isinstance(part, dict)
        )
    return output if isinstance(output, str) else str(output)


def claude_output_text(entry):
    """Claude의 도구 결과는 user 엔트리의 tool_result 블록으로 온다."""
    content = (entry.get("message") or {}).get("content")
    if not isinstance(content, list):
        return ""
    parts = []
    for block in content:
        if not isinstance(block, dict) or block.get("type") != "tool_result":
            continue
        parts.append(output_text(block.get("content")))
    return "\n".join(parts)


# 전사·원장을 직접 여는 호출의 결과는 실패 신호·한도 거절 검색에서 뺀다 — 그
# 출력은 다른 세션·문서에 있던 과거 문자열의 인용이라 이 회차의 실패가 아니다.
# 2026-09-24 구간의 `command not found` 1건이 전부 token-digest 회차가 전사를
# 스캔한 출력의 인용이었다. 결과와 호출은 `source_call_id`↔`tool_call_id`로 잇는다.
QUOTE_SOURCE = re.compile(r"transcripts/|\.codex/sessions|\.claude/projects|handoff/|docs/")


def devin_output_text(step):
    """Devin의 도구 결과는 스텝의 `observation.results[].content`로 온다."""
    results = (step.get("observation") or {}).get("results") or []
    quoting = {
        tc.get("tool_call_id")
        for tc in (step.get("tool_calls") or [])
        if isinstance(tc, dict)
        and QUOTE_SOURCE.search(json.dumps(tc.get("arguments") or "", ensure_ascii=False))
    }
    return "\n".join(
        str(r.get("content", ""))
        for r in results
        if isinstance(r, dict) and r.get("source_call_id") not in quoting
    )


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


def round_automation(payload):
    """도구호출이 **실행한** 회차 시작 명령의 automation을 꺼낸다. 없으면 None."""
    if payload.get("type") not in ("function_call", "custom_tool_call"):
        return None
    arguments = str(payload.get("arguments") or payload.get("input") or "")
    for command in SHELL_INPUT.findall(arguments):
        found = ROUND_CALL.search(command)
        if found:
            return found.group(1)
    return None


def rounds_codex(since, until):
    out = []
    failures = collections.Counter()
    detail = []
    for path in sorted(matched(CODEX, "codex")):
        if os.path.getmtime(path) < since:
            continue
        if session_cwd(path) != ROOT:
            continue
        automation = None
        started = None
        turns = 0
        tokens = 0
        at = None
        # 실패 신호는 회차의 것만 센다. 세션이 회차인지는 끝까지 읽어야 알 수
        # 있으므로 일단 세션별로 모으고 회차로 판명될 때만 합친다.
        seen = collections.Counter()
        seen_at = {}
        for line in open(path):
            try:
                entry = json.loads(line)
            except Exception:
                continue
            payload = entry.get("payload", {})
            # 회차 식별은 구간 밖에서도 본다 — 자정을 넘긴 회차의 시작 명령이
            # 구간 앞에 있어도 그 세션은 회차다. 금액만 구간 안으로 자른다.
            automation = automation or round_automation(payload)
            at = stamp_of(entry) or at
            if at is None or not (since <= at < until):
                continue
            if payload.get("type") == "token_count":
                try:
                    last = payload["info"]["last_token_usage"]
                except Exception:
                    continue
                if started is None:
                    started = at
                turns += 1
                tokens += last["input_tokens"]
            elif payload.get("type") in ("function_call_output", "custom_tool_call_output"):
                text = output_text(payload.get("output"))
                for name, pattern in FAILURES:
                    if pattern.search(text):
                        seen[name] += 1
                        seen_at.setdefault(name, at)
        if not automation:
            continue
        failures.update(seen)
        for name, count in seen.items():
            detail.append((name, seen_at[name], automation + "(codex)", count, os.path.basename(path)))
        if turns:
            out.append((started, automation + "(codex)", turns, tokens))
    return out, failures, detail


def rounds_claude(since, until):
    """Claude 회차는 트리거 첫 입력으로 잡고, 실패는 tool_result 본문에서 센다."""
    out = []
    failures = collections.Counter()
    detail = []
    for path in sorted(matched(CLAUDE, "claude")):
        if os.path.getmtime(path) < since:
            continue
        automation = None
        opener = None
        started = None
        turns = 0
        tokens = 0
        seen = collections.Counter()
        seen_at = {}
        for line in open(path):
            try:
                entry = json.loads(line)
            except Exception:
                continue
            if opener is None:
                # 첫 user 텍스트만 트리거로 본다 — 이후 입력에 그 문장이 와도
                # 사람 세션이다(회차 식별 계약은 첫 사용자 입력).
                opener = first_user_text(entry)
                if opener is not None:
                    found = TRIGGER.search(opener)
                    if found:
                        automation = found.group(1)
            at = stamp_of(entry)
            if at is None or not (since <= at < until):
                continue
            if entry.get("type") == "assistant":
                usage = (entry.get("message") or {}).get("usage")
                if not usage:
                    continue
                if started is None:
                    started = at
                turns += 1
                tokens += (
                    usage.get("input_tokens", 0)
                    + usage.get("cache_creation_input_tokens", 0)
                    + usage.get("cache_read_input_tokens", 0)
                )
            elif entry.get("type") == "user":
                text = claude_output_text(entry)
                for name, pattern in FAILURES:
                    if pattern.search(text):
                        seen[name] += 1
                        seen_at.setdefault(name, at)
        if not automation:
            continue
        failures.update(seen)
        for name, count in seen.items():
            detail.append((name, seen_at[name], automation + "(claude)", count, os.path.basename(path)))
        if turns:
            out.append((started, automation + "(claude)", turns, tokens))
    return out, failures, detail


def rounds_devin(since, until):
    """Devin 회차는 트리거 첫 입력으로 잡고, 실패는 observation 본문에서 센다."""
    out = []
    failures = collections.Counter()
    detail = []
    for path in sorted(matched(DEVIN, "devin")):
        if os.path.getmtime(path) < since:
            continue
        try:
            transcript = json.load(open(path))
        except Exception:
            continue
        steps = transcript.get("steps") or []
        opener, cwd = devin_opener_and_cwd(steps)
        if cwd != ROOT:
            continue
        found = TRIGGER.search(opener or "")
        if not found:
            continue
        started = None
        turns = 0
        tokens = 0
        seen = collections.Counter()
        seen_at = {}
        for step in steps:
            at = stamp_of(step)
            if at is None or not (since <= at < until):
                continue
            metrics = step.get("metrics")
            if metrics:
                if started is None:
                    started = at
                turns += 1
                tokens += metrics.get("prompt_tokens", 0)
            text = devin_output_text(step)
            for name, pattern in FAILURES:
                if pattern.search(text):
                    seen[name] += 1
                    seen_at.setdefault(name, at)
        failures.update(seen)
        for name, count in seen.items():
            detail.append((name, seen_at[name], found.group(1) + "(devin)", count, os.path.basename(path)))
        if turns:
            out.append((started, found.group(1) + "(devin)", turns, tokens))
    return out, failures, detail


def first_user_text(entry):
    if entry.get("type") != "user":
        return None
    content = (entry.get("message") or {}).get("content")
    if isinstance(content, list):
        content = "".join(c.get("text", "") for c in content if isinstance(c, dict))
    if not isinstance(content, str):
        return None
    content = content.strip()
    return content if content and not content.startswith("<") else None


def refusals(since, until):
    """한도 거절을 워커와 사람 세션으로 갈라 센다.

    같은 프로젝트 디렉터리에 사람이 띄운 세션이 섞인다. 워커는 `pr-session.sh`가
    보낸 리뷰 지시로 시작하므로 첫 사용자 입력 형태로 가른다 — `token-report.py`의
    `WORKER_OPENER`와 같은 기준이다. 거절 문구는 스텝 본문·도구 결과 어디에도
    남을 수 있어 스텝 전체 문자열에서 찾는다.
    """
    counts = {"워커": 0, "사람": 0}
    sessions = {"워커": set(), "사람": set()}
    for path in matched(DEVIN, "devin"):
        if os.path.getmtime(path) < since:
            continue
        try:
            transcript = json.load(open(path))
        except Exception:
            continue
        steps = transcript.get("steps") or []
        opener, cwd = devin_opener_and_cwd(steps)
        if cwd != ROOT:
            continue
        hits = 0
        for step in steps:
            at = stamp_of(step)
            if at is None or not (since <= at < until):
                continue
            text = devin_text(step.get("message")) + devin_output_text(step)
            if LIMIT_REFUSAL.search(text):
                hits += 1
        if not hits:
            continue
        role = "워커" if opener and WORKER_OPENER.search(opener) else "사람"
        counts[role] += hits
        sessions[role].add(os.path.basename(path)[:-5])
    return counts, sessions


def limits(since, until):
    """가장 최근 `rate_limits` 기록과 구간 양 끝의 크레딧 잔액."""
    seen = []
    for path in matched(CODEX, "codex"):
        if os.path.getmtime(path) < since:
            continue
        for line in open(path):
            if '"rate_limits"' not in line:
                continue
            try:
                entry = json.loads(line)
            except Exception:
                continue
            at = stamp_of(entry)
            if at is None or not (since <= at < until):
                continue
            balance = re.search(r'"balance":"([0-9.]+)"', line)
            used = re.search(r'"used_percent":([0-9.]+)', line)
            resets = re.search(r'"resets_at":(\d+)', line)
            if balance and used and resets:
                seen.append((at, float(balance.group(1)), float(used.group(1)), int(resets.group(1))))
    seen.sort()
    return seen


def main(argv):
    since = moment(argv[1] if len(argv) > 1 else None, 0.0)
    until = moment(argv[2] if len(argv) > 2 else None, 2.0e10)

    listed, failures, detail = rounds_codex(since, until)
    for provider_rounds in (rounds_claude, rounds_devin):
        more, more_failures, more_detail = provider_rounds(since, until)
        listed += more
        failures.update(more_failures)
        detail += more_detail
    listed.sort()
    print(f"\n회차 {len(listed)}건")
    for started, automation, turns, tokens in listed:
        clock = datetime.datetime.fromtimestamp(started).strftime("%H:%M")
        print(f"  {clock}  {automation:30}턴 {turns:>4}  입력 {tokens:>12,}")

    print(f"\n실패 신호")
    if failures:
        by_name = collections.defaultdict(list)
        for name, at, label, count, transcript in detail:
            by_name[name].append((at, label, count, transcript))
        for name, count in failures.most_common():
            occ = sorted(by_name[name])
            where = ", ".join(
                f"{datetime.datetime.fromtimestamp(at).strftime('%H:%M')} {label} {os.path.splitext(tid)[0]}"
                + (f"×{n}" if n > 1 else "")
                for at, label, n, tid in occ
            )
            print(f"  {name:24}{count:>5}  — {where}")
    else:
        print("  없음")

    counts, who = refusals(since, until)
    print("\n한도 거절")
    for role in ("워커", "사람"):
        tail = f"  세션 {', '.join(sorted(who[role]))}" if who[role] else ""
        print(f"  {role}{counts[role]:>5}건{tail}")

    seen = limits(since, until)
    print("\n한도·크레딧")
    if seen:
        first, last = seen[0], seen[-1]
        reset_at = datetime.datetime.fromtimestamp(last[3]).strftime("%Y-%m-%d %H:%M")
        print(f"  주간 한도 {last[2]:.1f}% 사용, 리셋 {reset_at}")
        print(f"  크레딧 {first[1]:.2f} → {last[1]:.2f} (구간 소모 {first[1] - last[1]:.2f})")
    else:
        print("  구간 안 기록 없음")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
