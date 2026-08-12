"""非流式 Chat Completions 有序故障切换服务。"""
from __future__ import annotations

import json
import sqlite3
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import aiosqlite
import httpx

from ..config import settings
from ..security import decrypt_api_key


@dataclass(slots=True)
class Candidate:
    upstream_id: str
    display_name: str
    base_url: str
    encrypted_api_key: str
    model: str
    timeout_ms: int


@dataclass(slots=True)
class RouteResult:
    status_code: int
    body: dict[str, Any]
    upstream_name: str | None
    final_status: str


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def chat_completions_url(base_url: str) -> str:
    """兼容填到域名、/v1 或完整接口三种 Base URL。"""
    normalized = base_url.strip().rstrip("/")
    if normalized.endswith("/chat/completions"):
        return normalized
    if normalized.endswith("/v1"):
        return f"{normalized}/chat/completions"
    return f"{normalized}/v1/chat/completions"


async def load_group_candidates(
    db: aiosqlite.Connection,
    route_key: str,
) -> tuple[str, int, list[Candidate]] | None:
    cur = await db.execute(
        "SELECT id, max_attempts FROM api_group "
        "WHERE route_key=? AND enabled=1",
        (route_key,),
    )
    group = await cur.fetchone()
    if group is None:
        return None

    cur = await db.execute(
        "SELECT u.id AS upstream_id, u.display_name, u.base_url, "
        "       u.encrypted_api_key, u.timeout_ms, m.upstream_model_name "
        "FROM api_group_member m "
        "JOIN upstream_endpoint u ON u.id=m.upstream_endpoint_id "
        "JOIN provider p ON p.id=u.provider_id "
        "WHERE m.group_id=? AND m.enabled=1 AND u.enabled=1 AND p.enabled=1 "
        "ORDER BY m.priority_rank ASC, m.id ASC",
        (group["id"],),
    )
    rows = await cur.fetchall()
    candidates = [
        Candidate(
            upstream_id=row["upstream_id"],
            display_name=row["display_name"],
            base_url=row["base_url"],
            encrypted_api_key=row["encrypted_api_key"],
            model=row["upstream_model_name"],
            timeout_ms=row["timeout_ms"],
        )
        for row in rows
    ]
    return group["id"], max(1, int(group["max_attempts"])), candidates


async def create_gateway_request(
    db: aiosqlite.Connection,
    request_id: str,
    route_key: str,
    started_at: str,
) -> str:
    """创建请求记录；客户端重复使用 request id 时生成新的服务端 id。"""
    actual_request_id = request_id
    for _ in range(2):
        try:
            await db.execute(
                "INSERT INTO gateway_request(request_id,route_key,started_at,attempt_count) "
                "VALUES(?,?,?,0)",
                (actual_request_id, route_key, started_at),
            )
            await db.commit()
            return actual_request_id
        except sqlite3.IntegrityError:
            await db.rollback()
            actual_request_id = uuid.uuid4().hex

    raise RuntimeError("无法生成唯一的请求 ID")


async def finish_gateway_request(
    db: aiosqlite.Connection,
    request_id: str,
    final_status: str,
    attempt_count: int,
    upstream_name: str | None = None,
) -> None:
    await db.execute(
        "UPDATE gateway_request SET ended_at=?,final_status=?,"
        "final_upstream_display=?,attempt_count=? WHERE request_id=?",
        (utc_now(), final_status, upstream_name, attempt_count, request_id),
    )
    await db.commit()


async def record_attempt(
    db: aiosqlite.Connection,
    *,
    request_id: str,
    attempt_index: int,
    candidate: Candidate,
    started_at: str,
    result_category: str,
    status_code: int | None,
    duration_ms: int,
    retryable: bool,
    sanitized_error: str | None = None,
) -> None:
    await db.execute(
        "INSERT INTO route_attempt("
        "request_id,attempt_index,upstream_endpoint_id,upstream_display_name,"
        "upstream_model_name,started_at,ended_at,result_category,"
        "upstream_status_code,duration_ms,sanitized_error,retryable) "
        "VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            request_id,
            attempt_index,
            candidate.upstream_id,
            candidate.display_name,
            candidate.model,
            started_at,
            utc_now(),
            result_category,
            status_code,
            duration_ms,
            sanitized_error,
            1 if retryable else 0,
        ),
    )
    await db.commit()


async def route_chat_completion(
    db: aiosqlite.Connection,
    *,
    request_id: str,
    route_key: str,
    payload: dict[str, Any],
) -> RouteResult:
    loaded = await load_group_candidates(db, route_key)
    if loaded is None:
        await finish_gateway_request(db, request_id, "client_error", 0)
        return RouteResult(
            status_code=404,
            body=error_envelope(404, "not_found", f"未找到已启用的 API 分组：{route_key}", request_id),
            upstream_name=None,
            final_status="client_error",
        )

    _, max_attempts, candidates = loaded
    candidates = candidates[:max_attempts]
    if not candidates:
        await finish_gateway_request(db, request_id, "all_failed", 0)
        return RouteResult(
            status_code=502,
            body=error_envelope(502, "all_upstreams_failed", "分组内没有可用上游", request_id),
            upstream_name=None,
            final_status="all_failed",
        )

    deadline = time.monotonic() + max(1, settings.request_total_timeout_seconds)
    last_category = "server_error"
    last_message = "所有候选上游均调用失败"
    attempts_made = 0

    async with httpx.AsyncClient(follow_redirects=False) as client:
        for index, candidate in enumerate(candidates, start=1):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                last_category = "timeout"
                last_message = "整次请求超过总超时时间"
                break

            attempts_made = index

            started_at = utc_now()
            started_clock = time.monotonic()
            per_endpoint = max(0.1, candidate.timeout_ms / 1000)
            timeout_seconds = min(
                remaining,
                per_endpoint,
                max(0.1, settings.upstream_timeout_seconds),
            )

            try:
                api_key = decrypt_api_key(candidate.encrypted_api_key)
            except Exception:
                last_category = "auth_error"
                last_message = f"上游 {candidate.display_name} 的 API Key 无法解密"
                await record_attempt(
                    db,
                    request_id=request_id,
                    attempt_index=index,
                    candidate=candidate,
                    started_at=started_at,
                    result_category="auth_error",
                    status_code=None,
                    duration_ms=elapsed_ms(started_clock),
                    retryable=True,
                    sanitized_error="API Key 无法解密",
                )
                continue

            try:
                response = await client.post(
                    chat_completions_url(candidate.base_url),
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                        "Accept": "application/json",
                        "X-Request-Id": request_id,
                    },
                    json={**payload, "model": candidate.model, "stream": False},
                    timeout=httpx.Timeout(timeout_seconds),
                )
            except httpx.TimeoutException:
                last_category = "timeout"
                last_message = f"上游 {candidate.display_name} 请求超时"
                await record_attempt(
                    db,
                    request_id=request_id,
                    attempt_index=index,
                    candidate=candidate,
                    started_at=started_at,
                    result_category="timeout",
                    status_code=None,
                    duration_ms=elapsed_ms(started_clock),
                    retryable=True,
                    sanitized_error="上游请求超时",
                )
                continue
            except httpx.RequestError:
                last_category = "network_error"
                last_message = f"无法连接上游 {candidate.display_name}"
                await record_attempt(
                    db,
                    request_id=request_id,
                    attempt_index=index,
                    candidate=candidate,
                    started_at=started_at,
                    result_category="network_error",
                    status_code=None,
                    duration_ms=elapsed_ms(started_clock),
                    retryable=True,
                    sanitized_error="上游连接失败",
                )
                continue

            status = response.status_code
            parsed = safe_json(response)
            if 200 <= status < 300 and parsed is not None:
                parsed = normalize_chat_completion(parsed, route_key, request_id)
                await record_attempt(
                    db,
                    request_id=request_id,
                    attempt_index=index,
                    candidate=candidate,
                    started_at=started_at,
                    result_category="success",
                    status_code=status,
                    duration_ms=elapsed_ms(started_clock),
                    retryable=False,
                )
                await finish_gateway_request(db, request_id, "success", index, candidate.display_name)
                return RouteResult(status, parsed, candidate.display_name, "success")

            if status in (400, 422) or (400 <= status < 500 and status not in (408, 429)):
                category = "auth_error" if status in (401, 403) else "client_error"
                message = upstream_message(parsed, f"上游返回不可重试的 HTTP {status}")
                await record_attempt(
                    db,
                    request_id=request_id,
                    attempt_index=index,
                    candidate=candidate,
                    started_at=started_at,
                    result_category=category,
                    status_code=status,
                    duration_ms=elapsed_ms(started_clock),
                    retryable=False,
                    sanitized_error=message,
                )
                await finish_gateway_request(db, request_id, "client_error", index, candidate.display_name)
                return RouteResult(
                    status,
                    error_envelope(status, "upstream_error", message, request_id),
                    candidate.display_name,
                    "client_error",
                )

            retry_category = "timeout" if status == 408 else (
                "rate_limited" if status == 429 else "server_error"
            )
            last_category = retry_category
            last_message = upstream_message(parsed, f"上游 {candidate.display_name} 返回 HTTP {status}")
            await record_attempt(
                db,
                request_id=request_id,
                attempt_index=index,
                candidate=candidate,
                started_at=started_at,
                result_category=retry_category,
                status_code=status,
                duration_ms=elapsed_ms(started_clock),
                retryable=True,
                sanitized_error=last_message,
            )

    timed_out = last_category == "timeout"
    final_status = "timeout" if timed_out else "all_failed"
    status_code = 504 if timed_out else 502
    error_type = "request_timeout" if timed_out else "all_upstreams_failed"
    await finish_gateway_request(db, request_id, final_status, attempts_made)
    return RouteResult(
        status_code,
        error_envelope(status_code, error_type, last_message, request_id),
        None,
        final_status,
    )


def elapsed_ms(started_clock: float) -> int:
    return max(0, round((time.monotonic() - started_clock) * 1000))


def safe_json(response: httpx.Response) -> dict[str, Any] | None:
    try:
        value = response.json()
    except (json.JSONDecodeError, ValueError):
        return None
    return value if isinstance(value, dict) else None


def upstream_message(body: dict[str, Any] | None, fallback: str) -> str:
    if body:
        error = body.get("error")
        if isinstance(error, dict) and isinstance(error.get("message"), str):
            return error["message"][:300]
    return fallback


def error_envelope(status: int, error_type: str, message: str, request_id: str) -> dict[str, Any]:
    return {
        "error": {
            "code": status,
            "type": error_type,
            "message": message,
            "requestId": request_id,
        }
    }


def normalize_chat_completion(
    payload: Any,
    model: str = "gateway-model",
    request_id: str = "gateway-request",
) -> Any:
    """Normalize successful OpenAI-compatible content for strict clients.

    Some compatible providers return ``message.content`` as an array of text
    parts or as an object. Several desktop clients only accept a string and
    call string methods while rendering, so flatten those variants here.
    Unknown response shapes are otherwise passed through unchanged.
    """
    if not isinstance(payload, dict):
        return payload

    choices = payload.get("choices")
    if not isinstance(choices, list):
        return payload

    normalized_choices: list[dict[str, Any]] = []
    for fallback_index, choice in enumerate(choices):
        if not isinstance(choice, dict):
            continue
        message = choice.get("message")
        if not isinstance(message, dict):
            continue
        index = choice.get("index", fallback_index)
        if not isinstance(index, int):
            index = fallback_index
        finish_reason = choice.get("finish_reason")
        if finish_reason is not None and not isinstance(finish_reason, str):
            finish_reason = str(finish_reason)
        normalized_choices.append({
            "index": index,
            "message": {
                "role": "assistant",
                "content": content_as_text(message.get("content")),
            },
            "finish_reason": finish_reason,
        })

    created = payload.get("created")
    if not isinstance(created, int):
        created = int(time.time())
    response_id = payload.get("id")
    if not isinstance(response_id, str) or not response_id:
        response_id = f"chatcmpl-{request_id}"

    normalized: dict[str, Any] = {
        "id": response_id,
        "object": "chat.completion",
        "created": created,
        # Return the virtual gateway model, not a provider-specific object or id.
        "model": model,
        "choices": normalized_choices,
    }
    usage = normalize_usage(payload.get("usage"))
    if usage is not None:
        normalized["usage"] = usage
    return normalized


def normalize_usage(usage: Any) -> dict[str, int] | None:
    if not isinstance(usage, dict):
        return None

    def token_count(name: str) -> int:
        value = usage.get(name, 0)
        if isinstance(value, bool):
            return 0
        if isinstance(value, (int, float)):
            return max(0, int(value))
        return 0

    prompt = token_count("prompt_tokens")
    completion = token_count("completion_tokens")
    total = token_count("total_tokens") or prompt + completion
    return {
        "prompt_tokens": prompt,
        "completion_tokens": completion,
        "total_tokens": total,
    }


def content_as_text(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                text = item.get("text", item.get("content"))
                if isinstance(text, str):
                    parts.append(text)
                elif text is not None:
                    parts.append(str(text))
        return "".join(parts)
    if isinstance(content, dict):
        text = content.get("text", content.get("content"))
        if isinstance(text, str):
            return text
        return json.dumps(content, ensure_ascii=False)
    return str(content)
