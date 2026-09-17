#!/usr/bin/env python3
# sanitized template — 실제 값은 로컬 ROUTINE-CONFIG에서 주입된다.
"""orca automation별 조기 게이트와 필요한 사내 레포 fetch를 수행한다."""

import hashlib
import json
import os
import re
import pathlib
import subprocess
import sys
import time

SKIP_EXIT = 10
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
STATE_ROOT = Path(os.environ.get("ROUTINE_STATE_ROOT") or REPO_ROOT / "state")
GATE_DIR = STATE_ROOT / "gate"
DIFF_DIR = STATE_ROOT / "diff"
CONFIG_PATH = Path.home() / "work" / "ROUTINE-CONFIG.md"
FOLD_WORKLIST = SCRIPT_DIR / "fold-worklist.py"
FETCH_REPOS = SCRIPT_DIR / "fetch-repos.sh"
AZ = SCRIPT_DIR / "az"

GATED_AUTOMATIONS = {
    "pr-review-intake",
    "deploy-approve-intake",
    "pr-review-resolve",
}
AUTOMATIONS = GATED_AUTOMATIONS | {
    "deploy-approve-resolve",
    "pr-review-merged",
}
# org·project·repo·PR id를 모두 잡는다. pull ref fetch에 정본 URL이 필요하다.
PR_URL = re.compile(
    r"https://dev\.azure\.com/([^/]+)/([^/\s)]+)/_git/([^/\s)]+)/(?:pullrequest|pullrequests)/(\d+)"
)


def fetch_target(org: str, project: str, repository: str, pull_request_id) -> str:
    """fetch-repos.sh가 받는 `<repo>#<id>#<정본URL>` 형식.

    **공백을 `%20`으로 인코딩한다.** 프로젝트와 레포 이름에 공백이 있고(`Back
    Office`, `<공백 있는 프로젝트>`) 스크립트가 인자를 단어 분리로 읽으므로, 그대로
    넘기면 한 대상이 여러 조각으로 깨져 전부 `missing`이 된다. 스크립트가 레포
    이름만 되돌리고 URL은 인코딩된 채로 git에 넘긴다."""
    # 입력 인코딩이 둘로 갈린다 — Slack URL에서 뽑은 값은 이미 percent-encoded고
    # (`FCL%20Schedule`), worklist 항목의 값은 원문이다(`<공백 있는 프로젝트>`). 그대로
    # quote하면 앞의 것이 `FCL%2520Schedule`이 되어 fetch가 조용히 실패한다.
    # unquote로 원문에 맞춘 뒤 한 번만 인코딩한다.
    raw_project = urllib.parse.unquote(project)
    raw_repository = urllib.parse.unquote(repository)
    quoted = urllib.parse.quote(f"{org}/{raw_project}/_git/{raw_repository}")
    return f"{raw_repository.replace(' ', '%20')}#{pull_request_id}#https://dev.azure.com/{quoted}"


def log(message: str) -> None:
    print(message, file=sys.stderr)


def load_json(path: Path, default):
    try:
        with path.open() as file:
            return json.load(file)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return default


def load_json_strict(path: Path):
    with path.open() as file:
        return json.load(file)


def save_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.tmp")
    with temporary.open("w") as file:
        json.dump(value, file, ensure_ascii=False, indent=1)
    os.replace(temporary, path)


def read_config() -> str:
    return CONFIG_PATH.read_text()


def config_channel(config: str, channel_name: str) -> str:
    match = re.search(
        rf"^\s*-\s*채널\s+`{re.escape(channel_name)}`\s*=\s*`([^`]+)`",
        config,
        re.MULTILINE,
    )
    if not match:
        raise ValueError("Slack channel coordinate is missing")
    return match.group(1)


# 봇 토큰은 이 워크스페이스 안에 있다. ROUTINE-CONFIG.md의 경로는 현행 루틴용
# 이고, 그것을 읽으면 런타임에 점 디렉터리를 만지게 된다(설계 DEC-004·DEC-011).
BOT_TOKEN_PATH = STATE_ROOT / ".deploy-approval-bot-token"


def config_ado_org(config: str) -> str:
    match = re.search(r"^\s*-\s*조직:\s*`?([^`\n]+?)`?\s*$", config, re.MULTILINE)
    if not match:
        raise ValueError("Azure DevOps organization is missing")
    return f"https://dev.azure.com/{match.group(1).strip()}/"


def ado_org_name(config: str) -> str:
    return config_ado_org(config).rstrip("/").rsplit("/", 1)[-1]


def config_user(config: str) -> str:
    match = re.search(r"^\s*-\s*사용자:\s*`([^`]+)`", config, re.MULTILINE)
    if not match:
        raise ValueError("user identity is missing")
    return match.group(1).strip()


def config_slack_user(config: str) -> str:
    match = re.search(r"^\s*-\s*사용자:[^\n]*Slack user\s*`([^`]+)`", config, re.MULTILINE)
    if not match:
        raise ValueError("user Slack id is missing")
    return match.group(1).strip()


def config_bot_user(config: str) -> str:
    match = re.search(r"^\s*-\s*봇[^\n]*Slack user\s*`([^`]+)`", config, re.MULTILINE)
    if not match:
        raise ValueError("bot Slack id is missing")
    return match.group(1).strip()


def config_mentions(config: str) -> list[str]:
    line = re.search(r"^\s*-\s*대상 유저그룹 멘션[^\n]*$", config, re.MULTILINE)
    mentions = re.findall(r"<!subteam\^[^>]+>", line.group(0)) if line else []
    if not mentions:
        raise ValueError("target user group mentions are missing")
    return mentions


def config_pr_url_pattern(config: str) -> str:
    match = re.search(r"^\s*-\s*PR URL 패턴:\s*`([^`]+)`", config, re.MULTILINE)
    if not match:
        raise ValueError("PR URL pattern is missing")
    return match.group(1).strip()


def config_disclaimer(config: str) -> str:
    match = re.search(
        r"^\s*-\s*PR 댓글 면책 문구[^\n]*\n\s*```\n(.*?)\n\s*```",
        config,
        re.MULTILINE | re.DOTALL,
    )
    if not match:
        raise ValueError("PR comment disclaimer is missing")
    return "\n".join(line.strip() for line in match.group(1).splitlines())


def config_context() -> dict:
    """세션이 ROUTINE-CONFIG.md를 런타임에 읽지 않도록 해석값을 넘긴다.

    precheck는 게이트 판정에서 이미 이 파일을 파싱한다. 세션이 같은 파일을 다시
    읽으면 그 1,637토큰이 회차가 끝날 때까지 매 턴 다시 실린다(2026-09-16 실측).

    Jira·Confluence 좌표는 넣지 않는다. 그것을 쓰는 automation은 남은 값 때문에
    어차피 파일을 읽어야 해서, 여기 실어도 읽기가 줄지 않는다.
    """
    config = read_config()
    return {
        "adoOrg": config_ado_org(config),
        "prUrlPattern": config_pr_url_pattern(config),
        "user": config_user(config),
        "slackUser": config_slack_user(config),
        "botUser": config_bot_user(config),
        "channels": {
            name: config_channel(config, name)
            for name in ("#pr-review-requests", "#deploy-approval")
        },
        "mentions": config_mentions(config),
        "disclaimer": config_disclaimer(config),
    }


def bot_token() -> str:
    token = BOT_TOKEN_PATH.read_text().strip()
    if not token:
        raise ValueError("bot token is empty")
    return token


def slack_api(token: str, method: str, params: dict) -> dict:
    query = urllib.parse.urlencode(params)
    request = urllib.request.Request(
        f"https://slack.com/api/{method}?{query}",
        headers={"Authorization": f"Bearer {token}"},
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        payload = json.load(response)
    if not payload.get("ok"):
        raise RuntimeError("Slack API returned an error")
    return payload


def slack_channel_signal(token: str, channel: str, oldest: str | None = None) -> tuple[str, set[str]]:
    """게이트 신호와 fetch 대상을 각각 다른 조회로 얻는다.

    신호는 **창과 무관하게 채널 전체의 최신 ts**다. 창을 씌우면 96시간 동안
    조용한 채널에서 응답이 비어 신호가 `no-messages`가 되고, committed의 옛
    ts와 달라 매 회차 RUN한다(토큰 절감이 무너진다).

    fetch 대상은 세션이 처리할 창을 cursor가 소진될 때까지 읽는다. 한 페이지만
    읽거나 페이지 수를 고정하면 뒤 페이지 PR의 레포가 fetch되지 않는다.
    """
    head = slack_api(token, "conversations.history", {"channel": channel, "limit": 1})
    head_messages = head.get("messages", [])
    if not head_messages:
        return "no-messages", set()
    latest = head_messages[0].get("ts")
    if latest is None:
        raise RuntimeError("Slack latest message has no ts")

    repositories: set[str] = set()
    cursor = None
    pages = 0
    while True:
        params = {"channel": channel, "limit": 200}
        if oldest:
            params["oldest"] = oldest
        if cursor:
            params["cursor"] = cursor
        payload = slack_api(token, "conversations.history", params)
        for message in payload.get("messages", []):
            if isinstance(message, dict):
                for org, project, repository, pull_request_id in PR_URL.findall(message.get("text", "")):
                    repositories.add(fetch_target(org, project, repository, pull_request_id))
        cursor = (payload.get("response_metadata") or {}).get("next_cursor")
        pages += 1
        if not cursor:
            break
        if pages >= 200:
            # 조용히 자르지 않는다 — 자르면 뒤 페이지 레포가 영구히 fetch되지 않는다.
            raise RuntimeError("Slack history pagination did not terminate")
    return str(latest), repositories


def slack_thread_signal(token: str, channel: str, message_ts: str, oldest: str) -> str:
    payload = slack_api(
        token,
        "conversations.replies",
        {"channel": channel, "ts": message_ts, "oldest": oldest, "limit": 200},
    )
    replies = [
        str(message["ts"])
        for message in payload.get("messages", [])
        if isinstance(message, dict) and message.get("ts") and str(message["ts"]) != str(message_ts)
    ]
    return max(replies, key=float) if replies else "no-new"


def folded_worklist(name: str) -> list[dict]:
    output = subprocess.run(
        [sys.executable, str(FOLD_WORKLIST), str(STATE_ROOT / name)],
        capture_output=True,
        text=True,
        check=True,
    )
    items = json.loads(output.stdout)
    if not isinstance(items, list):
        raise ValueError("folded worklist is not an array")
    return items


def az_json(automation: str, args: list[str], timeout: int = 90):
    result = subprocess.run(
        [str(AZ), automation, *args, "-o", "json"],
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError("Azure DevOps query failed")
    return json.loads(result.stdout)


PR_CONTEXT: dict = {}


def azdo_digest(worklist: list[dict], org: str, me: str) -> str:
    """세션이 실제로 처리하는 신호만 담는다.

    이전에는 PR의 모든 스레드를 넣어서, 남이 만든 스레드 하나가 바뀌어도 회차가
    떴다. 세션이 처리하는 것은 **내가 댓글을 단 스레드**다 — 내가 루트인 것은
    경로 A·B의 대상이고, 남의 루트에 단 내 `issue:`/`discuss:` 답글은 재투표와
    close 판정의 입력이다. 그래서 내 댓글이 하나라도 있는 스레드만 담는다.
    루트만으로 좁히면 남의 스레드에 단 내 답글이 해소돼도 게이트가 RUN을 내지
    않아 재투표가 열리지 않는다. `commentType: system` 스레드는 제외한다 — 내
    투표가 시스템 스레드를 만들어 digest를 흔들면 매 회차 RUN이 된다.

    경로 B의 source 푸시는 아래 `srcCommit`이 잡는다.
    """
    structure = {"worklist": [], "prs": {}}
    for item in sorted(worklist, key=lambda value: value.get("pullRequestId", 0)):
        project = item["project"]
        repository = item["repository"]
        pull_request_id = item["pullRequestId"]
        structure["worklist"].append([project, repository, pull_request_id, item.get("status")])
        pull_request = az_json(
            "pr-review-resolve",
            ["repos", "pr", "show", "--id", str(pull_request_id), "--org", org],
        )
        if pull_request.get("status") == "completed":
            # 병합된 PR은 pr-review-merged가 담당한다. 프롬프트가 completed를
            # close하지 않고 남기므로 이 루틴에는 할 일이 없는데, merged는
            # 17시 하루 한 번이다. 스레드 요약을 digest에 넣으면 오전에 머지된
            # PR이 17시까지 스레드가 건드려질 때마다 no-op 회차를 띄운다.
            structure["prs"]["%s/%s#%s" % (project, repository, pull_request_id)] = {
                "status": "completed"
            }
            continue

        threads = az_json(
            "pr-review-resolve",
            [
                "devops",
                "invoke",
                "--area",
                "git",
                "--resource",
                "pullRequestThreads",
                "--route-parameters",
                f"project={project}",
                f"repositoryId={repository}",
                f"pullRequestId={pull_request_id}",
                "--org",
                org,
                "--api-version",
                "7.1",
            ],
        )
        thread_summary = sorted(
            [
                thread.get("id"),
                thread.get("status"),
                thread.get("lastUpdatedDate"),
                ((thread.get("comments") or [{}])[-1].get("author") or {}).get("uniqueName"),
            ]
            for thread in threads.get("value", [])
            if not thread.get("isDeleted")
            and (thread.get("comments") or [{}])[0].get("commentType") != "system"
            and any(
                ((comment.get("author") or {}).get("uniqueName")) == me
                for comment in (thread.get("comments") or [])
            )
        )
        structure["prs"]["%s/%s#%s" % (project, repository, pull_request_id)] = {
            "status": pull_request.get("status"),
            "srcCommit": (pull_request.get("lastMergeSourceCommit") or {}).get("commitId"),
            "tgtCommit": (pull_request.get("lastMergeTargetCommit") or {}).get("commitId"),
            "createdById": (pull_request.get("createdBy") or {}).get("id"),
            "threads": thread_summary,
        }
    # 맥락으로 넘기는 것은 **손실 없는 값만**이다. `threads`는 digest 해시용
    # 축약이라 댓글 원문도 루트 작성자도 접두어도 없다. 그것을 검증 입력으로
    # 넘기면 세션이 경로 A를 구성할 수 없다(R-02·R-03). 스레드는 세션이 직접
    # 조회한다 — 이 최적화는 5.7%를 아끼려다 검증 경로를 끊었다.
    PR_CONTEXT.clear()
    PR_CONTEXT.update(
        {key: {k: v for k, v in value.items() if k != "threads"}
         for key, value in structure["prs"].items()}
    )
    encoded = json.dumps(structure, sort_keys=True, default=str).encode()
    return hashlib.sha256(encoded).hexdigest()


def repository_names(worklist: list[dict], org: str) -> set[str]:
    """두 worklist가 PR id 키를 다르게 쓴다 — PR 쪽은 `pullRequestId`, 배포 보류
    쪽은 현행 hold 스키마 그대로 `prId`다(DEC-009). 한쪽만 보면 그 worklist의
    fetch 대상이 통째로 비어 회차가 커밋 부재로 미처리가 된다."""
    targets = set()
    for item in worklist:
        repository = item.get("repository")
        project = item.get("project")
        pull_request_id = item.get("pullRequestId") or item.get("prId")
        if not (isinstance(repository, str) and repository and project and pull_request_id):
            continue
        targets.add(fetch_target(org, project, repository, pull_request_id))
    return targets


def fetch_repositories(repositories: set[str]) -> str:
    # 집합이 비어도 부른다 — fetch-repos.sh가 state/fetch-queue를 소비한다.
    # deploy-approve-intake는 세션 안에서 Jira를 조회해야 레포를 알므로 precheck의
    # 직접 발견 집합이 늘 비어 있고, 그때 큐가 소비되지 않으면 F-06이 무효가 된다.
    result = subprocess.run(
        [str(FETCH_REPOS), *sorted(repositories)], check=False, capture_output=True, text=True
    )
    if result.returncode != 0:
        raise RuntimeError("repository fetch failed")
    return result.stdout or ""


def write_diff(repository: str, key: str, src: str, tgt: str) -> dict:
    """PR 소속 변경을 파일로 떨궈 워커가 결정적 git을 부르지 않게 한다.

    워커 1차 리뷰의 도구 호출 18회 중 15회가 `git diff`·`show`·`ls-tree`였고
    46,738토큰이었다(2026-09-16 실측). `srcCommit`·`tgtCommit`만 알면 전부
    결정적이라 세션 밖에서 뽑을 수 있다. 범위 `tgt...src`는 merge-base부터
    source까지여서 PR 소속 커밋의 변경만 나온다 — target에 먼저 들어온 남의
    커밋이 섞이지 않는다.

    요약은 `--stat`이 아니라 `--numstat`이다. `--stat`은 긴 경로를 `...`으로
    줄여서 ADO 스레드의 filePath로 쓸 수 없다.

    실패하면 빈 dict를 돌려준다. 프롬프트가 그때만 워커에게 직접 범위를 잡게
    한다. tgt 커밋이 로컬에 없는 경우가 여기 해당한다.
    """
    if not (src and tgt):
        return {}
    work = pathlib.Path.home() / "work" / repository
    slug = urllib.parse.quote(key, safe="")
    dropped = {}
    # numstat에만 `--no-renames`를 건다. rename을 감지하면 git이 실제 경로 대신
    # `{old => new}/tail` brace 표기를 내보내는데, 그것은 source에 없는 경로라
    # ADO 스레드의 filePath가 되지 못한다(2026-09-16 <레포 C>
    # `{sha}...{sha}` 실측). patch에는 걸지 않는다 — 거기까지 풀면 rename이
    # 파일 전체 삭제+추가가 되어 큰 rename PR의 patch가 두 배가 된다.
    # 바이트로 받아 바이트로 쓴다. text 모드는 PR 안의 UTF-8이 아닌 파일 하나에
    # UnicodeDecodeError를 내고, 그것이 write_context를 뚫고 나가면 그 회차의 맥락
    # 파일이 통째로 안 써진다(config·다른 PR 전부). 내용을 파이썬이 볼 일이 없다.
    outputs = {}
    for field, args in (("numstat", ["--numstat", "--no-renames"]), ("patch", [])):
        result = subprocess.run(
            ["git", "--no-optional-locks", "-C", str(work), "diff", *args, f"{tgt}...{src}"],
            check=False, capture_output=True,
        )
        if result.returncode != 0:
            return {}
        outputs[field] = result.stdout
    # 둘 다 성공한 뒤에 쓴다. numstat만 쓰고 patch에서 실패하면 맥락이 가리키지
    # 않는 고아 파일이 남는다.
    for field, data in outputs.items():
        path = DIFF_DIR / f"{slug}.{field}"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        try:
            dropped[field] = str(path.relative_to(REPO_ROOT))
        except ValueError:
            dropped[field] = str(path)
    return dropped


def write_context(automation: str, fetch_output: str, prs: dict | None = None) -> None:
    """세션이 다시 조회하지 않도록 precheck가 이미 얻은 것을 넘긴다.

    두 가지다. **fetch 결과**는 세션이 착수 투표 전에 코드 판정 가능 여부를 알게
    한다 — 2026-09-16에 <프로젝트 A> PR 3건이 `wait-for-author`만 찍힌 채 리뷰 없이
    남았다. 커밋이 없다는 것을 판정 단계에서야 알았기 때문이다. **PR 상태와 내
    스레드**는 `azdo_digest`가 이미 조회하고 해시만 남긴 뒤 버리던 것으로,
    세션이 `pr show`와 `pullRequestThreads`를 다시 부르지 않게 한다.
    """
    fetched = {}
    for line in fetch_output.splitlines():
        head, _, target = line.partition(": ")
        if target:
            fetched[target.strip()] = head.strip()
    payload = {"generatedAt": int(time.time()), "fetch": fetched}
    if prs is not None:
        payload["prs"] = prs
    # 브랜치 fetch 성공은 그 PR의 source commit 존재를 뜻하지 않는다 — force
    # push나 fetch 직후의 추가 push로 어긋난다(R-07). 실제로 확인해 적는다.
    # precheck는 세션 밖이므로 git을 써도 오케스트레이터 금지와 무관하다.
    for key, value in (prs or {}).items():
        repository = key.split("/")[-1].split("#")[0]
        pull_request_id = key.rsplit("#", 1)[-1]
        target = f"{repository}#{pull_request_id}"
        if value.get("error"):
            fetched[target] = value["error"]
            continue
        commit = value.get("srcCommit")
        if not commit:
            fetched[target] = "no-source-commit"
            continue
        present = subprocess.run(
            ["git", "--no-optional-locks", "-C", str(pathlib.Path.home() / "work" / repository),
             "cat-file", "-e", commit],
            check=False, capture_output=True,
        )
        if present.returncode != 0:
            fetched[target] = "commit-missing"
            continue
        if fetched.get(target, "").startswith("fetch"):
            fetched[target] = "commit-present"
        value.update(write_diff(repository, key, commit, value.get("tgtCommit") or ""))
    marks = load_json(STATE_ROOT / "marks" / f"{automation}.json", {})
    if isinstance(marks, dict) and "lastRunTs" in marks:
        # reviewedPrs는 싣지 않는다 — 세션이 필요한 것은 lastRunTs 하나다. 500건
        # 목록은 bin/prior-review.py가 PR 키로 걸러 준다.
        payload["marks"] = {"lastRunTs": marks["lastRunTs"]}
    try:
        payload["config"] = config_context()
    except Exception as error:
        # 해석에 실패하면 항목을 빼고 세션이 파일을 직접 읽게 둔다. 프롬프트가 그
        # 폴백을 갖는다.
        log(f"config context unavailable: {type(error).__name__}")
    save_json(GATE_DIR / f"context.{automation}.json", payload)


def lock_held(automation: str) -> bool:
    """그 automation의 세션이 이미 돌고 있나. **읽기만 한다.**

    앞 회차가 길어지면 다음 회차의 세션이 떠서 `lock.sh acquire` 실패로 첫
    스텝에서 죽는다. 그 세션도 프롬프트를 읽고 도구 목록을 올리는 비용을 낸다
    — 2026-09-14~15 실측으로 16세션 7.9M 토큰이 그렇게 버려졌다. 여기서 걸러
    세션 기동 자체를 막는다. 설계 DEC-006이 금지한 것은 precheck가 락을 **쓰는**
    것이고, 소유권은 여전히 세션의 `acquire`만 정한다.

    staleness 판정은 `lock.sh`와 같은 30분이다. 좀비 락이 회차를 영구히 막지
    않는다.
    """
    owner = STATE_ROOT / "locks" / f"{automation}.lock" / "owner"
    try:
        acquired = int(owner.read_text().strip())
    except (FileNotFoundError, ValueError, OSError):
        return False
    return time.time() - acquired <= 1800


def committed_path(automation: str) -> Path:
    return GATE_DIR / f"{automation}.json"


def pending_path(automation: str) -> Path:
    return GATE_DIR / f"pending.{automation}.json"


def pending_slack(channel: str, signal: str) -> dict:
    return {"slack_ts": {channel: signal}}


def stored_slack(automation: str, channel: str):
    committed = load_json(committed_path(automation), {})
    return committed.get("slack_ts", {}).get(channel)


def intake_window_oldest(automation: str) -> str:
    """세션이 조회할 창의 시작 epoch. 설계 DEC-009와 같은 식이다 —
    min(now - 1200, lastRunTs - 600), 96시간 상한. fetch 대상 수집이 세션의
    창을 그대로 덮어야 창 안의 PR이 빠짐없이 fetch된다(I-07)."""
    now = int(time.time())
    mark = load_json(STATE_ROOT / "marks" / f"{automation}.json", {})
    last = mark.get("lastRunTs")
    oldest = now - 1200
    if isinstance(last, int):
        oldest = min(oldest, last - 600)
    return str(max(oldest, now - 345600))


def intake_gate(automation: str, channel_name: str) -> tuple[bool, str, set[str]]:
    config = read_config()
    channel = config_channel(config, channel_name)
    signal, repositories = slack_channel_signal(
        bot_token(), channel, intake_window_oldest(automation)
    )
    save_json(pending_path(automation), pending_slack(channel, signal))
    if signal != stored_slack(automation, channel):
        # 계약: 루틴 실행 전에 PR별 상태를 API로 확인해 세션에 전달한다(R-06).
        # 세션이 기동 후 `repos pr show`를 다시 부르지 않게 하고, 착수 투표 전에
        # completed/abandoned를 구분할 수 있게 한다.
        PR_CONTEXT.clear()
        PR_CONTEXT.update(intake_pr_context(automation, repositories))
        return True, "new-channel-activity", repositories
    return False, "ts-unchanged", set()


def intake_pr_context(automation: str, targets: set[str]) -> dict:
    """Slack에서 뽑은 fetch 대상마다 PR 상태를 조회해 **전부** 항목을 남긴다.

    조회에 실패한 PR도 `error`를 달아 넣는다. 항목을 빼면 세션이 같은 상태 API를
    런타임에 다시 부르게 되어 "실행 전에 확인해 전달만 한다"는 계약을 벗어난다
    (R-06). 실패한 PR은 그 회차만 미처리로 남고 다음 회차의 사전 조회로 회복한다.

    조회는 직렬이고 `az_json`의 개별 상한이 90초인데 precheck 전체 예산은
    180초다. 두 건이 연달아 늦으면 fetch와 맥락 저장에 도달하지 못한다(R-13).
    남은 예산을 보며 넘기고, 넘긴 PR도 `error`로 남긴다.
    """
    org = config_ado_org(read_config())
    deadline = time.monotonic() + 90
    context: dict = {}
    for target in sorted(targets):
        repository, _, rest = target.partition("#")
        pull_request_id, _, url = rest.partition("#")
        if not pull_request_id.isdigit() or not url:
            continue
        match = re.search(r"dev\.azure\.com/[^/]+/([^/]+)/_git/", url)
        if not match:
            continue
        project = urllib.parse.unquote(match.group(1))
        repository = urllib.parse.unquote(repository)
        key = "%s/%s#%s" % (project, repository, pull_request_id)
        remaining = int(deadline - time.monotonic())
        if remaining <= 5:
            context[key] = {"error": "precheck-budget"}
            continue
        try:
            # 개별 상한을 **남은 전체 예산**으로 묶는다. 고정 90초를 쓰면 두 건이
            # 연달아 늦을 때 함수가 180초를 쓰고 fetch·맥락 저장에 도달하지
            # 못한다(R-13).
            pull_request = az_json(
                automation,
                ["repos", "pr", "show", "--id", pull_request_id, "--org", org],
                timeout=remaining,
            )
        except Exception:
            context[key] = {"error": "status-unavailable"}
            continue
        if not isinstance(pull_request, dict) or not pull_request:
            context[key] = {"error": "status-unavailable"}
            continue
        context[key] = {
            "status": pull_request.get("status"),
            "srcCommit": (pull_request.get("lastMergeSourceCommit") or {}).get("commitId"),
            "tgtCommit": (pull_request.get("lastMergeTargetCommit") or {}).get("commitId"),
            "createdById": (pull_request.get("createdBy") or {}).get("id"),
        }
    return context


def pr_review_resolve_gate() -> tuple[bool, str, set[str]]:
    worklist = folded_worklist("pr-review-worklist.jsonl")
    org = ado_org_name(read_config())
    repositories = repository_names(worklist, org)
    if not worklist:
        save_json(pending_path("pr-review-resolve"), {"azdo_digest": None})
        return False, "worklist-empty", repositories

    try:
        config = read_config()
        digest = azdo_digest(worklist, config_ado_org(config), config_user(config))
    except Exception:
        save_json(pending_path("pr-review-resolve"), {"azdo_digest": None})
        return True, "digest-unavailable", repositories
    save_json(pending_path("pr-review-resolve"), {"azdo_digest": digest})
    committed = load_json(committed_path("pr-review-resolve"), {})
    if digest != committed.get("azdo_digest"):
        return True, "digest-changed", repositories
    return False, "digest-unchanged", repositories


def parse_held_at(value) -> datetime:
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, timezone.utc)
    if not isinstance(value, str):
        raise ValueError("heldAt is missing")
    if value.isdigit():
        return datetime.fromtimestamp(int(value), timezone.utc)
    normalized = re.sub(r"([+-]\d{2})(\d{2})$", r"\1:\2", value.replace("Z", "+00:00"))
    parsed = datetime.fromisoformat(normalized)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def deploy_resolve_gate() -> tuple[bool, str, set[str]]:
    worklist = folded_worklist("deploy-approve-worklist.jsonl")
    repositories = repository_names(worklist, ado_org_name(read_config()))
    if not worklist:
        return False, "worklist-empty", repositories

    try:
        now = datetime.now(timezone.utc)
        if any(now - parse_held_at(item.get("heldAt")) > timedelta(days=7) for item in worklist):
            return True, "hold-expired", repositories

        config = read_config()
        token = bot_token()
        default_channel = config_channel(config, "#deploy-approval")
        for item in worklist:
            message_ts = item.get("messageTs")
            if not message_ts:
                raise ValueError("worklist item has no messageTs")
            latest = slack_thread_signal(
                token,
                item.get("channel") or default_channel,
                str(message_ts),
                str(item.get("lastCheckedTs") or 0),
            )
            if latest != "no-new" and float(latest) > float(item.get("lastCheckedTs") or 0):
                return True, "new-thread-reply", repositories
    except Exception:
        return True, "thread-check-failed", repositories
    return False, "threads-quiet", repositories


def pr_review_merged_gate() -> tuple[bool, str, set[str]]:
    worklist = folded_worklist("pr-review-worklist.jsonl")
    repositories = repository_names(worklist, ado_org_name(read_config()))
    if not worklist:
        return False, "worklist-empty", repositories

    try:
        org = config_ado_org(read_config())
        for item in worklist:
            pull_request = az_json(
                "pr-review-merged",
                ["repos", "pr", "show", "--id", str(item["pullRequestId"]), "--org", org],
            )
            if pull_request.get("status") == "completed":
                return True, "completed-pr", repositories
    except Exception:
        return True, "completed-check-failed", repositories
    return False, "no-completed-pr", repositories


def decide(automation: str) -> tuple[bool, str, set[str]]:
    if automation not in AUTOMATIONS:
        raise ValueError("unknown automation")
    if automation == "pr-review-intake":
        return intake_gate(automation, "#pr-review-requests")
    if automation == "deploy-approve-intake":
        return intake_gate(automation, "#deploy-approval")
    if automation == "pr-review-resolve":
        return pr_review_resolve_gate()
    if automation == "deploy-approve-resolve":
        return deploy_resolve_gate()
    return pr_review_merged_gate()


def commit(automation: str) -> int:
    if automation not in GATED_AUTOMATIONS:
        return 0
    snapshot = GATE_DIR / f"snapshot.{automation}.json"
    if not snapshot.exists():
        return 0
    save_json(committed_path(automation), load_json_strict(snapshot))
    return 0


def main(arguments: list[str]) -> int:
    try:
        if len(arguments) == 2 and arguments[0] == "commit":
            return commit(arguments[1])
        if len(arguments) != 1:
            raise ValueError("usage: precheck.py <automation> | commit <automation>")
        automation = arguments[0]
        if automation in AUTOMATIONS and lock_held(automation):
            print(f"SKIP {automation} reason=lock-held")
            return SKIP_EXIT
        should_run, reason, repositories = decide(automation)
        if should_run:
            write_context(automation, fetch_repositories(repositories), PR_CONTEXT or None)
            print(f"RUN {automation} reason={reason}")
            return 0
        print(f"SKIP {automation} reason={reason}")
        # 10 = 의도한 SKIP. 1을 쓰면 파이썬 자신의 실패(구문 오류·import 실패도
        # 종료 코드 1이다)와 구분되지 않아, precheck.sh가 그것을 SKIP으로 넘겨
        # 해당 automation이 영구히 안 돈다.
        return SKIP_EXIT
    except Exception as error:
        log(f"precheck failed open: {type(error).__name__}")
        return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
