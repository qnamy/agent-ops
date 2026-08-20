#!/usr/bin/env python3
"""PreToolUse Bash guard: 자동승인 불가한 복합 명령을 차단한다.

셸 인용부호를 고려해 판정한다 (단순 문자열 검색의 오탐 방지):
- 작은따옴표 안: 아무것도 차단하지 않음 (셸이 실행하지 않음)
- 큰따옴표 안: ';', '&&', '||'는 리터럴이므로 허용, '$('와 백틱은 실제 실행되므로 차단
- 인용부호 밖: ';', '&&', '||', '$(', 백틱 차단 (백슬래시 이스케이프된 문자는 리터럴로 취급)
- 명령 끝의 단독 ';'는 무해하므로 판정 전에 제거 (기존 perl strip과 동일)

stdin으로 훅 JSON을 받고, 차단 시 permissionDecision=deny JSON을 출력한다.
파싱 실패 시에는 조용히 통과시킨다 (fail-open, 기존 동작과 동일).
"""
import json
import sys

DENY = {
    "hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": (
            "복합 명령(&&, ;, ||, 명령치환, 백틱)은 자동승인 안 됨. "
            "단일 명령 여러 개로 나누세요. 나눌 수 없으면 .sh 파일로 Write 후 "
            "bash 파일.sh 로 실행."
        ),
    }
}


def has_compound(cmd):
    cmd = cmd.rstrip("; \t\n")
    state = None  # None(밖) | "'" | '"'
    i = 0
    n = len(cmd)
    while i < n:
        c = cmd[i]
        if state == "'":
            if c == "'":
                state = None
            i += 1
        elif state == '"':
            if c == "\\":
                i += 2
            elif c == '"':
                state = None
                i += 1
            elif c == "`":
                return True
            elif c == "$" and i + 1 < n and cmd[i + 1] == "(":
                return True
            else:
                i += 1
        else:
            if c == "\\":
                i += 2
            elif c == "'":
                state = "'"
                i += 1
            elif c == '"':
                state = '"'
                i += 1
            elif c in (";", "`"):
                return True
            elif c == "&" and i + 1 < n and cmd[i + 1] == "&":
                return True
            elif c == "|" and i + 1 < n and cmd[i + 1] == "|":
                return True
            elif c == "$" and i + 1 < n and cmd[i + 1] == "(":
                return True
            else:
                i += 1
    return False


def main():
    try:
        data = json.load(sys.stdin)
        cmd = data.get("tool_input", {}).get("command", "")
    except Exception:
        return
    if isinstance(cmd, str) and has_compound(cmd):
        print(json.dumps(DENY, ensure_ascii=False))


if __name__ == "__main__":
    main()
