# -*- coding: utf-8 -*-
"""GitHub Issues 唯讀/寫客戶端，給 /issue 系列指令用。

待辦清單的「資料庫」是 GitHub Issues 本身，不是自己刻一份 markdown
解析/序列化邏輯——理由詳見計畫書。這裡只負責組 request、解析回應，
不做任何 Discord 相關的事（跟 llm_client.py 對 cogs 的分工一樣）。

⚠️ 設計約束：跟 llm_client.py 同一個原則——這裡只做「文字進、文字出」
的 CRUD，不執行任何 shell/系統指令，也不讀寫本地檔案。所有函式回傳
(成功: bool, 資料或錯誤訊息) 的 tuple，不讓例外流出去讓呼叫端意外崩潰。

REST API 沒有「刪除 issue」這個端點——只有 open/closed 兩種狀態。
要做到字面上的刪除，只能透過 GraphQL 的 deleteIssue mutation
（先查 issue 的 node id，再送 mutation），所以 delete_issue() 跟其他
函式不一樣，是唯一一個打 GraphQL 而不是 REST 的函式。
"""
from __future__ import annotations

import httpx

import config

API_BASE = "https://api.github.com"
GRAPHQL_URL = "https://api.github.com/graphql"

# GitHub 建議帶的版本標頭，避免未來 API 版本更新時行為悄悄改變
_API_VERSION = "2022-11-28"

# 對應「緊急／次要」兩個分類的標籤。name 刻意用英文 slug（當 URL query
# 參數/GraphQL 變數用，不用處理中文編碼問題），description 放中文說明，
# 顯示在 GitHub 網頁的標籤 tooltip 上。
LABELS: dict[str, dict[str, str]] = {
    "urgent": {"color": "d73a4a", "description": "緊急：會影響遊戲進程"},
    "polish": {"color": "a2eeef", "description": "次要：外觀／遊玩體驗"},
}


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {config.GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": _API_VERSION,
    }


def _not_configured() -> str | None:
    """回傳缺少設定的錯誤訊息；設定齊全回 None。"""
    if not config.GITHUB_TOKEN:
        return "GITHUB_TOKEN 未設定，請於 ops/.env 填入具 repo 權限的個人存取權杖。"
    if not config.GITHUB_REPO:
        return "偵測不到 GitHub repo（GITHUB_REPO 未設定，且從 git remote 自動推算失敗）。"
    return None


async def ensure_labels() -> tuple[bool, str]:
    """確認 urgent/polish 這兩個標籤存在，不存在就建立。

    第一次用到 /issue add 前，或 bot 啟動時呼叫一次即可；標籤已存在時
    是安全的空操作（GitHub 建立同名標籤會回 422，這裡當成「已存在」
    處理，不算失敗）。
    """
    problem = _not_configured()
    if problem:
        return False, problem

    owner_repo = config.GITHUB_REPO
    try:
        async with httpx.AsyncClient(timeout=15.0, headers=_headers()) as client:
            r = await client.get(f"{API_BASE}/repos/{owner_repo}/labels", params={"per_page": 100})
            if r.status_code != 200:
                return False, f"查詢標籤失敗：HTTP {r.status_code} {r.text[:300]}"
            existing = {item["name"] for item in r.json()}

            created = []
            for name, meta in LABELS.items():
                if name in existing:
                    continue
                cr = await client.post(
                    f"{API_BASE}/repos/{owner_repo}/labels",
                    json={"name": name, "color": meta["color"], "description": meta["description"]},
                )
                # 422 通常代表標籤剛好被別的地方同時建立了，當成已存在，不當失敗
                if cr.status_code not in (201, 422):
                    return False, f"建立標籤 {name} 失敗：HTTP {cr.status_code} {cr.text[:300]}"
                if cr.status_code == 201:
                    created.append(name)
            return True, (f"已建立標籤：{', '.join(created)}" if created else "標籤都已存在")
    except httpx.TimeoutException:
        return False, "連線 GitHub 逾時。"
    except Exception as e:
        return False, f"連線 GitHub 失敗：{type(e).__name__}: {e}"


async def list_issues(label: str | None, state: str = "open") -> tuple[bool, list[dict] | str]:
    """列出 issue。label 為 None 時不篩選（緊急+次要都回傳）。

    GET /repos/{owner}/{repo}/issues 這個端點本來就會把 PR 也混進來
    （GitHub 把 PR 實作成一種特殊的 issue），要用有沒有 "pull_request"
    這個 key 濾掉，不然清單裡會混進不相關的 PR。
    """
    problem = _not_configured()
    if problem:
        return False, problem

    params: dict[str, str] = {"state": state, "per_page": "100"}
    if label:
        params["labels"] = label

    try:
        async with httpx.AsyncClient(timeout=15.0, headers=_headers()) as client:
            r = await client.get(f"{API_BASE}/repos/{config.GITHUB_REPO}/issues", params=params)
            if r.status_code != 200:
                return False, f"查詢 issue 失敗：HTTP {r.status_code} {r.text[:300]}"
            items = [item for item in r.json() if "pull_request" not in item]
            return True, items
    except httpx.TimeoutException:
        return False, "連線 GitHub 逾時。"
    except Exception as e:
        return False, f"連線 GitHub 失敗：{type(e).__name__}: {e}"


async def create_issue(label: str, title: str, body: str = "") -> tuple[bool, dict | str]:
    problem = _not_configured()
    if problem:
        return False, problem

    try:
        async with httpx.AsyncClient(timeout=15.0, headers=_headers()) as client:
            r = await client.post(
                f"{API_BASE}/repos/{config.GITHUB_REPO}/issues",
                json={"title": title, "body": body, "labels": [label]},
            )
            if r.status_code != 201:
                return False, f"建立 issue 失敗：HTTP {r.status_code} {r.text[:300]}"
            return True, r.json()
    except httpx.TimeoutException:
        return False, "連線 GitHub 逾時。"
    except Exception as e:
        return False, f"連線 GitHub 失敗：{type(e).__name__}: {e}"


async def set_state(number: int, closed: bool) -> tuple[bool, str]:
    """打勾 = 關閉（closed=True），取消勾選 = 重新開啟（closed=False）。"""
    problem = _not_configured()
    if problem:
        return False, problem

    try:
        async with httpx.AsyncClient(timeout=15.0, headers=_headers()) as client:
            r = await client.patch(
                f"{API_BASE}/repos/{config.GITHUB_REPO}/issues/{number}",
                json={"state": "closed" if closed else "open"},
            )
            if r.status_code != 200:
                return False, f"更新 issue #{number} 狀態失敗：HTTP {r.status_code} {r.text[:300]}"
            return True, f"#{number} 已{'關閉' if closed else '重新開啟'}"
    except httpx.TimeoutException:
        return False, "連線 GitHub 逾時。"
    except Exception as e:
        return False, f"連線 GitHub 失敗：{type(e).__name__}: {e}"


async def edit_issue(number: int, title: str | None, body: str | None) -> tuple[bool, str]:
    """title/body 至少要給一個，只送有給值的欄位——呼叫端（issue_cog）
    負責檔掉「兩個都沒給」這種無意義的呼叫。
    """
    problem = _not_configured()
    if problem:
        return False, problem

    payload: dict[str, str] = {}
    if title is not None:
        payload["title"] = title
    if body is not None:
        payload["body"] = body
    if not payload:
        return False, "標題與說明至少要給一個。"

    try:
        async with httpx.AsyncClient(timeout=15.0, headers=_headers()) as client:
            r = await client.patch(
                f"{API_BASE}/repos/{config.GITHUB_REPO}/issues/{number}", json=payload)
            if r.status_code != 200:
                return False, f"編輯 issue #{number} 失敗：HTTP {r.status_code} {r.text[:300]}"
            return True, f"#{number} 已更新"
    except httpx.TimeoutException:
        return False, "連線 GitHub 逾時。"
    except Exception as e:
        return False, f"連線 GitHub 失敗：{type(e).__name__}: {e}"


async def delete_issue(number: int) -> tuple[bool, str]:
    """真的刪除（不是關閉）。REST 沒有這個端點，改用 GraphQL：
    先查 issue 的 node id，再送 deleteIssue mutation。

    這個操作不可逆，且需要 token 對這個 repo有夠高的權限（刪除 issue
    這個動作 GitHub 限制得比開關 issue 嚴格）——權限不足時 GraphQL
    會回一個 errors 陣列而不是 HTTP 錯誤碼，這裡要另外檢查。
    """
    problem = _not_configured()
    if problem:
        return False, problem

    owner, repo = config.GITHUB_REPO.split("/", 1)
    query = """
    query($owner: String!, $repo: String!, $number: Int!) {
      repository(owner: $owner, name: $repo) {
        issue(number: $number) { id }
      }
    }
    """
    mutation = """
    mutation($id: ID!) {
      deleteIssue(input: {issueId: $id}) { clientMutationId }
    }
    """

    try:
        async with httpx.AsyncClient(timeout=15.0, headers=_headers()) as client:
            qr = await client.post(
                GRAPHQL_URL,
                json={"query": query, "variables": {"owner": owner, "repo": repo, "number": number}},
            )
            if qr.status_code != 200:
                return False, f"查詢 issue #{number} 失敗：HTTP {qr.status_code} {qr.text[:300]}"
            qdata = qr.json()
            if qdata.get("errors"):
                return False, f"查詢 issue #{number} 失敗：{qdata['errors'][0].get('message', qdata['errors'])}"
            issue_node = ((qdata.get("data") or {}).get("repository") or {}).get("issue")
            if not issue_node:
                return False, f"找不到 issue #{number}。"
            node_id = issue_node["id"]

            mr = await client.post(GRAPHQL_URL, json={"query": mutation, "variables": {"id": node_id}})
            if mr.status_code != 200:
                return False, f"刪除 issue #{number} 失敗：HTTP {mr.status_code} {mr.text[:300]}"
            mdata = mr.json()
            if mdata.get("errors"):
                msg = mdata["errors"][0].get("message", str(mdata["errors"]))
                return False, f"刪除 issue #{number} 失敗：{msg}（token 可能沒有刪除 issue 的權限）"
            return True, f"#{number} 已永久刪除"
    except httpx.TimeoutException:
        return False, "連線 GitHub 逾時。"
    except Exception as e:
        return False, f"連線 GitHub 失敗：{type(e).__name__}: {e}"
