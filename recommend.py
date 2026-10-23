"""Deterministic budget check for normalized McDonald's MCP responses."""

from __future__ import annotations

import json
import sys
from collections import Counter
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_FLOOR
from pathlib import Path

DEFAULT_HISTORY_DAYS = 90
DEFAULT_BUDGET_MULTIPLIER = Decimal("1.25")
MIN_HISTORY_ORDERS = 3
DEFAULT_RECOMMENDATION_COUNT = 3


def _moment(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamps must include a timezone offset")
    return parsed


def analyze(data: dict) -> dict:
    as_of = _moment(data["asOf"])
    history_days = int(data.get("historyDays", DEFAULT_HISTORY_DAYS))
    multiplier = Decimal(str(data.get("budgetMultiplier", DEFAULT_BUDGET_MULTIPLIER)))
    recommendation_count = int(data.get("recommendationCount", DEFAULT_RECOMMENDATION_COUNT))
    if history_days < 1 or not multiplier.is_finite() or multiplier <= 0:
        raise ValueError("historyDays and budgetMultiplier must be positive")
    if recommendation_count < 1:
        raise ValueError("recommendationCount must be positive")
    window_start = as_of - timedelta(days=history_days)

    seen_ids: set[str] = set()
    orders: list[dict] = []
    for order in data.get("orders", []):
        order_id = str(order.get("id", "")).strip()
        if not order_id or order_id in seen_ids:
            continue
        created = _moment(order["createdAt"])
        if not window_start <= created <= as_of:
            continue
        if str(order.get("status", "")).lower() != "completed":
            continue
        paid_cents = int(order.get("paidCents", 0))
        if paid_cents <= 0:
            continue
        seen_ids.add(order_id)
        orders.append(order)

    average_cents = (
        sum(Decimal(int(order["paidCents"])) for order in orders) / len(orders)
        if orders else Decimal(0)
    )
    reliable_history = len(orders) >= MIN_HISTORY_ORDERS
    user_budget = data.get("userBudgetCents")
    if user_budget is not None and int(user_budget) <= 0:
        raise ValueError("userBudgetCents must be positive")
    ceiling = (
        int(user_budget) if user_budget is not None
        else int((average_cents * multiplier).to_integral_value(rounding=ROUND_FLOOR))
        if reliable_history else None
    )

    favorites = Counter(
        code
        for order in orders
        for code in order.get("itemCodes", [])
        if isinstance(code, str) and code.strip()
    )
    candidates = sorted(
        data.get("candidates", []),
        key=lambda item: (-int(item.get("fitScore", 0)), int(item.get("payableCents", 0))),
    )
    selected: list[dict] = []
    selected_mains: set[str] = set()
    if ceiling is not None:
        for candidate in candidates:
            main = str(candidate.get("mainCode", "")).strip()
            candidate_id = str(candidate.get("id", "")).strip()
            payable = int(candidate.get("payableCents", -1))
            if (not candidate.get("available", True) or not main or not candidate_id
                    or main in selected_mains or not 0 <= payable <= ceiling):
                continue
            selected.append(candidate)
            selected_mains.add(main)
            if len(selected) == recommendation_count:
                break

    if ceiling is None:
        note = "有效历史订单少于3笔；请让用户给出本次预算。"
    elif len(selected) < recommendation_count:
        note = f"合格套餐少于{recommendation_count}个；继续核价其他组合或优惠券，仍不足时如实说明。"
    else:
        note = f"{recommendation_count}个不同主餐的套餐均在预算内。"

    return {
        "asOf": as_of.isoformat(),
        "windowStart": window_start.isoformat(),
        "historyDays": history_days,
        "budgetMultiplier": str(multiplier),
        "recommendationCount": recommendation_count,
        "validOrderCount": len(orders),
        "averageCents": str(average_cents),
        "budgetCeilingCents": ceiling,
        "hasReliableHistory": reliable_history,
        "favoriteItems": [
            {"code": code, "count": count}
            for code, count in sorted(favorites.items(), key=lambda pair: (-pair[1], pair[0]))[:5]
        ],
        "recommendations": selected,
        "needsMoreCandidates": ceiling is not None and len(selected) < recommendation_count,
        "note": note,
    }


def self_test() -> None:
    now = "2026-10-23T12:00:00+08:00"
    data = {
        "asOf": now,
        "orders": [
            {"id": "1", "createdAt": "2026-10-20T12:00:00+08:00", "status": "completed", "paidCents": 3200},
            {"id": "2", "createdAt": "2026-09-21T12:00:00+08:00", "status": "completed", "paidCents": 4000},
            {"id": "3", "createdAt": "2026-08-01T12:00:00+08:00", "status": "completed", "paidCents": 4800},
            {"id": "3", "createdAt": "2026-08-01T12:00:00+08:00", "status": "completed", "paidCents": 4800},
            {"id": "4", "createdAt": "2026-10-18T12:00:00+08:00", "status": "canceled", "paidCents": 9000},
        ],
        "candidates": [
            {"id": "a", "mainCode": "A", "payableCents": 3900, "fitScore": 90},
            {"id": "a2", "mainCode": "A", "payableCents": 3800, "fitScore": 80},
            {"id": "b", "mainCode": "B", "payableCents": 4500, "fitScore": 80},
            {"id": "c", "mainCode": "C", "payableCents": 5000, "fitScore": 70},
            {"id": "d", "mainCode": "D", "payableCents": 5001, "fitScore": 100},
        ],
    }
    result = analyze(data)
    assert result["validOrderCount"] == 3
    assert result["averageCents"] == "4000"
    assert result["budgetCeilingCents"] == 5000
    assert [item["id"] for item in result["recommendations"]] == ["a", "b", "c"]
    assert analyze({"asOf": now, "orders": data["orders"][:2]})["budgetCeilingCents"] is None
    override = analyze({**data, "historyDays": 30, "userBudgetCents": 4600, "recommendationCount": 2})
    assert override["validOrderCount"] == 1 and override["budgetCeilingCents"] == 4600
    assert len(override["recommendations"]) == 2


if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "--self-test":
        self_test()
        print("Self-test passed.")
    elif len(sys.argv) == 2 and Path(sys.argv[1]).is_file():
        try:
            payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
            print(json.dumps(analyze(payload), ensure_ascii=False, indent=2))
        except (KeyError, ValueError, TypeError) as error:
            print(f"Invalid normalized input: {error}", file=sys.stderr)
            raise SystemExit(1) from error
    else:
        print("Usage: python src/recommend.py <normalized-input.json> | --self-test", file=sys.stderr)
        raise SystemExit(2)
