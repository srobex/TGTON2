"""Хендлеры Alpha Scanner / Gem Hunter."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.filters.command import CommandObject
from aiogram.types import CallbackQuery, Message
from aiogram.exceptions import TelegramBadRequest

from bot.keyboards.inline.gem import build_gem_list_keyboard, build_token_keyboard
from bot.context import gem_scanner, gem_watch_service, swap_service, ton_connect
from bot.utils.i18n import get_i18n

router = Router(name="ton-gem-hunter")
i18n = get_i18n()
DEFAULT_BUY_AMOUNT_TON = 1.0


@router.message(Command("gemhunter"))
@router.message(Command("gem"))
async def command_gemhunter(message: Message) -> None:
    locale = i18n.detect_locale(getattr(message.from_user, "language_code", None))
    text = await _render_top(locale)
    await message.answer(text, reply_markup=build_gem_list_keyboard())


@router.callback_query(F.data == "gem:refresh")
async def callback_refresh(callback: CallbackQuery) -> None:
    locale = i18n.detect_locale(getattr(callback.from_user, "language_code", None))
    text = await _render_top(locale)
    keyboard = build_gem_list_keyboard()
    if callback.message:
        try:
            await callback.message.edit_text(text, reply_markup=keyboard)
        except TelegramBadRequest as exc:
            # Telegram не позволяет редактировать сообщение, если контент не изменился.
            if "message is not modified" not in (exc.message or ""):
                raise
    await callback.answer(i18n.gettext("gem_refreshed", locale=locale))


@router.callback_query(F.data.startswith("gem:safety:"))
async def callback_safety(callback: CallbackQuery) -> None:
    locale = i18n.detect_locale(getattr(callback.from_user, "language_code", None))
    token_address = callback.data.split(":", maxsplit=2)[2]
    signal = await _find_signal(token_address)
    if not signal:
        await callback.answer(i18n.gettext("gem_not_found", locale=locale), show_alert=True)
        return
    report = signal.report
    text = i18n.gettext(
        "gem_safety_report",
        locale=locale,
        token=token_address,
        score=f"{report.score:.1f}",
        liquidity=f"{report.liquidity_usd:,.0f}",
        volume=f"{report.volume_5m_usd:,.0f}",
        smart=report.smart_money_hits,
        lp="Да" if report.lp_burned else "Нет",
        is_new="Да" if report.is_new else "Нет",
    )
    await callback.message.answer(text, reply_markup=build_token_keyboard(token_address))
    await callback.answer()


@router.callback_query(F.data.startswith("gem:buy:"))
async def callback_buy(callback: CallbackQuery) -> None:
    locale = i18n.detect_locale(getattr(callback.from_user, "language_code", None))
    user_id = callback.from_user.id
    session = ton_connect.get_session(user_id)
    if session is None:
        link = ton_connect.create_connection_url(user_id)
        await callback.answer(
            i18n.gettext("gem_connect_wallet", locale=locale),
            show_alert=True,
        )
        if callback.message:
            await callback.message.answer(
                i18n.gettext("gem_connect_instructions", locale=locale, link=link)
            )
        return
    token_address = callback.data.split(":", maxsplit=2)[2]
    try:
        quote = await swap_service.prepare_buy(
            wallet=session.wallet_address,
            jetton=token_address,
            amount_ton=DEFAULT_BUY_AMOUNT_TON,
            slippage_percent=5.0,
        )
    except Exception as exc:  # noqa: BLE001
        await callback.answer(i18n.gettext("gem_buy_failed", locale=locale), show_alert=True)
        return
    text = i18n.gettext(
        "gem_buy_quote",
        locale=locale,
        token=token_address,
        amount=DEFAULT_BUY_AMOUNT_TON,
        est=f"{quote.estimated_receive:.4f}",
        min_receive=f"{quote.min_receive:.4f}",
        fee=quote.fee_nano,
        payload=quote.tx_boc,
    )
    await callback.message.answer(text, reply_markup=build_token_keyboard(token_address))
    await callback.answer(i18n.gettext("gem_buy_ready", locale=locale))


@router.callback_query(F.data.startswith("gem:watch:"))
async def callback_watch(callback: CallbackQuery) -> None:
    locale = i18n.detect_locale(getattr(callback.from_user, "language_code", None))
    token_address = callback.data.split(":", maxsplit=2)[2]
    state = await gem_watch_service.toggle_watch(callback.from_user.id, token_address)
    key = "gem_watch_on" if state else "gem_watch_off"
    await callback.answer(i18n.gettext(key, locale=locale), show_alert=state)


@router.callback_query(F.data.startswith("gem:tp:"))
async def callback_tp_hint(callback: CallbackQuery) -> None:
    locale = i18n.detect_locale(getattr(callback.from_user, "language_code", None))
    await callback.answer(i18n.gettext("gem_tp_hint", locale=locale), show_alert=True)


@router.callback_query(F.data.startswith("gem:ar:"))
async def callback_ar_hint(callback: CallbackQuery) -> None:
    locale = i18n.detect_locale(getattr(callback.from_user, "language_code", None))
    await callback.answer(i18n.gettext("gem_ar_hint", locale=locale), show_alert=True)


@router.callback_query(F.data == "gem:filters")
async def callback_filters(callback: CallbackQuery) -> None:
    locale = i18n.detect_locale(getattr(callback.from_user, "language_code", None))
    filters = gem_scanner.get_filters()
    text = i18n.gettext(
        "gem_filters_current",
        locale=locale,
        score=filters["min_score"],
        lp="Да" if filters["lp_burned_only"] else "Нет",
        smart=filters["smart_money_min"],
        sort=filters["sort_key"],
    )
    if callback.message:
        await callback.message.answer(text)
    await callback.answer()


@router.message(Command("gemfilters"))
async def command_gemfilters(message: Message, command: CommandObject) -> None:
    locale = i18n.detect_locale(getattr(message.from_user, "language_code", None))
    args = (command.args or "").strip()
    current = gem_scanner.get_filters()
    if not args:
        await message.answer(
            i18n.gettext(
                "gem_filters_usage",
                locale=locale,
                score=current["min_score"],
                lp="Да" if current["lp_burned_only"] else "Нет",
                smart=current["smart_money_min"],
                sort=current["sort_key"],
            )
        )
        return
    params: dict[str, str] = {}
    for part in args.split():
        if "=" in part:
            key, value = part.split("=", maxsplit=1)
            params[key.lower()] = value
    try:
        min_score = float(params.get("score", current["min_score"]))
        smart_money = int(params.get("smart", current["smart_money_min"]))
    except ValueError:
        await message.answer(i18n.gettext("gem_filters_invalid", locale=locale))
        return
    lp_flag = params.get("lp", str(int(current["lp_burned_only"]))).lower()
    lp_only = lp_flag in {"1", "true", "да", "on"}
    sort_key = params.get("sort", current["sort_key"]).lower()
    gem_scanner.set_filters(
        min_score=min_score,
        lp_burned_only=lp_only,
        smart_money_min=smart_money,
        sort_key=sort_key,
    )
    await message.answer(
        i18n.gettext(
            "gem_filters_updated",
            locale=locale,
            score=min_score,
            lp="Да" if lp_only else "Нет",
            smart=smart_money,
            sort=sort_key,
        )
    )


@router.callback_query(F.data.startswith("gem:pin:"))
async def callback_pin(callback: CallbackQuery) -> None:
    locale = i18n.detect_locale(getattr(callback.from_user, "language_code", None))
    token_address = callback.data.split(":", maxsplit=2)[2]
    signal = await _find_signal(token_address)
    if signal is None:
        await callback.answer(i18n.gettext("gem_not_found", locale=locale), show_alert=True)
        return
    text = i18n.gettext(
        "gem_pin_message",
        locale=locale,
        token=token_address,
        score=f"{signal.score:.1f}",
        tags=", ".join(signal.tags) if signal.tags else i18n.gettext("tag_unknown", locale=locale),
    )
    await callback.message.answer(text, reply_markup=build_token_keyboard(token_address))
    await callback.answer()


@router.message(Command("gemfeed_on"))
async def command_gemfeed_on(message: Message) -> None:
    locale = i18n.detect_locale(getattr(message.from_user, "language_code", None))
    added = await gem_watch_service.subscribe_global(message.from_user.id)
    key = "gem_feed_on" if added else "gem_feed_already_on"
    await message.answer(i18n.gettext(key, locale=locale))


@router.message(Command("gemfeed_off"))
async def command_gemfeed_off(message: Message) -> None:
    locale = i18n.detect_locale(getattr(message.from_user, "language_code", None))
    removed = await gem_watch_service.unsubscribe_global(message.from_user.id)
    key = "gem_feed_off" if removed else "gem_feed_already_off"
    await message.answer(i18n.gettext(key, locale=locale))


async def _render_top(locale: str) -> str:
    tokens = await gem_scanner.get_top()
    if not tokens:
        return i18n.gettext("hot_empty", locale=locale)
    lines = []
    for idx, token in enumerate(tokens, start=1):
        tags = ", ".join(token.tags) if token.tags else i18n.gettext("tag_unknown", locale=locale)
        lines.append(
            i18n.gettext(
                "hot_line",
                locale=locale,
                idx=idx,
                symbol=token.symbol or token.address[-6:],
                score=f"{token.score:.1f}",
                tags=tags,
            )
        )
    return "\n".join(lines)


async def _find_signal(address: str):
    tokens = await gem_scanner.get_top(limit=10)
    for token in tokens:
        if token.address == address:
            return token
    return None


__all__ = ["router"]

