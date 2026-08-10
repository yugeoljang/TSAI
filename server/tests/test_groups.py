from __future__ import annotations

import unittest

from app.errors import GatewayError
from app.routers.groups import reorder_members
from app.schemas import ReorderRequest
from tests.helpers import close_test_db, now_iso, open_test_db, seed_group


class GroupReorderTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.db = await open_test_db()
        await seed_group(
            self.db,
            [
                {"id": "upstream-1", "base_url": "http://127.0.0.1:1/v1", "encrypted_api_key": "x"},
                {"id": "upstream-2", "base_url": "http://127.0.0.1:2/v1", "encrypted_api_key": "x"},
            ],
        )

    async def asyncTearDown(self) -> None:
        await close_test_db(self.db)

    async def test_swap_priorities_without_unique_constraint_failure(self) -> None:
        members = await reorder_members(
            "group",
            ReorderRequest(orderedMemberIds=["member-2", "member-1"]),
        )
        self.assertEqual([member.id for member in members], ["member-2", "member-1"])
        self.assertEqual([member.priorityRank for member in members], [1, 2])

    async def test_reorder_requires_all_members_exactly_once(self) -> None:
        with self.assertRaises(GatewayError) as caught:
            await reorder_members(
                "group",
                ReorderRequest(orderedMemberIds=["member-1", "member-1"]),
            )
        self.assertEqual(caught.exception.status_code, 422)


if __name__ == "__main__":
    unittest.main()
