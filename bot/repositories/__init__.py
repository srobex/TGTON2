"""Репозитории для работы с БД."""

from .user_repo import (
    attach_wallet_data,
    clear_wallet_data,
    get_or_create_user,
    ensure_user_by_telegram_id,
    get_user_by_ref_code,
    get_user_by_telegram,
    get_user_by_wallet,
)
from .position_repo import (
    get_positions_by_jetton,
    list_rules_for_wallet,
    load_active_rules,
    mark_rule_status,
    update_pnl,
    upsert_rule,
)
from .gem_cache_repo import upsert_gem_cache

__all__ = [
    "attach_wallet_data",
    "clear_wallet_data",
    "ensure_user_by_telegram_id",
    "get_or_create_user",
    "get_user_by_ref_code",
    "get_user_by_telegram",
    "get_user_by_wallet",
    "get_positions_by_jetton",
    "list_rules_for_wallet",
    "load_active_rules",
    "mark_rule_status",
    "update_pnl",
    "upsert_gem_cache",
    "upsert_rule",
]

