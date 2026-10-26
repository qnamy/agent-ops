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


def slack_latest_ts(token: str, channel: str) -> str:
    """창과 무관한 채널 전체의 최신 ts — intake 게이트 신호이자 commit 재계산 입력."""
    head = slack_api(token, "conversations.history", {"channel": channel, "limit": 1})
    head_messages = head.get("messages", [])
    if not head_messages:
        return "no-messages"
    latest = head_messages[0].get("ts")
    if latest is None:
        raise RuntimeError("Slack latest message has no ts")
    return str(latest)


def slack_channel_signal(
    token: str, channel: str, oldest: str | None = None, committed: str | None = None,
    review_config: str | None = None,
) -> tuple[str, dict]:
    """게이트 신호와 fetch 대상을 각각 다른 조회로 얻는다.

    신호는 **창과 무관하게 채널 전체의 최신 ts**다. 창을 씌우면 96시간 동안
    조용한 채널에서 응답이 비어 신호가 `no-messages`가 되고, committed의 옛
    ts와 달라 매 회차 RUN한다(토큰 절감이 무너진다).

    fetch 대상은 세션이 처리할 창을 cursor가 소진될 때까지 읽는다. 한 페이지만
    읽거나 페이지 수를 고정하면 뒤 페이지 PR의 레포가 fetch되지 않는다. 대상마다
    그 PR을 언급한 가장 이른 메시지의 ts를 함께 담아 돌려준다 — 예산이 모자라
    넘긴 PR의 경계를 commit이 그 ts로 계산한다.

    **committed ts 이하의 메시지는 대상에서 뺀다.** committed는 그 채널의 처리
    완료 경계이고, 예산이 모자라 넘긴 PR이 있으면 commit이 그 경계를 이미
    낮춰 둔다. 창은 `lastRunTs - 600`이라 한 건이라도 미처리로 mark가 멈추면
    같은 메시지들이 매 회차 다시 대상이 되어 `pr show` 예산을 먹고 새 PR을
    뒤로 민다(라이브락). cap된 회차에는 넘긴 메시지만 남아 큐가 회차마다 준다.
    """
    if review_config is not None:
        excluded_users = {config_slack_user(review_config), config_bot_user(review_config)}
        mentions = config_mentions(review_config)
    latest = slack_latest_ts(token, channel)
    if latest == "no-messages":
        return "no-messages", {}

    # ts는 자릿수가 고정된 epoch 문자열이라 사전순 비교가 수치 비교와 같다.
    floor = committed if isinstance(committed, str) and committed != "no-messages" else None
    targets: dict[str, str] = {}
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
                # conversations.history는 최신 메시지부터 준다 — 뒤에 오는 언급이
                # 더 이르므로 덮어쓰면 대상마다 가장 이른 ts가 남는다.
                message_ts = str(message.get("ts") or "")
                if floor and message_ts and message_ts <= floor:
                    continue
                if review_config is not None:
                    if message.get("user") in excluded_users:
                        continue
                    if not any(mention in message.get("text", "") for mention in mentions):
                        continue
                for org, project, repository, pull_request_id in PR_URL.findall(message.get("text", "")):
                    targets[fetch_target(org, project, repository, pull_request_id)] = message_ts
        cursor = (payload.get("response_metadata") or {}).get("next_cursor")
        pages += 1
        if not cursor:
            break
        if pages >= 200:
            # 조용히 자르지 않는다 — 자르면 뒤 페이지 레포가 영구히 fetch되지 않는다.
            raise RuntimeError("Slack history pagination did not terminate")
    return latest, targets


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


def is_routine_comment(comment: dict, me: str, disclaimer: str) -> bool:
    """봇 계정이 쓰고 서명 두 줄로 끝나는 댓글 — 어느 automation이 썼든 봇 쓰기다.

    같은 계정이라도 서명이 없는 댓글(사람의 UI 댓글·다른 용도의 세션)은 외부
    신호로 세야 한다."""
    return (
        comment.get("commentType") == "text"
        and ((comment.get("author") or {}).get("uniqueName")) == me
        and (comment.get("content") or "").rstrip().endswith(disclaimer)
    )


def azdo_structure(worklist: list[dict], org: str, me: str, disclaimer: str) -> dict:
    """세션이 실제로 처리하는 신호만 담는다.

    이전에는 PR의 모든 스레드를 넣어서, 남이 만든 스레드 하나가 바뀌어도 회차가
    떴다. 세션이 처리하는 것은 **내가 댓글을 단 스레드**다 — 내가 루트인 것은
    경로 A·B의 대상이고, 남의 루트에 단 내 `issue:`/`discuss:` 답글은 재투표와
    close 판정의 입력이다. 그래서 내 댓글이 하나라도 있는 스레드만 담는다.
    루트만으로 좁히면 남의 스레드에 단 내 답글이 해소돼도 게이트가 RUN을 내지
    않아 재투표가 열리지 않는다. `commentType: system` 스레드는 제외한다 — 내
    투표가 시스템 스레드를 만들어 digest를 흔들면 매 회차 RUN이 된다.

    스레드 항목은 `[id, status, [[비루틴 댓글 id, lastContentUpdatedDate], ...]]`다.
    루틴 댓글(`is_routine_comment`)은 신호에서 뺀다 — 자기 쓰기가 digest를
    흔들지 않아야 종료 커밋이 snapshot 재생으로 끝난다(자기유발과 삼키기를
    동시에 닫는다). 포함 판정은 disclaimer와 무관하게 내 댓글 존재로 한다 —
    `by Claude Code`로 끝나는 예전 루틴 댓글만 있는 스레드도 계속 추적한다.
    `lastUpdatedDate`는 봇 댓글로도 갱신돼 키에서 뺐고, status는 사람의 조용한
    변경을 잡기 위해 남긴다 — 자기 PATCH는 commit의 재생으로 상쇄한다.

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
                [
                    [comment.get("id"), comment.get("lastContentUpdatedDate")]
                    for comment in (thread.get("comments") or [])
                    if comment.get("commentType") == "text"
                    and not comment.get("isDeleted")
                    and not is_routine_comment(comment, me, disclaimer)
                ],
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
    return structure


def structure_digest(structure: dict) -> str:
    encoded = json.dumps(structure, sort_keys=True, default=str).encode()
    return hashlib.sha256(encoded).hexdigest()


def repository_names(worklist: list[dict], org: str) -> set[str]:
    """두 worklist가 PR id 키를 다르게 쓴다 — PR 쪽은 `pullRequestId`, 배포 보류
    쪽은 현행 hold 스키마 그대로 `prId`다(DEC-009). 한쪽만 보면 그 worklist의
    fetch 대상이 통째로 비어 회차가 커밋 부재로 미처리가 된다."""
    targets = set()
    for item in worklist:
        prs = item.get("prs", [])
        if not isinstance(prs, list):
            prs = []
        for pr in [item, *prs]:
            if not isinstance(pr, dict):
                continue
            repository = pr.get("repository")
            project = pr.get("project")
            pull_request_id = pr.get("pullRequestId") or pr.get("prId")
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
    # 수집의 committed 하한을 세션에도 넘긴다. precheck는 `slack_channel_signal`에서
    # 이 ts 이하의 메시지를 대상에서 빼는데, 세션의 창(`lastRunTs - 600`)만 쓰면 그
    # 사이에 걸린 메시지가 맥락 없는 `미처리`로 떨어져 commit이 영구히 막힌다 —
    # 지적 0건으로 끝난 PR은 루트 댓글도 맥락 항목도 없어 어느 멱등 가드도 못 잡는다.
    committed = load_json(committed_path(automation), {})
    signals = committed.get("slack_ts") if isinstance(committed, dict) else None
    floors = [v for v in (signals or {}).values() if isinstance(v, str) and v != "no-messages"]
    if floors:
        payload["slackFloor"] = max(floors)
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

    staleness 판정은 `lock.sh`와 같은 30분이고, 나이도 같은 값으로 읽는다 —
    owner 파일의 획득 epoch과 `heartbeat` mtime 중 **최신**이다. 획득 epoch만
    보면 30분을 넘겨 살아 있는 회차(그 세션의 `lock.sh check`가 heartbeat를
    갱신한다)를 좀비로 읽어, 락이 잡힌 automation의 세션을 띄운다 — 그 세션은
    `acquire` 실패로 첫 스텝에서 죽으면서 기동 비용만 낸다. heartbeat가 없는
    구형식 락은 owner만 본다.
    """
    lock = STATE_ROOT / "locks" / f"{automation}.lock"
    try:
        acquired = int((lock / "owner").read_text().strip())
    except (FileNotFoundError, ValueError, OSError):
        return False
    try:
        acquired = max(acquired, int((lock / "heartbeat").stat().st_mtime))
    except OSError:
        pass
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
    committed = stored_slack(automation, channel)
    signal, targets = slack_channel_signal(
        bot_token(), channel, intake_window_oldest(automation), committed,
        review_config=config if automation == "pr-review-intake" else None,
    )
    save_json(pending_path(automation), pending_slack(channel, signal))
    if signal != committed:
        if (automation == "pr-review-intake" and not targets
                and (STATE_ROOT / "live" / f"{automation}.enabled").exists()):
            return False, "no-targets", set()
        # 계약: 루틴 실행 전에 PR별 상태를 API로 확인해 세션에 전달한다(R-06).
        # 세션이 기동 후 `repos pr show`를 다시 부르지 않게 하고, 착수 투표 전에
        # completed/abandoned를 구분할 수 있게 한다.
        PR_CONTEXT.clear()
        PR_CONTEXT.update(intake_pr_context(automation, targets))
        return True, "new-channel-activity", set(targets)
    return False, "ts-unchanged", set()


def intake_pr_context(automation: str, targets: dict) -> dict:
    """Slack에서 뽑은 fetch 대상마다 PR 상태를 조회해 **전부** 항목을 남긴다.

    조회에 실패한 PR도 `error`를 달아 넣는다. 항목을 빼면 세션이 같은 상태 API를
    런타임에 다시 부르게 되어 "실행 전에 확인해 전달만 한다"는 계약을 벗어난다
    (R-06). 실패한 PR은 그 회차만 미처리로 남고 다음 회차의 사전 조회로 회복한다.

    조회는 직렬이고 `az_json`의 개별 상한이 90초인데 precheck 전체 예산은
    180초다. 두 건이 연달아 늦으면 fetch와 맥락 저장에 도달하지 못한다(R-13).
    남은 예산을 보며 넘기고, 넘긴 PR도 `error`로 남긴다. 처리는 **메시지가
    이른 순**이다 — 예산이 모자라면 최신 것부터 넘어가고, commit이 넘어간 것들의
    경계 앞에서 committed ts를 끊어 다음 회차가 나머지를 이어받는다.
    """
    org = config_ado_org(read_config())
    deadline = time.monotonic() + 90
    context: dict = {}
    for target in sorted(targets, key=lambda value: (targets[value], value)):
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
        # ts는 이 PR을 언급한 가장 이른 Slack 메시지다. commit이 넘어간 PR의
        # 경계를 이 값으로 계산한다.
        record = {"ts": targets[target]}
        context[key] = record
        fill_pr_record(automation, org, record, pull_request_id, deadline)
    return context


def fill_pr_record(automation: str, org: str, record: dict, pull_request_id: str, deadline: float) -> None:
    """record에 PR 상태 필드를 채운다. 예산이 없거나 조회가 실패하면 `error`만 남긴다.

    개별 상한을 **남은 전체 예산**으로 묶는다. 고정 90초를 쓰면 두 건이 연달아
    늦을 때 함수가 180초를 쓰고 fetch·맥락 저장에 도달하지 못한다(R-13)."""
    remaining = int(deadline - time.monotonic())
    if remaining <= 5:
        record["error"] = "precheck-budget"
        return
    try:
        pull_request = az_json(
            automation,
            ["repos", "pr", "show", "--id", pull_request_id, "--org", org],
            timeout=remaining,
        )
    except Exception:
        record["error"] = "status-unavailable"
        return
    if not isinstance(pull_request, dict) or not pull_request:
        record["error"] = "status-unavailable"
        return
    record.update({
        "status": pull_request.get("status"),
        "srcCommit": (pull_request.get("lastMergeSourceCommit") or {}).get("commitId"),
        "tgtCommit": (pull_request.get("lastMergeTargetCommit") or {}).get("commitId"),
        "createdById": (pull_request.get("createdBy") or {}).get("id"),
    })


def resolve_pending(worklist: list[dict], as_of: float) -> dict:
    """pr-review-resolve 게이트가 pending에 쓰는 값. `structure`·`asOf`를 실어
    두면 round.py가 pending을 snapshot으로 통째 복사해 commit의 재생 입력이 된다."""
    if not worklist:
        return {"azdo_digest": None}
    config = read_config()
    structure = azdo_structure(
        worklist, config_ado_org(config), config_user(config), config_disclaimer(config)
    )
    return {
        "azdo_digest": structure_digest(structure),
        "structure": structure,
        "asOf": as_of,
    }


def pr_review_resolve_gate() -> tuple[bool, str, set[str]]:
    as_of = time.time()
    worklist = folded_worklist("pr-review-worklist.jsonl")
    org = ado_org_name(read_config())
    repositories = repository_names(worklist, org)
    if not worklist:
        save_json(pending_path("pr-review-resolve"), {"azdo_digest": None})
        return False, "worklist-empty", repositories

    try:
        pending = resolve_pending(worklist, as_of)
    except Exception:
        save_json(pending_path("pr-review-resolve"), {"azdo_digest": None})
        return True, "digest-unavailable", repositories
    save_json(pending_path("pr-review-resolve"), pending)
    committed = load_json(committed_path("pr-review-resolve"), {})
    if pending["azdo_digest"] != committed.get("azdo_digest"):
        return True, "digest-changed", repositories
    return False, "digest-unchanged", repositories


def _resolve_own_lines(name: str, as_of: float):
    """이번 회차의 원장 줄만 돌려준다 — `by`와 `ts > asOf`로 귀속한다.

    파일 읽기·JSON 파싱 실패는 그대로 올라간다 — commit이 `azdo_digest: null`로
    무효화해 다음 precheck가 RUN을 낸다. `by`가 다르거나 `ts`가 없는 계약 이전
    줄은 이번 회차의 것이 아니므로 건너뛴다."""
    for raw in (STATE_ROOT / name).read_text().splitlines():
        line = json.loads(raw)
        if line.get("by") != "pr-review-resolve":
            continue
        ts = line.get("ts")
        if not isinstance(ts, (int, float)) or ts <= as_of:
            continue
        yield line


def _pr_key(line: dict) -> str:
    return "%s/%s#%s" % (line["project"], line["repository"], line["pullRequestId"])


def _replay_target(prs: dict, key: str):
    entry = prs.get(key)
    if not isinstance(entry, dict) or not isinstance(entry.get("threads"), list):
        raise ValueError(f"replay target missing: {key}")
    return entry["threads"]


def resolve_committed(snapshot: dict) -> dict:
    """snapshot 구조에 이 회차 자신의 op만 재생해 committed를 만든다.

    종료 시점 라이브 재계산은 회차 중 도착한 외부 변화까지 committed에 실어
    삼켰다(2026-10-12 `Ais#{PR}` — 답글이 회차 조회 40초 뒤에 도착했는데
    commit에 포함돼 이후 precheck가 영구히 `digest-unchanged`가 됐다). 재생은
    회차가 소비한 상태에 자기가 만든 상태만 얹으므로, 회차 중의 외부 변화는
    committed와 pending의 차이로 남아 다음 회차를 발화시킨다.

    재생 대상으로 식별된 줄을 적용할 수 없으면 실패다 — 건너뛰고 정상 해시를
    쓰면 자기 쓰기가 빠진 채 값이 수렴해 외부 변화를 삼킨다."""
    structure = snapshot.get("structure")
    if not isinstance(structure, dict):
        return snapshot  # 전환기 구형 — 해시 입력이 달라 1회 RUN 뒤 수렴한다.
    as_of = snapshot["asOf"]
    prs = structure["prs"]

    # 복구가 만든 새 루트 스레드를 먼저 넣는다 — 아래 status 재생이 이 스레드를
    # 참조할 수 있고, close가 마지막에 적용돼도 덮이지 않는다.
    for line in _resolve_own_lines("review-findings.jsonl", as_of):
        if "threadId" not in line:
            continue  # 스레드를 만들지 않은 줄은 재생 대상이 아니다.
        threads = _replay_target(prs, _pr_key(line))
        thread_id = int(line["threadId"])
        if not any(entry[0] == thread_id for entry in threads):
            threads.append([thread_id, "active", []])
            threads.sort()

    for line in _resolve_own_lines("code-quality-list.jsonl", as_of):
        if "threadStatus" not in line:
            continue  # PATCH하지 않은 줄(타인 루트 해소 등)은 재생하지 않는다.
        # 대상은 occId에서 온다 — 별도 좌표 필드가 올바르게 적혀 있어도 깨진
        # occId는 그 줄의 귀속을 증명하지 못하므로 재생 실패다.
        key, thread_text = line["occId"].rsplit("/", 1)
        thread_id = int(thread_text)
        threads = _replay_target(prs, key)
        target = next((entry for entry in threads if entry[0] == thread_id), None)
        if target is None:
            raise ValueError(f"replay target thread missing: {key}/{thread_id}")
        target[1] = line["threadStatus"]

    for line in _resolve_own_lines("pr-review-worklist.jsonl", as_of):
        if line.get("op") != "close":
            continue  # resolve는 add를 쓰지 않는다 — 재생하지 않은 자기 op는
            # committed에 옛 상태로 남아 과발화하는 안전 방향이다.
        key = line["key"]
        if key not in prs:
            raise ValueError(f"replay target missing: {key}")
        del prs[key]
        structure["worklist"] = [
            item for item in structure["worklist"]
            if "%s/%s#%s" % (item[0], item[1], item[2]) != key
        ]

    return {"azdo_digest": structure_digest(structure)}


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


def slack_ts_before(value: str) -> str:
    """Slack ts 한 눈금(마이크로초) 이전 값. ts의 자릿수가 곧 해상도다."""
    seconds, _, fraction = value.partition(".")
    micro = int(seconds) * 1000000 + int(fraction.ljust(6, "0")[:6]) - 1
    return "%d.%06d" % divmod(micro, 1000000)


def cap_committed_slack(automation: str, payload: dict) -> dict:
    """예산 부족으로 넘긴 PR이 있으면 committed ts를 가장 이른 그 메시지 직전까지
    낮춘다.

    넘긴 PR까지 포함한 ts를 커밋하면 그 메시지는 다음 메시지가 올 때까지 다시
    수집되지 않고, 그 사이 `lastRunTs`만 앞서가 수집 창이 넓어져 예산 초과가
    재발한다(래칫). 경계를 낮추면 다음 tick이 `new-channel-activity`로 떠서
    나머지를 이어받는다. ts는 자릿수가 고정된 epoch 문자열이라 사전순 비교가
    수치 비교와 같다."""
    context = load_json(GATE_DIR / f"context.{automation}.json", {})
    prs = context.get("prs") if isinstance(context, dict) else None
    deferred = [
        str(value["ts"])
        for value in (prs or {}).values()
        if isinstance(value, dict) and value.get("error") == "precheck-budget" and value.get("ts")
    ]
    signals = payload.get("slack_ts") if isinstance(payload, dict) else None
    if not (deferred and isinstance(signals, dict)):
        return payload
    limit = slack_ts_before(min(deferred))
    for channel, signal in signals.items():
        if signal != "no-messages" and signal > limit:
            signals[channel] = limit
    return payload


def commit(automation: str) -> int:
    """intake 둘은 회차 시작 시점 snapshot을 옮긴다(`pr-review-intake`는 예산이
    모자라 넘긴 PR의 경계까지 낮춘 값). 그 둘의 신호는 채널 전체 최신 ts인데
    회차의 쓰기는 스레드 답글이라 그 ts를 올리지 않아 자기유발이 성립하지 않고,
    종료 시점 재계산은 회차 중 도착해 수집되지 않은 메시지까지 committed에 실어
    다음 tick을 `ts-unchanged`로 재우는 손실 창만 만든다.

    `pr-review-resolve`는 종료 시점 재계산 대신 snapshot 구조에 이 회차 자신의
    op를 재생한 값을 committed로 쓴다(`resolve_committed`). 재생이 실패하면
    `azdo_digest: null`을 커밋해 다음 precheck가 RUN을 내게 한다 — 아예
    커밋하지 않으면 미처리 재시도 트리거(미커밋 재발화)와 구별되지 않는다."""
    if automation not in GATED_AUTOMATIONS:
        return 0
    snapshot = GATE_DIR / f"snapshot.{automation}.json"
    if not snapshot.exists():
        return 0
    if automation == "pr-review-resolve":
        try:
            payload = resolve_committed(load_json_strict(snapshot))
        except Exception as error:
            log(f"gate replay failed, committing null digest: {type(error).__name__}")
            save_json(committed_path(automation), {"azdo_digest": None})
            return 1
    elif automation == "pr-review-intake":
        # cap은 이 automation에만 건다. `deploy-approve-intake`는 `context.prs`를
        # 쓰지 않고 프롬프트에 예산 규칙도 없어, 정상 성공 회차의 committed ts만
        # 낮춰 다음 tick을 헛발화시킨다.
        try:
            payload = cap_committed_slack(automation, load_json_strict(snapshot))
        except Exception as error:
            # 예외를 그대로 내보내면 main의 catch-all이 0을 돌려주고 round.py가
            # `commit: done`으로 적는다 — 커밋이 안 됐는데 됐다고 보고된다.
            # 재계산 갈래와 같이 snapshot을 옮긴다.
            log(f"budget cap failed, committing snapshot: {type(error).__name__}")
            payload = load_json_strict(snapshot)
    else:
        payload = load_json_strict(snapshot)
    save_json(committed_path(automation), payload)
    return 0


def main(arguments: list[str]) -> int:
    if len(arguments) == 2 and arguments[0] == "commit":
        # commit 실패는 fail open이 아니다. 아래 catch-all에 맡기면 0이 나가고
        # round.py가 그것을 `commit: done`으로 적는다 — 커밋되지 않은 회차가
        # 완료로 보고되고, 미커밋 재발화라는 재시도 경로도 함께 사라진다.
        try:
            return commit(arguments[1])
        except Exception as error:
            log(f"gate commit failed: {type(error).__name__}")
            return 1
    try:
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
