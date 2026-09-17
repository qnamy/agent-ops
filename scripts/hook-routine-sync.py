#!/usr/bin/env python3
"""Claude Code PostToolUse 훅: 라이브 루틴이 수정되면 게시 템플릿을 로컬 동기화.

stdin으로 받는 훅 JSON에서 손댄 경로를 읽어, 감시 대상일 때만 sync-templates.sh를
실행한다. 훅은 항상 exit 0 — 동기화 실패가 원래 편집을 막으면 안 되므로 fail-open이며,
결과는 `.sync-templates.log`에 남는다.

**Bash도 본다.** 세션이 파일을 Edit/Write로만 고치지 않는다 — heredoc과 스크립트로
쓰는 편이 많고, 그때 매처가 `Edit|Write`뿐이면 훅이 한 번도 뜨지 않는다(2026-09-17에
하루치 루틴 수정이 전부 그렇게 새어 나갔다). Bash는 `file_path`가 없으므로 명령 문자열에
감시 경로가 들어 있는지로 본다. 읽기 명령에도 뜨지만 `sanitize.py`는 멱등이고
`sync-templates.sh`는 diff가 없으면 커밋하지 않는다.

감시 경로는 저장소 밖 비공개 맵에서 읽는다 — 그 경로 자체가 감추려는 값이다.
기본 `~/.config/agent-ops/sanitize-map.json`의 `live`, `AGENT_OPS_SANITIZE_MAP`으로 덮어쓴다.

`~/.claude/settings.json` 등록 조각은 `claude/codex-hooks.json`에 있다.
"""
import json
import os
import pathlib
import subprocess
import sys

HOME = pathlib.Path.home()
MAP_PATH = pathlib.Path(os.environ.get("AGENT_OPS_SANITIZE_MAP")
                        or HOME / ".config" / "agent-ops" / "sanitize-map.json")
SYNC = HOME / "workspace" / "agent-ops" / "scripts" / "sync-templates.sh"


def watched() -> list[str]:
    """라이브 저장소 루트를 `~`형과 절대경로형 둘 다로 돌려준다.

    끝에 `/`를 붙여 좁히지 않는다 — 세션은 `cd <루트> && … prompts/x.md`처럼 루트로
    한 번 들어간 뒤 상대경로로 쓴다. 접두어를 `<루트>/prompts/`로 두면 그 형태가
    통째로 안 걸린다(2026-09-17 실측).
    """
    try:
        live = json.loads(MAP_PATH.read_text(encoding="utf-8"))["live"]
    except (OSError, ValueError, KeyError):
        return []
    root = live.rstrip("/")
    return list({root, str(pathlib.Path(root).expanduser())})


def touched(payload: dict) -> str:
    tool_input = payload.get("tool_input") or {}
    return str(tool_input.get("file_path") or tool_input.get("command") or "")


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0
    prefixes = watched()
    if not prefixes:
        return 0
    text = touched(payload)
    if not any(root in text for root in prefixes):
        return 0
    subprocess.run(["bash", str(SYNC)], check=False, timeout=120)
    return 0


if __name__ == "__main__":
    sys.exit(main())
