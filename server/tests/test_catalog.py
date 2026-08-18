from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from pydantic import ValidationError

from app.errors import ConflictError, GatewayError
from app.routers.catalog import (
    create_model,
    create_price,
    create_promotion,
    delete_price,
    list_models,
    list_prices,
    list_promotions,
    price_history,
    update_promotion,
)
from app.schemas import (
    ModelCatalogCreate,
    PriceSnapshotCreate,
    PromotionCreate,
    PromotionUpdate,
)
from tests.helpers import close_test_db, now_iso, open_test_db


def iso(offset_days: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(days=offset_days)).strftime("%Y-%m-%dT%H:%M:%SZ")


class CatalogTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.db = await open_test_db()
        now = now_iso()
        await self.db.execute(
            "INSERT INTO provider(id,name,protocol_type,enabled,created_at,updated_at) "
            "VALUES('provider','Test','OPENAI_COMPATIBLE',1,?,?)",
            (now, now),
        )
        await self.db.commit()

    async def asyncTearDown(self) -> None:
        await close_test_db(self.db)

    async def create_test_model(self):
        return await create_model(
            ModelCatalogCreate(
                providerId="provider",
                upstreamModelId="test-model",
                displayName="Test Model",
                contextWindow=128000,
                sourceUrl="https://example.com/pricing",
                verifiedAt=iso(0),
            )
        )

    async def test_model_crud_and_duplicate_guard(self) -> None:
        model = await self.create_test_model()
        self.assertEqual(model.providerId, "provider")
        self.assertEqual(len(await list_models()), 1)
        with self.assertRaises(ConflictError):
            await self.create_test_model()

    async def test_price_creation_keeps_history_and_one_current(self) -> None:
        model = await self.create_test_model()
        first = await create_price(
            PriceSnapshotCreate(
                modelCatalogEntryId=model.id,
                currency="cny",
                inputPricePerMillionTokens=1,
                outputPricePerMillionTokens=2,
                sourceUrl="https://example.com/pricing",
                effectiveFrom=iso(-2),
                verifiedAt=iso(-2),
            )
        )
        second = await create_price(
            PriceSnapshotCreate(
                modelCatalogEntryId=model.id,
                currency="CNY",
                inputPricePerMillionTokens=3,
                outputPricePerMillionTokens=4,
                sourceUrl="https://example.com/pricing",
                effectiveFrom=iso(-1),
                verifiedAt=iso(-1),
            )
        )
        current = await list_prices()
        history = await price_history(model.id)
        self.assertEqual([item.id for item in current], [second.id])
        self.assertEqual(len(history), 2)
        self.assertTrue(history[0].isCurrent)
        self.assertFalse(history[1].isCurrent)
        self.assertEqual(first.currency, "CNY")

    async def test_deleting_current_price_restores_previous_snapshot(self) -> None:
        model = await self.create_test_model()
        first = await create_price(
            PriceSnapshotCreate(
                modelCatalogEntryId=model.id,
                inputPricePerMillionTokens=1,
                sourceUrl="https://example.com/pricing",
                effectiveFrom=iso(-2),
                verifiedAt=iso(-2),
            )
        )
        second = await create_price(
            PriceSnapshotCreate(
                modelCatalogEntryId=model.id,
                outputPricePerMillionTokens=5,
                sourceUrl="https://example.com/pricing",
                effectiveFrom=iso(-1),
                verifiedAt=iso(-1),
            )
        )
        await delete_price(second.id)
        current = await list_prices()
        self.assertEqual(current[0].id, first.id)

    def test_price_requires_at_least_one_value(self) -> None:
        with self.assertRaises(ValidationError):
            PriceSnapshotCreate(
                modelCatalogEntryId="model",
                sourceUrl="https://example.com/pricing",
                effectiveFrom=iso(0),
                verifiedAt=iso(0),
            )

    async def test_promotion_has_four_lifecycle_states(self) -> None:
        base = dict(
            providerId="provider",
            type="discount",
            description="test",
            sourceUrl="https://example.com/promo",
            verifiedAt=iso(0),
        )
        await create_promotion(PromotionCreate(title="Active", startsAt=iso(-1), endsAt=iso(1), status="verified", **base))
        await create_promotion(PromotionCreate(title="Upcoming", startsAt=iso(1), endsAt=iso(2), status="verified", **base))
        await create_promotion(PromotionCreate(title="Expired", startsAt=iso(-2), endsAt=iso(-1), status="verified", **base))
        await create_promotion(PromotionCreate(providerId="provider", title="Draft", type="credit", status="draft"))
        states = {item.title: item.lifecycleStatus for item in await list_promotions()}
        self.assertEqual(states, {"Active": "active", "Upcoming": "upcoming", "Expired": "expired", "Draft": "draft"})
        self.assertEqual([item.title for item in await list_promotions(activeOnly=True)], ["Active"])

    async def test_verified_promotion_requires_source_and_dates(self) -> None:
        with self.assertRaises(GatewayError):
            await create_promotion(
                PromotionCreate(providerId="provider", title="Invalid", type="credit", status="verified")
            )

    async def test_update_validates_combined_promotion_state(self) -> None:
        promo = await create_promotion(
            PromotionCreate(providerId="provider", title="Draft", type="credit", status="draft")
        )
        with self.assertRaises(GatewayError):
            await update_promotion(promo.id, PromotionUpdate(status="verified"))


if __name__ == "__main__":
    unittest.main()
