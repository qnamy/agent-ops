#!/usr/bin/env python3
# sanitized template — 실제 값은 로컬 ROUTINE-CONFIG에서 주입된다.
"""round.py begin <automation> | finish <automation> <token> [--commit] [--sweep]

회차의 결정적 앞뒤를 한 턴으로 접는다. 세션이 도구를 부를 때마다 그때까지의
컨텍스트가 다시 실리므로, 할 일 없는 회차조차 앞 8턴(dry-run 판정·락·lock
check·스냅샷·맥락 읽기·lock check·인증·폴드)과 뒤 5턴(check·commit·check·
sweep·release)을 쓰고 있었다 — 2026-09-16 resolve 18호출 중 13, 09-17 intake
11호출 중 7 실측. 여기서는 그 전부가 서브프로세스라 토큰이 0이다.

begin은 실패하면 락을 스스로 풀고 `error`를 낸다. 프롬프트의 "대상 특정 전
실패는 release만 하고 종료"가 그대로다. 성공하면 토큰이 곧 시작 epoch이다.
"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

BIN = Path(__file__).resolve().parent
ROOT = Path(os.environ.get("ROUTINE_STATE_ROOT") or BIN.parent / "state")

# 정본은 precheck.py의 GATED_AUTOMATIONS와 각 프롬프트의 시작 절이다.
TABLE = {
    "pr-review-intake":       dict(gated=True,  ado=True,  bot=False, worklist=None),
    "pr-review-resolve":      dict(gated=True,  ado=True,  bot=False, worklist="pr-review-worklist.jsonl"),
    "deploy-approve-intake":  dict(gated=True,  ado=True,  bot=True,  worklist="deploy-approve-worklist.jsonl"),
    "deploy-approve-resolve": dict(gated=False, ado=True,  bot=True,  worklist="deploy-approve-worklist.jsonl"),
    "pr-review-merged":       dict(gated=False, ado=True,  bot=False, worklist="pr-review-worklist.jsonl"),
    "code-convention-digest": dict(gated=False, ado=False, bot=False, worklist=None),
}


def sh(*args, timeout=90):
    return subprocess.run([str(a) for a in args], capture_output=True, text=True, timeout=timeout, check=False)


def lock(verb, automation, token=None):
    args = ["sh", BIN / "lock.sh", verb, automation] + ([token] if token else [])
    return sh(*args)


def emit(payload, code=0):
    print(json.dumps(payload, ensure_ascii=False))
    return code


class Fail(Exception):
    """begin이 정한 실패 사유. 락 획득 뒤에 나면 release로 이어진다."""


def begin(automation):
    acquired = lock("acquire", automation)
    if acquired.returncode != 0:
        return emit({"error": "lock-busy"}, 1)
    token = acquired.stdout.strip()
    live = (ROOT / "live" / f"{automation}.enabled").exists()
    # 획득 뒤의 실패는 사유를 정한 것이든 예외든 전부 여기서 락을 푼다. 반환
    # 코드 실패만 풀면 copyfile의 OSError·az의 TimeoutExpired가 락을 남겨 다음
    # 회차가 stale 회수(30분)까지 lock-busy로 빠진다(리뷰 R-36 재현).
    try:
        return emit(collect(automation, token, live))
    except Fail as reason:
        lock("release", automation, token)
        return emit({"error": str(reason), "live": live}, 1)
    except Exception as error:
        lock("release", automation, token)
        return emit({"error": f"begin-failed:{type(error).__name__}", "live": live}, 1)


def collect(automation, token, live):
    spec = TABLE[automation]
    out = {"live": live, "token": token, "runStartedEpoch": int(token)}

    if spec["gated"]:
        pending = ROOT / "gate" / f"pending.{automation}.json"
        if not pending.exists():
            raise Fail("no-pending")
        shutil.copyfile(pending, ROOT / "gate" / f"snapshot.{automation}.json")
        out["snapshot"] = "copied"
    else:
        out["snapshot"] = "not-gated"

    if spec["bot"]:
        bot = ROOT / ".deploy-approval-bot-token"
        if not (bot.exists() and bot.stat().st_size > 0):
            raise Fail("bot-token-missing")
        out["botToken"] = "ok"

    if spec["ado"]:
        # 값을 출력하지 않는다 — 성공 여부만 본다.
        if sh(BIN / "az", automation, "account", "show").returncode != 0:
            raise Fail("auth-failed")
        out["auth"] = "ok"

    context = ROOT / "gate" / f"context.{automation}.json"
    try:
        out["context"] = json.loads(context.read_text()) if context.exists() else None
    except (json.JSONDecodeError, OSError):
        out["context"] = None

    if spec["worklist"]:
        folded = sh(sys.executable, BIN / "fold-worklist.py", ROOT / spec["worklist"])
        if folded.returncode != 0:
            raise Fail("fold-failed")
        try:
            out["worklist"] = json.loads(folded.stdout)
        except json.JSONDecodeError:
            raise Fail("fold-failed")
    return out


def finish(automation, token, commit, sweep):
    """state·세션을 바꾸는 단계마다 소유권을 다시 본다. 종전 프롬프트가 check→commit,
    check→sweep을 각각 요구한 것과 같은 모양이고, 한 번 잃으면 뒤의 어떤 변경도
    실행하지 않는다(R-37). 잃은 뒤 release는 부르지 않는다 — 새 소유자의 락이다."""
    out = {}

    def held():
        return lock("check", automation, token).returncode == 0

    if not held():
        return emit({"error": "lock-lost", **out}, 1)
    if commit:
        out["commit"] = "done" if sh(sys.executable, BIN / "precheck.py", "commit", automation).returncode == 0 else "failed"
        if not held():
            return emit({"error": "lock-lost", **out}, 1)
    if sweep is not None:
        # 살릴 세션은 **지금** worklist를 다시 폴드해 정한다. 세션이 회차 초반의
        # 활성 집합을 넘기면 이 회차에 close한 PR의 세션이 "살릴 것"이 되어 누수된다
        # — 2026-09-16 17:01 resolve가 방금 abandoned로 닫은 #19110의 세션을 인자로
        # 넘겨 15시간 살려 뒀다. 인자로 온 key는 쓰지 않는다.
        keep = []
        worklist = TABLE[automation]["worklist"]
        if worklist:
            folded = sh(sys.executable, BIN / "fold-worklist.py", ROOT / worklist)
            if folded.returncode != 0:
                out["sweep"] = "skipped:fold-failed"
            else:
                for item in json.loads(folded.stdout):
                    key = item.get("key") or "%s/%s#%s" % (item.get("project"), item.get("repository"),
                                                          item.get("pullRequestId") or item.get("prId"))
                    keep.append(key)
        if "sweep" not in out:
            out["sweep"] = "done" if sh("sh", BIN / "pr-session.sh", "sweep", *keep, timeout=300).returncode == 0 else "failed"
            out["kept"] = len(keep)
        if not held():
            return emit({"error": "lock-lost", **out}, 1)
    out["release"] = "done" if lock("release", automation, token).returncode == 0 else "failed"
    return emit(out)


def main(argv):
    if len(argv) >= 2 and argv[0] == "begin" and argv[1] in TABLE and len(argv) == 2:
        return begin(argv[1])
    if len(argv) >= 3 and argv[0] == "finish" and argv[1] in TABLE:
        rest = argv[3:]
        commit = "--commit" in rest
        sweep = True if "--sweep" in rest else None
        return finish(argv[1], argv[2], commit, sweep)
    print("usage: round.py begin <automation> | finish <automation> <token> [--commit] [--sweep]", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
