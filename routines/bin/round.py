#!/usr/bin/env python3
# sanitized template — 실제 값은 로컬 ROUTINE-CONFIG에서 주입된다.
"""round.py begin <automation> | finish <automation> <token> [--commit]

회차의 결정적 앞뒤를 한 턴으로 접는다. 세션이 도구를 부를 때마다 그때까지의
컨텍스트가 다시 실리므로, 할 일 없는 회차조차 앞 8턴(dry-run 판정·락·lock
check·스냅샷·맥락 읽기·lock check·인증·폴드)과 뒤 4턴(check·commit·check·
release)을 쓰고 있었다 — 2026-09-16 resolve 18호출 중 13, 09-17 intake
11호출 중 7 실측. 여기서는 그 전부가 서브프로세스라 토큰이 0이다.

begin은 실패하면 락을 스스로 풀고 `error`를 낸다. 프롬프트의 "대상 특정 전
실패는 release만 하고 종료"가 그대로다. 성공하면 토큰이 곧 시작 epoch이다.
"""
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

BIN = Path(__file__).resolve().parent
ROOT = Path(os.environ.get("ROUTINE_STATE_ROOT") or BIN.parent / "state")

# 정본은 precheck.py의 GATED_AUTOMATIONS와 각 프롬프트의 시작 절이다.
TABLE = {
    "pr-review-intake":       dict(gated=True,  ado=True,  bot=False, worklist=None),
    "pr-review-resolve":      dict(gated=True,  ado=True,  bot=False, worklist="pr-review-worklist.jsonl",
                                   concurrent="pr-review-intake"),
    "deploy-approve-intake":  dict(gated=True,  ado=True,  bot=True,  worklist="deploy-approve-worklist.jsonl"),
    "deploy-approve-resolve": dict(gated=False, ado=True,  bot=True,  worklist="deploy-approve-worklist.jsonl"),
    "pr-review-merged":       dict(gated=False, ado=True,  bot=False, worklist="pr-review-worklist.jsonl"),
    "code-convention-digest": dict(gated=False, ado=False, bot=False, worklist=None),
}


def sh(*args, timeout=90):
    return subprocess.run([str(a) for a in args], capture_output=True, text=True, timeout=timeout, check=False)


def lock_owner(automation):
    """다른 automation의 회차가 **지금 돌고 있는지**. 살아 있으면 획득 epoch, 아니면 None.

    `lock.sh`의 두 동사는 서로 다른 질문에 답한다 — `check`는 "내가 아직 주인인가"라
    token만 보고, `acquire`는 "기존 주인이 살아 있나"라 STALE=1800으로 좀비를 회수한다.
    여기서 묻는 것은 후자이므로 `acquire`와 같은 기준을 쓴다. 1라운드 리뷰 C-01을
    "두 코드가 같은 락을 다르게 판정한다"로 받아들여 나이 판정을 지웠던 것은 이
    구분을 놓친 것이고, 그렇게 두면 죽은 owner가 회수될 때까지 resolve가 그 PR을
    매번 `inFlight`로 미뤄 무기한 멈춘다(2라운드 C-01). 게이트가 정상화된 뒤 intake는
    새 Slack 활동이 없으면 SKIP이라 `acquire` 자체가 오래 안 일어날 수 있어, 그
    경로가 오히려 흔해졌다.

    살아 있는 회차가 30분을 넘길 수 있어 `lock.sh check`가 heartbeat를 남긴다.
    여기서도 owner와 heartbeat 중 최신 시각으로 살아 있는 회차를 판정한다.

    STALE의 정본은 `lock.sh`다 — 그쪽을 바꾸면 여기도 같이 바꾼다.
    """
    lock = ROOT / "locks" / f"{automation}.lock"
    try:
        owner = int((lock / "owner").read_text().strip())
    except (OSError, ValueError):
        return None
    try:
        owner = max(owner, int((lock / "heartbeat").stat().st_mtime))
    except OSError:
        pass
    return owner if time.time() - owner <= 1800 else None


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
        # 깨진 줄은 건너뛰지만 건수는 남긴다 — fold가 stderr 경고만 내고 계속하는
        # 동작이라, 여기서 삼키면 닫히지 않은 항목이 영원히 활성으로 남아도 회차
        # 보고에 아무 신호가 없다.
        skipped = folded.stderr.count("warning:")
        if skipped:
            out["worklistSkipped"] = skipped
        mark_concurrent(spec.get("concurrent"), out["worklist"])
    return out


def mark_concurrent(other, worklist):
    """지금 도는 다른 automation 회차가 등록한 항목에 `inFlight`를 단다.

    intake는 09-16 고아 PR 사고 뒤 **리뷰 전에** worklist에 등록하고, resolve는
    「내 text 스레드 0건 = 미리뷰」를 리뷰 실패 복구 신호로 쓴다. 리뷰가 도는
    몇 분은 두 판정이 함께 성립하는 창이고, 락은 automation별이라 둘을
    직렬화하지 않는다. 2026-09-17 11:01 intake와 11:10 resolve가 그 창에서
    Lingo/tx-lingo-api#19116에 같은 지적을 두 벌 달았다(스레드 91421·91425,
    91422·91426). 작성자가 네 스레드에 모두 답글을 썼다.

    등록 ts가 그 회차의 시작 epoch 이상이고 **`by`가 그 automation일 때만** 붙인다.
    ts만 보면 resolve가 「미리뷰 복구」로 쓴 add도 조건을 만족한다 — 폴드는 같은 key의
    가장 늦은 add를 남기므로, 도는 intake와 겹친 resolve의 자기 등록이 intake의 것으로
    오인돼 다음 resolve 회차가 그 PR을 통째로 건너뛴다(리뷰 C-02). 2026-09-17
    13:11:13의 #{PR}·#{PR} 등록이 resolve 토큰인데 13:01 intake가 도는 중이었다."""
    if not other:
        return
    started = lock_owner(other)
    if started is None:
        return
    for item in worklist:
        ts = item.get("ts")
        if isinstance(ts, int) and ts >= started and item.get("by") == other:
            item["inFlight"] = other


def finish(automation, token, commit):
    """state를 바꾸는 단계마다 소유권을 다시 본다. 종전 프롬프트가 check→commit을
    요구한 것과 같은 모양이고, 한 번 잃으면 뒤의 어떤 변경도 실행하지 않는다(R-37).
    잃은 뒤 release는 부르지 않는다 — 새 소유자의 락이다."""
    out = {}

    def held():
        return lock("check", automation, token).returncode == 0

    if not held():
        return emit({"error": "lock-lost", **out}, 1)
    if commit:
        # commit이 종료 시점 게이트 신호를 재계산하므로 ADO·Slack 조회가 든다.
        # 상한은 precheck 전체 예산과 같은 180초. timeout이 예외로 새면 release가
        # 안 돌고 락이 남으므로 returncode≠0인 다른 서브프로세스 실패와 같은
        # commit=failed로 수렴시킨다 — 미커밋 재발화가 다음 tick에 재시도한다.
        try:
            rc = sh(sys.executable, BIN / "precheck.py", "commit", automation, timeout=180).returncode
        except subprocess.TimeoutExpired:
            rc = -1
        out["commit"] = "done" if rc == 0 else "failed"
        if not held():
            return emit({"error": "lock-lost", **out}, 1)
    out["release"] = "done" if lock("release", automation, token).returncode == 0 else "failed"
    # 종료된 run의 터미널을 회수한다 — run이 끝나도 그 세션 터미널은 프롬프트
    # 대기로 남고 Orca는 회수하지 않는다(2026-09-18 관측: 회차당 하나씩 무한
    # 누적, 40분에 19→26개). 이 회차 자신의 run은 아직 dispatched라 대상이
    # 아니고, release 뒤라 락과도 무관하다. 실패해도 회차 결과를 바꾸지 않는다 —
    # 남은 누수는 다음 회차가 치운다.
    try:
        reap = sh(sys.executable, BIN / "reap-run-terminals.py", timeout=300)
        out["reap"] = json.loads(reap.stdout.strip().splitlines()[-1])
    except (json.JSONDecodeError, IndexError, subprocess.TimeoutExpired):
        out["reap"] = "failed"
    return emit(out)


def main(argv):
    if len(argv) >= 2 and argv[0] == "begin" and argv[1] in TABLE and len(argv) == 2:
        return begin(argv[1])
    if len(argv) >= 3 and argv[0] == "finish" and argv[1] in TABLE:
        return finish(argv[1], argv[2], "--commit" in argv[3:])
    print("usage: round.py begin <automation> | finish <automation> <token> [--commit]", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
