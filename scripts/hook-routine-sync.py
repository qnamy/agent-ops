#!/usr/bin/env python3
"""Claude Code PostToolUse 훅: 라이브 루틴 문서가 수정되면 게시 템플릿을 로컬 동기화.

stdin으로 받는 훅 JSON에서 편집된 파일 경로를 읽어, 감시 대상 경로일 때만
sync-templates.sh를 실행한다. 훅은 항상 exit 0 — 동기화 실패가 원래 편집
작업을 막으면 안 되므로 fail-open이며, 결과는 .sync-templates.log에 남는다.

~/.claude/settings.json 등록 조각:
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [{ "type": "command",
                    "command": "python3 ~/workspace/agent-ops/scripts/hook-routine-sync.py" }]
      }
    ]
  }
}
"""
import json
import pathlib
import subprocess
import sys

HOME = str(pathlib.Path.home())

WATCH_PREFIXES = (
    f"{HOME}/Tradlinx/routines-codex/",
    f"{HOME}/Tradlinx/.routine-state/codex-wrappers/",
    f"{HOME}/.claude/scheduled-tasks/",
)

SYNC = f"{HOME}/workspace/agent-ops/scripts/sync-templates.sh"


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0
    path = (payload.get("tool_input") or {}).get("file_path", "")
    if not path.startswith(WATCH_PREFIXES):
        return 0
    subprocess.run(["bash", SYNC], check=False, timeout=120)
    return 0


if __name__ == "__main__":
    sys.exit(main())
