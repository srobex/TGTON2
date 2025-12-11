"""Команды Ton Connect: /connect, /wallet, /setwallet."""

from __future__ import annotations

import re

from aiogram import F, Router
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.keyboards.inline.wallet import build_wallet_keyboard
from bot.context import ton_connect
from bot.models import User
from bot.repositories import get_or_create_user, attach_wallet_data
from bot.utils.i18n import get_i18n
from bot.utils.security import issue_session_token

router = Router(name="core-wallet")
i18n = get_i18n()

# Регулярка для TON адреса (EQ... или UQ... или 0:...)
TON_ADDRESS_REGEX = re.compile(r"^(EQ|UQ)[A-Za-z0-9_-]{46}$|^0:[a-fA-F0-9]{64}$")


class WalletStates(StatesGroup):
    """FSM для ввода адреса кошелька."""
    waiting_for_address = State()


@router.message(Command("connect"))
async def command_connect(message: Message, state: FSMContext) -> None:
    """Показывает инструкцию по подключению кошелька."""
    locale = i18n.detect_locale(getattr(message.from_user, "language_code", None))
    
    # Показываем инструкцию с кнопками выбора способа
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 Ввести адрес вручную", callback_data="wallet:manual_input")],
        [InlineKeyboardButton(text="📱 Tonkeeper", url="https://tonkeeper.com/")],
        [InlineKeyboardButton(text="💎 Tonhub", url="https://tonhub.com/")],
    ])
    
    text = (
        "🔗 <b>Подключение кошелька</b>\n\n"
        "Выберите способ подключения:\n\n"
        "1️⃣ <b>Ввести адрес вручную</b> — для тестирования\n"
        "   Скопируйте адрес из вашего кошелька\n\n"
        "2️⃣ <b>Tonkeeper / Tonhub</b> — установите приложение,\n"
        "   затем используйте ручной ввод адреса\n\n"
        "💡 <i>Полная интеграция TON Connect через Mini App в разработке</i>"
    )
    await message.answer(text, reply_markup=keyboard)


@router.callback_query(F.data == "wallet:manual_input")
async def callback_manual_input(callback: CallbackQuery, state: FSMContext) -> None:
    """Запрашивает ввод адреса кошелька."""
    await state.set_state(WalletStates.waiting_for_address)
    
    text = (
        "📝 <b>Введите адрес вашего TON кошелька</b>\n\n"
        "Формат: <code>EQ...</code> или <code>UQ...</code>\n\n"
        "Где найти адрес:\n"
        "• <b>Tonkeeper</b>: Настройки → Копировать адрес\n"
        "• <b>@wallet</b>: Откройте → Нажмите на адрес сверху\n"
        "• <b>Tonhub</b>: Главная → Иконка копирования\n\n"
        "Отправьте адрес сообщением:"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="wallet:cancel_input")],
    ])
    
    if callback.message:
        await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data == "wallet:cancel_input")
async def callback_cancel_input(callback: CallbackQuery, state: FSMContext) -> None:
    """Отменяет ввод адреса."""
    await state.clear()
    if callback.message:
        await callback.message.edit_text("❌ Ввод адреса отменён.")
    await callback.answer()


@router.message(WalletStates.waiting_for_address)
async def process_wallet_address(message: Message, state: FSMContext, session: AsyncSession) -> None:
    """Обрабатывает введённый адрес кошелька."""
    address = message.text.strip() if message.text else ""
    
    # Валидация адреса
    if not TON_ADDRESS_REGEX.match(address):
        await message.answer(
            "❌ <b>Неверный формат адреса</b>\n\n"
            "TON адрес должен начинаться с <code>EQ</code> или <code>UQ</code> "
            "и содержать 48 символов.\n\n"
            "Пример: <code>EQBvW8Z5huBkMJYdnfAEM5JqTNLuuU4DW8YE...</code>\n\n"
            "Попробуйте ещё раз или нажмите /cancel для отмены."
        )
        return
    
    await state.clear()
    
    # Сохраняем кошелёк
    user = await get_or_create_user(session, message.from_user)
    await attach_wallet_data(
        session,
        user,
        wallet_address=address,
        public_key="manual_input",
        device="manual",
    )
    
    await message.answer(
        f"✅ <b>Кошелёк подключён!</b>\n\n"
        f"📍 Адрес: <code>{address[:8]}...{address[-6:]}</code>\n\n"
        f"Теперь вы можете:\n"
        f"• 💎 Искать гемы через Gem Hunter\n"
        f"• 📊 Отслеживать позиции\n"
        f"• 🔔 Получать уведомления\n\n"
        f"Используйте /wallet для просмотра статуса."
    )


@router.message(Command("setwallet"))
async def command_setwallet(message: Message, command: CommandObject, session: AsyncSession) -> None:
    """Быстрая команда для установки адреса: /setwallet EQ..."""
    address = command.args.strip() if command.args else ""
    
    if not address:
        await message.answer(
            "📝 <b>Использование:</b>\n"
            "<code>/setwallet EQB...</code>\n\n"
            "Или нажмите /connect для пошаговой инструкции."
        )
        return
    
    if not TON_ADDRESS_REGEX.match(address):
        await message.answer(
            "❌ <b>Неверный формат адреса</b>\n\n"
            "TON адрес должен начинаться с <code>EQ</code> или <code>UQ</code>."
        )
        return
    
    user = await get_or_create_user(session, message.from_user)
    await attach_wallet_data(
        session,
        user,
        wallet_address=address,
        public_key="manual_input",
        device="manual",
    )
    
    await message.answer(
        f"✅ <b>Кошелёк установлен!</b>\n\n"
        f"📍 <code>{address[:8]}...{address[-6:]}</code>"
    )


@router.message(Command("wallet"))
async def command_wallet(message: Message, session: AsyncSession) -> None:
    locale = i18n.detect_locale(getattr(message.from_user, "language_code", None))
    user = await get_or_create_user(session, message.from_user)
    text, keyboard = await _wallet_status(user, locale)
    await message.answer(text, reply_markup=keyboard)


@router.callback_query(F.data == "wallet:refresh")
async def callback_wallet_refresh(callback: CallbackQuery, session: AsyncSession) -> None:
    locale = i18n.detect_locale(getattr(callback.from_user, "language_code", None))
    user = await get_or_create_user(session, callback.from_user)
    text, keyboard = await _wallet_status(user, locale)
    if callback.message:
        await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer(i18n.gettext("wallet_refreshed", locale=locale))


@router.callback_query(F.data == "wallet:disconnect")
async def callback_wallet_disconnect(callback: CallbackQuery, session: AsyncSession) -> None:
    locale = i18n.detect_locale(getattr(callback.from_user, "language_code", None))
    user = await get_or_create_user(session, callback.from_user)
    await ton_connect.detach_wallet(user.telegram_id, session=session)
    text, keyboard = await _wallet_status(user, locale)
    if callback.message:
        await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer(i18n.gettext("wallet_disconnected", locale=locale), show_alert=True)


async def _wallet_status(user: User, locale: str) -> tuple[str, InlineKeyboardMarkup | None]:
    session = ton_connect.get_session(user.telegram_id)
    if not user.wallet_address:
        return (
            i18n.gettext("wallet_not_connected", locale=locale),
            build_wallet_keyboard(connected=False),
        )
    last_seen = (
        session.last_active.strftime("%Y-%m-%d %H:%M:%S")
        if session
        else user.updated_at.strftime("%Y-%m-%d %H:%M:%S")
    )
    text = i18n.gettext(
        "wallet_status",
        locale=locale,
        address=user.wallet_address,
        device=session.device if session else (user.device or "unknown"),
        last=last_seen,
    )
    return text, build_wallet_keyboard(connected=True)


__all__ = ["router", "command_wallet", "command_connect"]

