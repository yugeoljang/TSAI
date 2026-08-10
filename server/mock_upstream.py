#!/usr/bin/env python3
"""Personal Gateway Plus — 模拟上游（E1）

零依赖、模拟 OpenAI 兼容供应商的"假上游"，供 B 的网关做故障切换测试。

五种可控场景（对应 B 的验收要求）：
    normal  正常回答（200 + 标准 OpenAI Chat Completion JSON）
    timeout 延迟默认 3 秒后返回 HTTP 408（用于稳定触发网关超时切换）
    429     限流（HTTP 429 + OpenAI 风格错误）
    500     服务器故障（HTTP 500 + OpenAI 风格错误）
    400     参数错误（HTTP 400 + OpenAI 风格错误，验证"不切换"）

控制方式（场景只通过控制接口切换，绝不混进 ChatCompletions 请求体）：
    PUT  /_mock/scenario   {"scenario": "timeout"}          切换场景
    GET  /_mock/scenario   读取当前场景
    （兼容别名：POST /control / GET /control）

可选：单个请求也可用查询参数临时覆盖（?scenario=429），
只对模拟服务自身生效，不会转发给真实上游，适合自动化测试。

启动：
    python mock_upstream.py             # 监听 127.0.0.1:8100
    python mock_upstream.py --selftest  # 自检五种场景并输出测试记录

环境变量：
    MOCK_HOST   监听地址（默认 127.0.0.1，同机联调/演示避免防火墙）
    MOCK_PORT   监听端口（默认 8100）
    MOCK_TIMEOUT_SECONDS  超时场景延迟秒数（默认 3）

安全说明：
    - Authorization 接受任意测试 Key，不校验、不记录完整值（日志只留掩码）
    - CORS 仅放行 http://localhost:5173（Web 管理端本地联调）
    - 模拟的是"外部真实供应商"，错误返回 OpenAI 风格
      （{"error":{"message","type","code"}}），而不是网关自身的 ErrorEnvelope。
"""

from __future__ import annotations

import json
import logging
import os
import socket
import sys
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("mock-upstream")

DEFAULT_HOST = "127.0.0.1"  # 同机联调/演示，避免局域网与防火墙问题
DEFAULT_PORT = 8100
# B 要求的超时延迟约 3 秒；需要更大可改环境变量或用 /_mock/scenario 调 timeout_seconds。
DEFAULT_TIMEOUT_SECONDS = 3

# 规范场景名 + 别名
SCENARIOS = ("normal", "timeout", "429", "500", "400")
ALIASES = {
    "ok": "normal",          # 兼容旧命名
    "reset": "normal",       # B 提到的"恢复正常状态"
    "mock/reset": "normal",
}
ALLOWED_ORIGINS = {"http://localhost:5173", "http://127.0.0.1:5173"}

# 当前场景状态（有状态），所有请求以它为准；?scenario= 查询参数可临时覆盖。
_state = {
    "scenario": "normal",
    "timeout_seconds": DEFAULT_TIMEOUT_SECONDS,
    "requests": 0,
}
_lock = threading.Lock()


def _normalize_scenario(raw: str | None) -> str | None:
    """把别名归一化为规范场景名，未知返回 None。"""
    if raw is None:
        return None
    return raw if raw in SCENARIOS else ALIASES.get(raw)


def _current_state() -> dict:
    with _lock:
        return dict(_state)


def _set_state(scenario: str | None = None, timeout_seconds: int | None = None) -> dict:
    with _lock:
        if scenario is not None:
            norm = _normalize_scenario(scenario)
            if norm is None:
                raise ValueError(f"未知场景: {scenario}，可用: {', '.join(SCENARIOS)}")
            _state["scenario"] = norm
        if timeout_seconds is not None:
            _state["timeout_seconds"] = int(timeout_seconds)
        return dict(_state)


def _resolve_scenario(path: str) -> str:
    """场景优先级：?scenario= 查询参数 > 当前默认状态。"""
    sc = parse_qs(urlparse(path).query).get("scenario", [None])[0]
    if sc is not None:
        norm = _normalize_scenario(sc)
        return norm if norm is not None else "normal"
    with _lock:
        return _state["scenario"]


def _mask_auth(auth: str | None) -> str:
    """Authorization 只留掩码，不记录完整 Key。"""
    if not auth:
        return "-"
    parts = auth.split(None, 1)
    scheme = parts[0] if parts else auth
    token = parts[1] if len(parts) > 1 else ""
    return f"{scheme} ****{token[-4:]}" if token else f"{scheme} ****"


def _last_user_content(raw_body: bytes) -> str:
    """从请求体里取出最后一条 user 消息，用于拼正常的模拟回答。"""
    try:
        data = json.loads(raw_body)
        for m in reversed(data.get("messages", []) or []):
            if isinstance(m, dict) and m.get("role") == "user" and m.get("content"):
                return str(m["content"])[:200]
    except Exception:
        pass
    return "(空问题)"


class MockHandler(BaseHTTPRequestHandler):
    server_version = "MockUpstream/1.0"

    # ---- HTTP 基础 ----
    def log_message(self, fmt, *args):  # 关掉默认日志，用下面的自定义日志
        pass

    def _send(self, status: int, payload: dict, extra_headers: dict | None = None) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self._add_cors_headers()
        for k, v in (extra_headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, html: str) -> None:
        body = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self._add_cors_headers()
        self.end_headers()
        self.wfile.write(body)

    def _add_cors_headers(self) -> None:
        origin = self.headers.get("Origin")
        if origin in ALLOWED_ORIGINS:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")

    def _read_body(self) -> bytes:
        length = int(self.headers.get("Content-Length") or 0)
        return self.rfile.read(length) if length else b""

    # ---- 方法路由 ----
    def do_OPTIONS(self) -> None:
        # CORS 预检：Web 管理端（localhost:5173）跨域调用控制接口
        origin = self.headers.get("Origin")
        if origin not in ALLOWED_ORIGINS:
            return self._send(403, _openai_error("forbidden", "CORS 来源不允许"))
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", origin)
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Access-Control-Max-Age", "600")
        self.end_headers()

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/":
            return self._html_console()
        if path == "/health":
            return self._send(200, {"status": "ok", "service": "mock-upstream"})
        if path in ("/_mock/scenario", "/control"):
            return self._send(200, _current_state())
        return self._send(404, _openai_error("not_found", f"未知路径: {path}"))

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if path == "/v1/chat/completions":
            return self._chat_completions()
        if path in ("/_mock/scenario", "/control"):
            return self._set_scenario()
        return self._send(404, _openai_error("not_found", f"未知路径: {path}"))

    def do_PUT(self) -> None:
        path = urlparse(self.path).path
        if path in ("/_mock/scenario", "/control"):
            return self._set_scenario()
        return self._send(404, _openai_error("not_found", f"未知路径: {path}"))

    # ---- 各端点实现 ----
    def _chat_completions(self) -> None:
        scenario = _resolve_scenario(self.path)
        request_id = self.headers.get("X-Request-Id") or ""
        auth = _mask_auth(self.headers.get("Authorization"))
        body = self._read_body()

        with _lock:
            _state["requests"] += 1
        log.info("[%s] POST /v1/chat/completions requestId=%s auth=%s",
                 scenario, request_id or "-", auth)

        headers = {"X-Request-Id": request_id} if request_id else {}

        if scenario == "timeout":
            # 延迟后明确返回 408，既保留“慢上游”效果，也不依赖网关默认
            # timeoutMs，保证演示在约 3 秒内稳定切换。
            time.sleep(_current_state()["timeout_seconds"])
            return self._send(
                408,
                _openai_error("request_timeout", "Upstream request timed out (simulated)."),
                headers,
            )

        if scenario == "429":
            headers["Retry-After"] = "60"
            return self._send(
                429,
                _openai_error("rate_limit_exceeded", "Rate limit reached. Please retry later."),
                headers,
            )

        if scenario == "500":
            return self._send(
                500,
                _openai_error("server_error", "Internal server error (simulated)."),
                headers,
            )

        if scenario == "400":
            # 参数错误：网关对 400/422 不切换，直接返回给调用方。
            return self._send(
                400,
                _openai_error("invalid_request_error", "Invalid parameters (simulated)."),
                headers,
            )

        # 默认 normal
        return self._send(200, _ok_payload(body), headers)

    def _set_scenario(self) -> None:
        body = self._read_body()
        try:
            data = json.loads(body) if body else {}
        except json.JSONDecodeError:
            return self._send(400, _openai_error("validation_error", "请求体不是合法 JSON"))
        try:
            state = _set_state(
                scenario=data.get("scenario"),
                timeout_seconds=data.get("timeout_seconds"),
            )
        except ValueError as e:
            return self._send(400, _openai_error("validation_error", str(e)))
        log.info("[control] 场景 -> %s（超时 %s 秒）", state["scenario"], state["timeout_seconds"])
        self._send(200, state)

    # ---- 浏览器控制台 ----
    def _html_console(self) -> None:
        self._send_html(_CONSOLE_HTML)


# ============================================================
# 响应构造
# ============================================================
def _ok_payload(raw_body: bytes) -> dict:
    data = _safe_json(raw_body) or {}
    last = _last_user_content(raw_body)
    return {
        "id": "chatcmpl-mock-" + os.urandom(6).hex(),
        "object": "chat.completion",
        "created": int(time.time()),
        "model": data.get("model") or "mock-model",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": f"[模拟上游-正常] 收到你的提问：「{last}」。",
                },
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 12, "completion_tokens": 20, "total_tokens": 32},
    }


def _openai_error(error_type: str, message: str) -> dict:
    return {"error": {"message": message, "type": error_type, "code": error_type}}


def _safe_json(raw: bytes) -> dict | None:
    try:
        return json.loads(raw)
    except Exception:
        return None


# ============================================================
# 浏览器控制台页面
# ============================================================
_CONSOLE_HTML = """<!doctype html>
<html lang="zh">
<head>
<meta charset="utf-8">
<title>模拟上游控制台</title>
<style>
  body { font-family: system-ui, sans-serif; max-width: 720px; margin: 40px auto; padding: 0 16px; color: #222; }
  h1 { font-size: 22px; }
  .state { font-size: 18px; margin: 16px 0; }
  .state b { color: #d00; }
  .btns { display: flex; gap: 10px; flex-wrap: wrap; margin: 16px 0; }
  button { font-size: 15px; padding: 10px 18px; border: 1px solid #999; border-radius: 6px; cursor: pointer; background: #fff; }
  button:hover { background: #f0f0f0; }
  button.active { background: #0a0; color: #fff; border-color: #0a0; }
  pre { background: #f6f6f6; padding: 12px; border-radius: 6px; overflow: auto; }
  .tip { color: #666; font-size: 13px; }
</style>
</head>
<body>
<h1>模拟上游控制台</h1>
<p class="state">当前状态：<b id="cur">读取中…</b></p>
<div class="btns">
  <button data-scenario="normal">正常</button>
  <button data-scenario="timeout">超时</button>
  <button data-scenario="429">限流 429</button>
  <button data-scenario="500">崩溃 500</button>
  <button data-scenario="400">参数错误 400</button>
</div>
<button id="test">发一次测试请求</button>
<p class="tip">提示：点"超时"后发测试请求会等约 3 秒才返回，这是故意模拟卡住。</p>
<pre id="result">（结果会显示在这里）</pre>

<script>
  const SCENARIO_NAMES = {normal: "正常", timeout: "超时", "429": "限流 429", "500": "崩溃 500", "400": "参数错误 400"};
  let cur = "normal";

  async function refresh() {
    const r = await fetch("/_mock/scenario");
    const s = await r.json();
    cur = s.scenario;
    document.getElementById("cur").textContent = SCENARIO_NAMES[cur] + "（超时 " + s.timeout_seconds + " 秒）";
    document.querySelectorAll("button[data-scenario]").forEach(b => {
      b.classList.toggle("active", b.dataset.scenario === cur);
    });
  }

  document.querySelectorAll("button[data-scenario]").forEach(b => {
    b.addEventListener("click", async () => {
      await fetch("/_mock/scenario", {
        method: "PUT",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({scenario: b.dataset.scenario})
      });
      refresh();
    });
  });

  document.getElementById("test").addEventListener("click", async () => {
    const pre = document.getElementById("result");
    const t0 = performance.now();
    pre.textContent = "正在请求（当前状态：" + SCENARIO_NAMES[cur] + "）…";
    try {
      const r = await fetch("/v1/chat/completions", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({model: "mock-model", messages: [{role: "user", content: "你好"}]})
      });
      const txt = await r.text();
      const ms = Math.round(performance.now() - t0);
      pre.textContent = "HTTP " + r.status + "（耗时 " + ms + " ms）\\n" + txt;
    } catch (e) {
      pre.textContent = "请求失败：" + e;
    }
  });

  refresh();
</script>
</body>
</html>
"""


# ============================================================
# 自检（--selftest）：E2 的"模拟故障可重复"测试记录
# ============================================================
def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _http_post(url: str, data: dict | None = None, timeout: float = 30) -> tuple[int, dict | None, float]:
    """POST 并返回 (状态码, JSON 或 None, 耗时秒)。非 2xx 也正常返回。"""
    t0 = time.monotonic()
    req = urllib.request.Request(
        url,
        data=json.dumps(data or {}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            try:
                body = json.loads(raw)
            except Exception:
                body = None
            return resp.status, body, time.monotonic() - t0
    except urllib.error.HTTPError as e:
        try:
            body = json.loads(e.read())
        except Exception:
            body = None
        return e.code, body, time.monotonic() - t0


def _selftest() -> int:
    log.info("自检开始：依次验证 normal / 429 / 500 / 400 / timeout 五种场景")
    server = ThreadingHTTPServer(("127.0.0.1", _free_port()), MockHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_port}"

    results: list[tuple[str, bool, str]] = []
    try:
        # 1. 正常
        status, body, _ = _http_post(f"{base}/v1/chat/completions?scenario=normal")
        results.append(
            ("normal", status == 200 and bool(body and body.get("choices")),
             f"status={status}, 含 choices={bool(body and body.get('choices'))}")
        )

        # 2. 限流 429
        status, body, _ = _http_post(f"{base}/v1/chat/completions?scenario=429")
        etype = (body or {}).get("error", {}).get("type") if body else None
        results.append(("429", status == 429, f"status={status}, type={etype}"))

        # 3. 崩溃 500
        status, body, _ = _http_post(f"{base}/v1/chat/completions?scenario=500")
        etype = (body or {}).get("error", {}).get("type") if body else None
        results.append(("500", status == 500, f"status={status}, type={etype}"))

        # 4. 参数错误 400（验证"不切换"场景）
        status, body, _ = _http_post(f"{base}/v1/chat/completions?scenario=400")
        etype = (body or {}).get("error", {}).get("type") if body else None
        results.append(("400", status == 400, f"status={status}, type={etype}"))

        # 5. 超时：先把延迟调成 1 秒，验证卡住后返回 408
        _http_post(f"{base}/_mock/scenario", {"scenario": "normal", "timeout_seconds": 1})
        status, _, elapsed = _http_post(f"{base}/v1/chat/completions?scenario=timeout", timeout=30)
        results.append(
            ("timeout", status == 408 and elapsed >= 1.0,
             f"status={status}, 耗时={elapsed:.2f}s（应为 408 且 ≥1s）")
        )
        # 恢复正常
        _http_post(f"{base}/_mock/scenario", {"scenario": "normal", "timeout_seconds": DEFAULT_TIMEOUT_SECONDS})
    finally:
        server.shutdown()
        server.server_close()

    print()
    print("模拟上游自检结果")
    print("=" * 60)
    for name, passed, detail in results:
        mark = "PASS" if passed else "FAIL"
        print(f"  {mark}  {name:<8} {detail}")
    print("=" * 60)
    passed_count = sum(1 for _, p, _ in results if p)
    print(f"  合计：{passed_count}/{len(results)} 通过")
    print()
    return 0 if passed_count == len(results) else 1


def main() -> int:
    if "--selftest" in sys.argv:
        return _selftest()

    host = os.getenv("MOCK_HOST", DEFAULT_HOST)
    port = int(os.getenv("MOCK_PORT", str(DEFAULT_PORT)))
    os.environ.setdefault("MOCK_TIMEOUT_SECONDS", str(DEFAULT_TIMEOUT_SECONDS))

    server = ThreadingHTTPServer((host, port), MockHandler)
    log.info("模拟上游已启动：http://%s:%d", host, port)
    log.info("  浏览器控制台：/   健康检查：/health   控制接口：PUT /_mock/scenario")
    log.info("  主入口：POST /v1/chat/completions（供网关转发，B 的 Base URL=http://127.0.0.1:8100/v1）")
    log.info("  当前默认场景：%s（超时 %s 秒）", _current_state()["scenario"], _current_state()["timeout_seconds"])
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log.info("已停止")
    return 0


if __name__ == "__main__":
    sys.exit(main())
