PLANS = {
    "lifetime": {"label": "Lifetime", "price_usd": 29, "mode": "payment", "pages": 1, "monitors": 10,
                 "price_env": "STRIPE_PRICE_LIFETIME"},
    "hosted": {"label": "Hosted", "price_usd": 5, "mode": "subscription", "pages": 1, "monitors": 10,
               "price_env": "STRIPE_PRICE_MONTHLY"},
}


def can_add_monitor(plan: str, current_count: int) -> bool:
    return plan in PLANS and current_count < PLANS[plan]["monitors"]
