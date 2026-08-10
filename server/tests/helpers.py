from __future__ import annotations

from datetime import datetime, timezone

import aiosqlite

from app import database
from app.config import BASE_DIR


async def open_test_db() -> aiosqlite.Connection:
    db = await aiosqlite.connect(":memory:")
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA foreign_keys = ON")
    schema = (BASE_DIR / "app" / "schema.sql").read_text(encoding="utf-8")
    await db.executescript(schema)
    await db.commit()
    database._db = db
    return db


async def close_test_db(db: aiosqlite.Connection) -> None:
    await db.close()
    database._db = None


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


async def seed_group(
    db: aiosqlite.Connection,
    upstreams: list[dict],
    *,
    route_key: str = "demo-route",
    max_attempts: int = 3,
) -> None:
    now = now_iso()
    await db.execute(
        "INSERT INTO provider(id,name,protocol_type,enabled,created_at,updated_at) "
        "VALUES('provider','Test','OPENAI_COMPATIBLE',1,?,?)",
        (now, now),
    )
    await db.execute(
        "INSERT INTO api_group(id,name,route_key,routing_policy,max_attempts,enabled,created_at,updated_at) "
        "VALUES('group','Test Group',?,'ORDERED_FAILOVER',?,1,?,?)",
        (route_key, max_attempts, now, now),
    )
    for index, upstream in enumerate(upstreams, start=1):
        upstream_id = upstream.get("id", f"upstream-{index}")
        await db.execute(
            "INSERT INTO upstream_endpoint(id,provider_id,display_name,base_url,encrypted_api_key,"
            "api_key_last_four,default_model,enabled,timeout_ms,created_at,updated_at) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (
                upstream_id,
                "provider",
                upstream.get("name", upstream_id),
                upstream["base_url"],
                upstream["encrypted_api_key"],
                "test",
                upstream.get("model", f"model-{index}"),
                1,
                upstream.get("timeout_ms", 2000),
                now,
                now,
            ),
        )
        await db.execute(
            "INSERT INTO api_group_member(id,group_id,upstream_endpoint_id,upstream_model_name,"
            "priority_rank,enabled,created_at) VALUES(?,?,?,?,?,1,?)",
            (
                f"member-{index}",
                "group",
                upstream_id,
                upstream.get("model", f"model-{index}"),
                index,
                now,
            ),
        )
    await db.commit()
