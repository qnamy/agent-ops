#!/usr/bin/env python3
"""라이브 루틴 → 공개용 새니타이즈 템플릿 변환.

결정적 치환(리터럴 + 정규식)만 수행한다 — LLM에 맡기지 않는 이유는 문맥 단어까지
오치환하는 사고가 실제로 있었기 때문이다. 치환 후 유출 검사를 내장 수행하며,
의심 패턴이 남으면 exit 1로 실패한다.

**치환 규칙은 이 파일에 없다.** 규칙의 좌변이 곧 감추려는 값이라, 공개 저장소에 두면
스크립트 자신이 유출원이 된다. 규칙은 저장소 밖 비공개 맵에서 읽는다 — 기본 경로
`~/.config/agent-ops/sanitize-map.json`, `AGENT_OPS_SANITIZE_MAP`으로 덮어쓴다.

맵 형식:
    {
      "live": "~/…/orca-automations",         # 라이브 원본 루트
      "excludePrompts": ["…"],                # 공개하지 않을 프롬프트 (확장자 없는 이름)
      "literal": [["원본", "치환"], …],        # 순서 중요: 긴 리터럴 먼저
      "regex":   [["패턴", "치환"], …],
      "deny":    ["정규식", …]                 # 치환 후 남으면 실패시킬 비공개 패턴
    }

`routines/README.md`와 `routines/templates/ROUTINE-CONFIG.example.md`는 생성물이 아니라
손으로 쓰는 문서다. 검사만 받는다.
"""
import json
import os
import re
import shutil
import sys
import pathlib

OUT = pathlib.Path(__file__).resolve().parent.parent / "routines"
MAP_PATH = pathlib.Path(os.environ.get("AGENT_OPS_SANITIZE_MAP")
                        or pathlib.Path.home() / ".config" / "agent-ops" / "sanitize-map.json")

SCRIPTS = ["precheck.py", "precheck.sh", "round.py", "guarded.sh", "mark.py", "prior-review.py",
           "pr-session.sh", "lock.sh", "az", "fold-worklist.py", "create-automations.sh",
           "fetch-repos.sh", "seed-azure.sh", "token-report.py"]

# 형태만 보는 검사. 회사 문자열은 비공개 맵의 deny가 맡는다.
LEAK = [
    re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"),
    re.compile(r"subteam\^S[A-Z0-9]+"),
    re.compile(r"\b[UCBW][A-Z0-9]{8,10}\b"),
    re.compile(r"\b1[89]\d{3}\b"),
    re.compile(r"\b[0-9a-f]{7}\.\.\.[0-9a-f]{7}\b"),
    re.compile(r"xoxb-[A-Za-z0-9-]{4,}"),
    re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
]
# 공개 example이 스스로 쓰는 자리표시자는 면제한다.
ALLOW = re.compile(r"U000|C000|B000|S000|me@example\.com|example\.atlassian\.net")

# 제외 프롬프트를 참조하는 코드 조각. 치환으로는 못 지우므로 블록째 들어낸다.
DROP = {
    "precheck.py": [('    "deploy-approve-resolve",\n    "pr-review-merged",\n'
                     '    "dp-report-draft",\n    "dp-report-sprint",\n',
                     '    "deploy-approve-resolve",\n    "pr-review-merged",\n'),
                    ('    if automation == "pr-review-merged":\n        return pr_review_merged_gate()\n'
                     '    return parity_gate()',
                     '    return pr_review_merged_gate()')],
    "round.py": [('    "dp-report-draft":        dict(gated=False, ado=False, bot=False, worklist=None),\n'
                  '    "dp-report-sprint":       dict(gated=False, ado=False, bot=False, worklist=None),\n', '')],
    "create-automations.sh": [("# orca automation 8개를", "# orca automation 6개를"),
                              ("# 날짜·파일만 보는 셋은 기본 60초로 충분하다.\n"
                               "mk code-convention-digest  '0 8 * * 5'         none\n"
                               "mk dp-report-draft         '0 13 * * 4'        -\n"
                               "mk dp-report-sprint        '0 16 * * 4'        -\n",
                               "# 파일만 보는 하나는 precheck를 붙이지 않는다.\n"
                               "mk code-convention-digest  '0 8 * * 5'         none\n")],
    "az": [("automation 8개가 공유한다", "automation 6개가 공유한다")],
}
DROP_REGEX = {"precheck.py": [(re.compile(r"def parity_gate\(\).*?\n\n\ndef decide", re.S), "def decide")]}
# 제외한 프롬프트의 이름이 산출물에 남으면 안 된다.
DROP_CHECK = re.compile(r"dp-report")

MD_HEADER = ("<!-- sanitized template — 실제 값은 로컬 ROUTINE-CONFIG에서 주입된다. "
             "원본은 비공개 워크스페이스에서 운영 중. -->\n")
SH_HEADER = "# sanitized template — 실제 값은 로컬 ROUTINE-CONFIG에서 주입된다."


def load_map():
    if not MAP_PATH.exists():
        print(f"치환 맵이 없다: {MAP_PATH}\n"
              f"AGENT_OPS_SANITIZE_MAP으로 경로를 주거나 그 자리에 만들어라 "
              f"(형식은 이 파일 상단 docstring).", file=sys.stderr)
        raise SystemExit(1)
    spec = json.loads(MAP_PATH.read_text(encoding="utf-8"))
    return (pathlib.Path(spec["live"]).expanduser(),
            set(spec.get("excludePrompts", [])),
            [(a, b) for a, b in spec["literal"]],
            [(re.compile(a), b) for a, b in spec.get("regex", [])],
            [re.compile(p) for p in spec.get("deny", [])])


def main() -> int:
    live, exclude, literal, regex, deny = load_map()
    if not live.is_dir():
        print(f"라이브 원본이 없다: {live}", file=sys.stderr)
        return 1

    def sanitize(text: str) -> str:
        for old, new in literal:
            text = text.replace(old, new)
        for pat, new in regex:
            text = pat.sub(new, text)
        return text

    for sub in ("bin", "prompts"):
        target = OUT / sub
        if target.exists():
            shutil.rmtree(target)
        target.mkdir(parents=True)

    written = []
    for name in SCRIPTS:
        src = live / "bin" / name
        text = sanitize(src.read_text(encoding="utf-8"))
        for old, new in DROP.get(name, []):
            if old not in text:
                print(f"DROP 규칙이 맞지 않는다 ({name}): {old[:50]!r}", file=sys.stderr)
                return 1
            text = text.replace(old, new, 1)
        for pat, new in DROP_REGEX.get(name, []):
            text = pat.sub(new, text)
        lines = text.split("\n")
        lines.insert(1, SH_HEADER)  # shebang 다음 줄
        dst = OUT / "bin" / name
        dst.write_text("\n".join(lines), encoding="utf-8")
        dst.chmod(src.stat().st_mode)
        written.append(dst)

    for src in sorted((live / "prompts").glob("*.md")):
        if src.stem in exclude:
            continue
        dst = OUT / "prompts" / src.name
        dst.write_text(MD_HEADER + sanitize(src.read_text(encoding="utf-8")), encoding="utf-8")
        written.append(dst)

    # 손으로 쓰는 문서도 같은 검사를 받는다.
    written += [OUT / "README.md", OUT / "templates" / "ROUTINE-CONFIG.example.md"]
    leaks = []
    for path in written:
        text = path.read_text(encoding="utf-8")
        for pat in LEAK + deny + [DROP_CHECK]:
            for m in pat.finditer(text):
                if ALLOW.search(m.group(0)):
                    continue
                leaks.append(f"{path.relative_to(OUT)}: {m.group(0)!r}")
        print(f"synced: {path.relative_to(OUT)}")

    if leaks:
        print("LEAK CHECK FAILED — 아래 패턴이 남아 있습니다. 푸시 금지, 치환 규칙을 보강하세요.",
              file=sys.stderr)
        for line in sorted(set(leaks)):
            print(f"  {line}", file=sys.stderr)
        return 1
    print("leak check: clean")
    return 0


if __name__ == "__main__":
    sys.exit(main())
