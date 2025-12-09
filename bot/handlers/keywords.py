import logging

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from bot.keyboards.menus import (
    get_cancel_keyboard,
    get_back_to_menu_keyboard,
    get_category_keyboard,
    CATEGORY_NAMES
)
from bot.models.session import session_manager
from bot.services.grok_service import grok_service

logger = logging.getLogger(__name__)
router = Router()


class KeywordsStates(StatesGroup):
    waiting_for_product_name = State()
    waiting_for_category = State()
    waiting_for_custom_category = State()
    processing = State()


@router.callback_query(F.data == "keywords")
async def start_keywords(callback: CallbackQuery, state: FSMContext):
    """Start keywords search flow"""
    await state.set_state(KeywordsStates.waiting_for_product_name)

    await callback.message.edit_text(
        "<b>Поиск ключевых слов для WB/Ozon</b>\n\n"
        "Введите название товара:\n\n"
        "<i>Например: Кроссовки мужские Nike Air Max</i>",
        reply_markup=get_cancel_keyboard()
    )
    await callback.answer()


@router.message(KeywordsStates.waiting_for_product_name, F.text)
async def receive_product_name(message: Message, state: FSMContext):
    """Receive product name"""
    product_name = message.text.strip()

    if len(product_name) < 3:
        await message.answer(
            "⚠️ Название слишком короткое. Введите полное название товара.",
            reply_markup=get_cancel_keyboard()
        )
        return

    # Save to session
    session = session_manager.get_session(message.from_user.id)
    session.product_name = product_name

    await state.set_state(KeywordsStates.waiting_for_category)

    await message.answer(
        f"<b>Товар:</b> {product_name}\n\n"
        "Выберите категорию товара или введите свою:",
        reply_markup=get_category_keyboard()
    )


@router.callback_query(KeywordsStates.waiting_for_category, F.data.startswith("cat_"))
async def receive_category_callback(callback: CallbackQuery, state: FSMContext):
    """Receive category from buttons"""
    category_key = callback.data

    if category_key == "cat_custom":
        await state.set_state(KeywordsStates.waiting_for_custom_category)
        await callback.message.edit_text(
            "Введите название категории:",
            reply_markup=get_cancel_keyboard()
        )
        await callback.answer()
        return

    category = CATEGORY_NAMES.get(category_key, "Другое")

    # Save to session and process
    session = session_manager.get_session(callback.from_user.id)
    session.category = category

    await callback.answer()
    await process_keywords(callback.message, state, callback.from_user.id)


@router.message(KeywordsStates.waiting_for_custom_category, F.text)
async def receive_custom_category(message: Message, state: FSMContext):
    """Receive custom category"""
    category = message.text.strip()

    session = session_manager.get_session(message.from_user.id)
    session.category = category

    await process_keywords(message, state, message.from_user.id)


async def process_keywords(message: Message, state: FSMContext, user_id: int):
    """Process keywords search"""
    await state.set_state(KeywordsStates.processing)

    session = session_manager.get_session(user_id)

    # Send processing message
    processing_msg = await message.answer(
        f"🔍 Ищу ключевые слова...\n\n"
        f"<b>Товар:</b> {session.product_name}\n"
        f"<b>Категория:</b> {session.category}\n\n"
        "Это может занять несколько секунд..."
    )

    try:
        # Get keywords from Grok
        keywords_data = await grok_service.analyze_keywords(
            session.product_name,
            session.category
        )

        if keywords_data:
            session.keywords = keywords_data

            # Format response
            response = session.format_keywords_message()

            await processing_msg.edit_text(
                response,
                reply_markup=get_back_to_menu_keyboard()
            )
        else:
            await processing_msg.edit_text(
                "❌ Не удалось найти ключевые слова.\n"
                "Попробуйте уточнить название товара.",
                reply_markup=get_back_to_menu_keyboard()
            )

    except Exception as e:
        logger.error(f"Error getting keywords: {e}")
        await processing_msg.edit_text(
            "❌ Произошла ошибка при поиске.\n"
            "Попробуйте позже.",
            reply_markup=get_back_to_menu_keyboard()
        )

    await state.clear()


@router.message(KeywordsStates.waiting_for_product_name)
async def invalid_product_name(message: Message):
    """Handle non-text input"""
    await message.answer(
        "⚠️ Пожалуйста, введите название товара текстом.",
        reply_markup=get_cancel_keyboard()
    )
