from __future__ import annotations

import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from app.config import settings
from app.security import encrypt_api_key
from app.services.gateway_service import (
    chat_completions_url,
    create_gateway_request,
    route_chat_completion,
    utc_now,
)
from tests.helpers import close_test_db, open_test_db, seed_group


class _Server:
    def __init__(self, status: int, content: str) -> None:
        state = {"hits": 0}

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_args):
                pass

            def do_POST(self):
                state["hits"] += 1
                length = int(self.headers.get("Content-Length", "0"))
                raw = self.rfile.read(length)
                request_body = json.loads(raw)
                body = (
                    {"error": {"message": content}}
                    if status >= 400
                    else {
                        "id": "chatcmpl-test",
                        "object": "chat.completion",
                        "choices": [{
                            "index": 0,
                            "message": {"role": "assistant", "content": content},
                            "finish_reason": "stop",
                        }],
                        "received_model": request_body.get("model"),
                    }
                )
                encoded = json.dumps(body).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(encoded)))
                self.end_headers()
                self.wfile.write(encoded)

        self._state = state
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    @property
    def hits(self) -> int:
        return self._state["hits"]

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.server.server_port}/v1"

    def close(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)


class GatewayTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.original_key = settings.master_key_hex
        settings.master_key_hex = "11" * 32
        self.db = await open_test_db()
        self.servers: list[_Server] = []

    async def asyncTearDown(self) -> None:
        for server in self.servers:
            server.close()
        await close_test_db(self.db)
        settings.master_key_hex = self.original_key

    def server(self, status: int, content: str) -> _Server:
        server = _Server(status, content)
        self.servers.append(server)
        return server

    async def test_500_switches_to_second_upstream_and_persists_attempts(self) -> None:
        first = self.server(500, "first failed")
        second = self.server(200, "backup answer")
        encrypted = encrypt_api_key("sk-test")
        await seed_group(self.db, [
            {"base_url": first.base_url, "encrypted_api_key": encrypted, "model": "model-a"},
            {"base_url": second.base_url, "encrypted_api_key": encrypted, "model": "model-b"},
        ])
        await create_gateway_request(self.db, "request-1", "demo-route", utc_now())

        result = await route_chat_completion(
            self.db,
            request_id="request-1",
            route_key="demo-route",
            payload={"model": "demo-route", "messages": [{"role": "user", "content": "hello"}]},
        )

        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.upstream_name, "upstream-2")
        self.assertEqual(first.hits, 1)
        self.assertEqual(second.hits, 1)
        cur = await self.db.execute(
            "SELECT result_category FROM route_attempt WHERE request_id=? ORDER BY attempt_index",
            ("request-1",),
        )
        self.assertEqual([row[0] for row in await cur.fetchall()], ["server_error", "success"])

    async def test_400_does_not_call_backup(self) -> None:
        first = self.server(400, "invalid request")
        second = self.server(200, "must not run")
        encrypted = encrypt_api_key("sk-test")
        await seed_group(self.db, [
            {"base_url": first.base_url, "encrypted_api_key": encrypted},
            {"base_url": second.base_url, "encrypted_api_key": encrypted},
        ])
        await create_gateway_request(self.db, "request-2", "demo-route", utc_now())

        result = await route_chat_completion(
            self.db,
            request_id="request-2",
            route_key="demo-route",
            payload={"model": "demo-route", "messages": [{"role": "user", "content": "hello"}]},
        )

        self.assertEqual(result.status_code, 400)
        self.assertEqual(first.hits, 1)
        self.assertEqual(second.hits, 0)

    async def test_duplicate_client_request_id_gets_a_new_id(self) -> None:
        first_id = await create_gateway_request(
            self.db, "duplicate-id", "demo-route", utc_now()
        )
        second_id = await create_gateway_request(
            self.db, "duplicate-id", "demo-route", utc_now()
        )

        self.assertEqual(first_id, "duplicate-id")
        self.assertNotEqual(second_id, first_id)
        cur = await self.db.execute("SELECT COUNT(*) FROM gateway_request")
        self.assertEqual((await cur.fetchone())[0], 2)

    def test_chat_url_accepts_domain_v1_and_full_path(self) -> None:
        self.assertEqual(
            chat_completions_url("https://example.com"),
            "https://example.com/v1/chat/completions",
        )
        self.assertEqual(
            chat_completions_url("https://example.com/v1/"),
            "https://example.com/v1/chat/completions",
        )
        self.assertEqual(
            chat_completions_url("https://example.com/v1/chat/completions"),
            "https://example.com/v1/chat/completions",
        )


if __name__ == "__main__":
    unittest.main()
