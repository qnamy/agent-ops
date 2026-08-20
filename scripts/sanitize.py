#!/usr/bin/env python3
"""라이브 루틴 문서 → 공개용 새니타이즈 템플릿 변환.

결정적 치환(리터럴 + 정규식)만 수행한다 — LLM에 맡기지 않는 이유는
문맥 단어까지 오치환하는 사고가 실제로 있었기 때문(agent-ops 운영 기록 참고).
치환 후 유출 검사를 내장 수행하며, 의심 패턴이 남으면 exit 1로 실패한다.
"""
import re
import sys
import pathlib

HOME = str(pathlib.Path.home())

# 원본(라이브) → 템플릿 파일명
SRC = {
    f"{HOME}/Tradlinx/routines-codex/slack-pr-review-autopilot.md": "slack-pr-review-autopilot.md",
    f"{HOME}/Tradlinx/routines-codex/qa-deploy-approval-autopilot.md": "qa-deploy-approval-autopilot.md",
    f"{HOME}/Tradlinx/routines-codex/azdo-pr-comment-resolver.md": "azdo-pr-comment-resolver.md",
    f"{HOME}/Tradlinx/routines-codex/azdo-pr-completed-comment-resolver.md": "azdo-pr-completed-comment-resolver.md",
    f"{HOME}/Tradlinx/routines-codex/quality-digest-weekly.md": "quality-digest-weekly.md",
    f"{HOME}/Tradlinx/.routine-state/codex-wrappers/slack-pr-review-autopilot.sh": "example-wrapper.sh",
    f"{HOME}/.claude/scheduled-tasks/pr-deploy-routines-10min/SKILL.md": "example-dispatcher-SKILL.md",
}
OUT = pathlib.Path(f"{HOME}/workspace/agent-ops/routines/templates")

# 순서 중요: 긴 리터럴 먼저
LITERAL = [
    ("gn.bak@tradlinx.com", "{user_email}"),
    ("tradlinxjira.atlassian.net", "{jira-site}.atlassian.net"),
    ("dev.azure.com/Tradlinx", "dev.azure.com/{ado_org}"),
    (f"{HOME}/Tradlinx", "{workspace}"),
    ("~/Tradlinx", "{workspace}"),
    (HOME, "{home}"),
    ("gn.bak", "{user}"),
    ("Tradlinx", "{org}"),
    ("#dev_approval_review", "#{review-channel}"),
    ("#qa-deploy", "#{qa-deploy-channel}"),
]

REGEX = [
    (re.compile(r"<!subteam\^[A-Z0-9]+>"), "<!subteam^{SUBTEAM_ID}>"),
    (re.compile(r"\b[BW][A-Z0-9]{8,}\b"), "{bot_id}"),
    (re.compile(r"\b[UC][A-Z0-9]{8,10}\b"), "{slack_id}"),
    (re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b"), "{guid}"),
    # 잘린 GUID 조각(예: `@c8e28351-…`)도 식별자 파편이므로 치환
    (re.compile(r"@[0-9a-f]{8}-"), "@{guid}-"),
    (re.compile(r"\bOP-\d{3,5}\b"), "{TICKET}"),
    (re.compile(r"PR 18\d{3}"), "PR {id}"),
    (re.compile(r"#18\d{3}"), "#{id}"),
]

# 유출 검사: 치환 후에도 남아 있으면 안 되는 패턴 (case-sensitive가 필요한 것은 분리)
LEAK = [
    re.compile(r"tradlinx", re.IGNORECASE),
    re.compile(r"gn\.bak", re.IGNORECASE),
    re.compile(r"bakgyunam", re.IGNORECASE),
    re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"),
    re.compile(r"@[0-9a-f]{8}"),
    re.compile(r"subteam\^S[A-Z0-9]+"),
    re.compile(r"\b[UCBW][A-Z0-9]{8,10}\b"),
    re.compile(r"\bOP-\d{3,}\b"),
    re.compile(r"\b18\d{3}\b"),
    re.compile(r"xoxb-[A-Za-z0-9-]+"),
    re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
]

HEADER = "<!-- sanitized template - 실제 값은 로컬 ROUTINE-CONFIG에서 주입된다. 원본은 비공개 워크스페이스에서 운영 중. -->\n"
SH_HEADER = "# sanitized template - 실제 값은 로컬 ROUTINE-CONFIG에서 주입된다."


def sanitize(text: str) -> str:
    for old, new in LITERAL:
        text = text.replace(old, new)
    for pat, new in REGEX:
        text = pat.sub(new, text)
    return text


def main() -> int:
    leaks = []
    for src, name in SRC.items():
        text = sanitize(pathlib.Path(src).read_text(encoding="utf-8"))
        if name.endswith(".sh"):
            lines = text.split("\n")
            lines.insert(1, SH_HEADER)  # shebang 다음 줄
            text = "\n".join(lines)
        else:
            text = HEADER + text
        for pat in LEAK:
            for m in pat.finditer(text):
                leaks.append(f"{name}: {m.group(0)!r}")
        (OUT / name).write_text(text, encoding="utf-8")
        print(f"synced: {name}")
    if leaks:
        print("LEAK CHECK FAILED — 아래 패턴이 남아 있습니다. 푸시 금지, 치환 규칙을 보강하세요.", file=sys.stderr)
        for line in leaks:
            print(f"  {line}", file=sys.stderr)
        return 1
    print("leak check: clean")
    return 0


if __name__ == "__main__":
    sys.exit(main())
