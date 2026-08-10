"""android_compat 查询接口契约测试。

断言服务端返回的 JSON 字段与现有 Kotlin DTO 严格一致，确保 E3/E-02 无需修改客户端即可接入：
- GET /providers              → ModelProvider + Channel
- GET /providers/{id}         → ModelProvider
- GET /providers/{id}/channels→ Channel
- GET /models                 → LlmModel（价格缺失为 null 而非 0）
- GET /news                   → PriceNews

测试直接调用路由函数（内部走 get_db() 的内存库），不依赖 HTTP 服务。
"""
from __future__ import annotations

import unittest

from app.routers import android_compat
from tests.helpers import close_test_db, open_test_db

# Kotlin data class 字段集合（data/model/ModelProvider.kt、PriceNews.kt）
MODEL_PROVIDER_FIELDS = {
    "id", "name", "logoUrl", "websiteUrl", "region",
    "channels", "apiBaseUrl", "apiKey", "chatModel", "supportsOpenAiChat",
}
CHANNEL_FIELDS = {"id", "name", "type", "link", "description"}
LLM_MODEL_FIELDS = {
    "id", "providerId", "name", "contextWindow",
    "inputPricePerMillionTokens", "outputPricePerMillionTokens",
    "currency", "tier", "priceSourceUrl", "updatedAt", "priceNote",
}
PRICE_NEWS_FIELDS = {
    "id", "providerId", "title", "summary", "type",
    "link", "validFrom", "validUntil", "createdAt",
}


class AndroidCompatContractTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.db = await open_test_db()
        await self._insert_fixtures()

    async def asyncTearDown(self) -> None:
        await close_test_db(self.db)

    async def _insert_fixtures(self) -> None:
        now = "2026-08-01T00:00:00Z"
        # 两个供应商：一个 OpenAI 兼容、一个非兼容
        await self.db.executemany(
            "INSERT INTO provider(id,name,protocol_type,official_url,pricing_url,"
            "enabled,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)",
            [
                ("alpha", "Alpha AI", "OPENAI_COMPATIBLE",
                 "https://alpha.example.com", "https://alpha.example.com/pricing", 1, now, now),
                ("beta", "Beta AI", "ANTHROPIC",
                 "https://beta.example.com", None, 1, now, now),
            ],
        )
        # 两个模型：alpha 一个有价格、一个没有价格（验证缺价返回 null 而非 0）
        await self.db.executemany(
            "INSERT INTO model_catalog_entry(id,provider_id,upstream_model_id,display_name,"
            "context_window,capabilities,enabled,source_url,verified_at) "
            "VALUES(?,?,?,?,?,?,?,?,?)",
            [
                ("model-a", "alpha", "alpha-chat", "Alpha Chat", 64000, None, 1,
                 "https://alpha.example.com/pricing", "2026-07-29"),
                ("model-b", "alpha", "alpha-other", "Alpha Other", 32000, None, 1,
                 "https://alpha.example.com/pricing", "2026-07-29"),
            ],
        )
        await self.db.execute(
            "INSERT INTO price_snapshot(id,provider_id,model_catalog_entry_id,currency,"
            "input_price_per_million_tokens,output_price_per_million_tokens,source_url,"
            "effective_from,verified_at,is_current) VALUES(?,?,?,?,?,?,?,?,?,1)",
            ("price-a", "alpha", "model-a", "CNY", 1.0, 8.0,
             "https://alpha.example.com/pricing", "2026-07-29", "2026-07-29"),
        )
        # 一条活动
        await self.db.execute(
            "INSERT INTO promotion(id,provider_id,title,type,description,source_url,"
            "starts_at,ends_at,status,verified_at,created_at) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            ("promo-alpha", "alpha", "Alpha 限时优惠", "discount",
             "演示活动", "https://alpha.example.com",
             "2026-06-01T00:00:00Z", "2026-12-31T23:59:59Z",
             "verified", "2026-07-29", now),
        )
        await self.db.commit()

    # ---------- /providers ----------

    async def test_list_providers_contract(self) -> None:
        providers = await android_compat.list_providers()
        self.assertEqual(len(providers), 2)
        by_id = {p.id: p for p in providers}
        alpha, beta = by_id["alpha"], by_id["beta"]

        # 字段集合与 ModelProvider.kt 完全一致
        self.assertEqual(set(alpha.model_dump().keys()), MODEL_PROVIDER_FIELDS)

        # 供应商字段语义
        self.assertIsNone(alpha.apiKey)  # 后端永不返回真实 Key
        self.assertIsNone(alpha.apiBaseUrl)
        self.assertTrue(alpha.supportsOpenAiChat)
        self.assertFalse(beta.supportsOpenAiChat)

        # 渠道字段与 Channel.kt 一致
        self.assertEqual(len(alpha.channels), 2)  # 官网 + 定价
        self.assertEqual(set(alpha.channels[0].model_dump().keys()), CHANNEL_FIELDS)
        # beta 只有 official_url，无 pricing_url → 仅「官网」渠道
        self.assertEqual([c.type for c in beta.channels], ["website"])

    async def test_get_provider_detail(self) -> None:
        provider = await android_compat.get_provider("alpha")
        self.assertEqual(provider.id, "alpha")
        self.assertEqual(set(provider.model_dump().keys()), MODEL_PROVIDER_FIELDS)

    async def test_get_provider_channels(self) -> None:
        channels = await android_compat.get_provider_channels("alpha")
        names = {c.name for c in channels}
        self.assertEqual(names, {"官网", "定价"})
        self.assertEqual(set(channels[0].model_dump().keys()), CHANNEL_FIELDS)

    # ---------- /models ----------

    async def test_list_models_contract(self) -> None:
        # 显式传 None，避免 FastAPI Query() 默认对象被绑进 SQL
        models = await android_compat.list_models(providerId=None)
        self.assertEqual(len(models), 2)
        by_id = {m.id: m for m in models}
        self.assertEqual(set(by_id["model-a"].model_dump().keys()), LLM_MODEL_FIELDS)

        # 有价格模型返回真实价格与币种
        priced = by_id["model-a"]
        self.assertEqual(priced.inputPricePerMillionTokens, 1.0)
        self.assertEqual(priced.outputPricePerMillionTokens, 8.0)
        self.assertEqual(priced.currency, "CNY")

        # 缺价模型返回 null 而非 0（LlmModel 可空字段语义）
        unpriced = by_id["model-b"]
        self.assertIsNone(unpriced.inputPricePerMillionTokens)
        self.assertIsNone(unpriced.outputPricePerMillionTokens)

    async def test_list_models_filter_by_provider(self) -> None:
        models = await android_compat.list_models(providerId="alpha")
        self.assertEqual(len(models), 2)
        models_beta = await android_compat.list_models(providerId="beta")
        self.assertEqual(len(models_beta), 0)

    # ---------- /news ----------

    async def test_list_news_contract(self) -> None:
        news = await android_compat.list_news(providerId=None, type=None)
        self.assertEqual(len(news), 1)
        item = news[0]
        self.assertEqual(set(item.model_dump().keys()), PRICE_NEWS_FIELDS)
        self.assertEqual(item.type, "discount")
        self.assertEqual(item.validUntil, "2026-12-31T23:59:59Z")

    async def test_list_news_filter(self) -> None:
        by_type = await android_compat.list_news(providerId=None, type="discount")
        self.assertEqual(len(by_type), 1)
        by_other = await android_compat.list_news(providerId=None, type="price_change")
        self.assertEqual(len(by_other), 0)


if __name__ == "__main__":
    unittest.main()