"""android_compat 分组路由契约测试（E-04）。

断言服务端返回的 JSON 字段与 E3 新增的 Kotlin DTO 严格兼容：
- GET /api/admin/groups              → ChatGroup.kt
- GET /api/admin/requests/{id}/attempts → RouteAttempt.kt

契约要点：
- ChatGroup.kt 只声明了 ApiGroup 的子集（id/name/routeKey/routingPolicy/maxAttempts/enabled），
  服务端额外返回 createdAt/updatedAt，由 Android 的 ignoreUnknownKeys 忽略。
- RouteAttempt.kt 与服务端 RouteAttempt 字段一一对应（含可空字段语义）。

测试直接调用路由函数（内部走 database._db 内存库），不依赖 HTTP 服务。
"""
from __future__ import annotations

import unittest

from app.routers.groups import list_groups
from app.routers.requests import list_attempts
from tests.helpers import close_test_db, now_iso, open_test_db, seed_group

# Kotlin data class 字段集合（data/model/ChatGroup.kt，不含被忽略的服务端扩展字段）
CHAT_GROUP_FIELDS = {
    "id", "name", "routeKey", "routingPolicy", "maxAttempts", "enabled",
}
# Kotlin data class 字段集合（data/model/RouteAttempt.kt）
ROUTE_ATTEMPT_FIELDS = {
    "requestId", "attemptIndex", "upstreamEndpointId", "upstreamDisplayName",
    "upstreamModelName", "startedAt", "endedAt", "resultCategory",
    "upstreamStatusCode", "durationMs", "sanitizedError", "retryable",
}


class AndroidCompatGroupRouteContractTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.db = await open_test_db()
        await seed_group(
            self.db,
            [
                {"id": "upstream-1", "name": "mock-fail",
                 "base_url": "http://127.0.0.1:8100/v1", "encrypted_api_key": "x"},
                {"id": "upstream-2", "name": "mock-ok",
                 "base_url": "http://127.0.0.1:8101/v1", "encrypted_api_key": "x"},
            ],
            route_key="demo",
            max_attempts=3,
        )
        await self._seed_route_request()

    async def asyncTearDown(self) -> None:
        await close_test_db(self.db)

    async def _seed_route_request(self) -> None:
        """插入一次故障切换请求：attempt1=500，attempt2=200。"""
        now = now_iso()
        await self.db.execute(
            "INSERT INTO gateway_request(request_id,route_key,started_at,ended_at,"
            "final_status,final_upstream_display,attempt_count) "
            "VALUES(?,?,?,?,?,?,?)",
            ("req-route-1", "demo", now, now, "success", "mock-ok", 2),
        )
        await self.db.executemany(
            "INSERT INTO route_attempt(request_id,attempt_index,upstream_endpoint_id,"
            "upstream_display_name,upstream_model_name,started_at,ended_at,"
            "result_category,upstream_status_code,duration_ms,sanitized_error,retryable) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
            [
                ("req-route-1", 1, "upstream-1", "mock-fail", "mock-model", now, now,
                 "server_error", 500, 8, "Internal server error (simulated).", 1),
                ("req-route-1", 2, "upstream-2", "mock-ok", "mock-model", now, now,
                 "success", 200, 6, None, 0),
            ],
        )
        await self.db.commit()

    # ---------- /api/admin/groups ----------

    async def test_list_groups_contract(self) -> None:
        groups = await list_groups()
        self.assertEqual(len(groups), 1)
        group = groups[0]

        # 服务端必须提供 ChatGroup.kt 声明的全部字段（superset，可含被忽略的扩展字段）
        self.assertTrue(CHAT_GROUP_FIELDS <= set(group.model_dump().keys()))

        # 语义：默认值在服务端侧兜底，与 Kotlin 默认值一致
        self.assertEqual(group.routeKey, "demo")
        self.assertEqual(group.routingPolicy, "ORDERED_FAILOVER")
        self.assertEqual(group.maxAttempts, 3)
        self.assertTrue(group.enabled)

    # ---------- /api/admin/requests/{id}/attempts ----------

    async def test_list_attempts_contract(self) -> None:
        attempts = await list_attempts("req-route-1")
        self.assertEqual(len(attempts), 2)

        # 字段集合与 RouteAttempt.kt 一一对应
        self.assertEqual(
            set(attempts[0].model_dump().keys()),
            ROUTE_ATTEMPT_FIELDS,
        )

        # 故障切换语义：attempt1 失败可重试，attempt2 成功不可重试
        first, second = attempts
        self.assertEqual(first.attemptIndex, 1)
        self.assertEqual(first.upstreamDisplayName, "mock-fail")
        self.assertEqual(first.resultCategory, "server_error")
        self.assertEqual(first.upstreamStatusCode, 500)
        self.assertTrue(first.retryable)
        self.assertEqual(first.sanitizedError, "Internal server error (simulated).")

        self.assertEqual(second.attemptIndex, 2)
        self.assertEqual(second.upstreamDisplayName, "mock-ok")
        self.assertEqual(second.resultCategory, "success")
        self.assertEqual(second.upstreamStatusCode, 200)
        self.assertFalse(second.retryable)
        self.assertIsNone(second.sanitizedError)

    async def test_list_attempts_order_and_retryable_null_semantics(self) -> None:
        # 第二个 attempt 的 succeeded 结果 retryable 必须为 False（Kotlin 默认值兜底）
        attempts = await list_attempts("req-route-1")
        self.assertEqual([a.attemptIndex for a in attempts], [1, 2])
        self.assertIs(attempts[1].retryable, False)


if __name__ == "__main__":
    unittest.main()