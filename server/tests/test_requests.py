from __future__ import annotations

import unittest

from app.errors import NotFoundError
from app.routers.requests import get_request, list_attempts, list_requests
from tests.helpers import close_test_db, now_iso, open_test_db


class RequestQueryTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.db = await open_test_db()
        now = now_iso()
        await self.db.execute(
            "INSERT INTO gateway_request(request_id,route_key,started_at,ended_at,"
            "final_status,final_upstream_display,attempt_count) VALUES(?,?,?,?,?,?,?)",
            ("req-1", "demo-route", now, now, "success", "Primary", 1),
        )
        await self.db.execute(
            "INSERT INTO route_attempt(request_id,attempt_index,upstream_endpoint_id,"
            "upstream_display_name,upstream_model_name,started_at,ended_at,result_category,"
            "upstream_status_code,duration_ms,retryable) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            ("req-1", 1, "up-1", "Primary", "model", now, now, "success", 200, 12, 0),
        )
        await self.db.commit()

    async def asyncTearDown(self) -> None:
        await close_test_db(self.db)

    async def test_list_detail_and_attempts(self) -> None:
        rows = await list_requests(limit=20)
        detail = await get_request("req-1")
        attempts = await list_attempts("req-1")
        self.assertEqual(len(rows), 1)
        self.assertEqual(detail.finalUpstreamDisplayName, "Primary")
        self.assertEqual(attempts[0].resultCategory, "success")

    async def test_missing_request_is_404(self) -> None:
        with self.assertRaises(NotFoundError):
            await get_request("missing")


if __name__ == "__main__":
    unittest.main()
