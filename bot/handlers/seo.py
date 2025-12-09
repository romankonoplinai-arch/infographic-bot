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


class SEOStates(StatesGroup):
    waiting_for_product_name = State()
    waiting_for_category = State()
    waiting_for_custom_category = State()
    processing = State()


@router.callback_query(F.data == "seo")
async def start_seo(callback: CallbackQuery, state: FSMContext):
    """Start SEO generation flow"""
    session = session_manager.get_session(callback.from_user.id)

    # Check if we already have product info from previous steps
    if session.product_name and session.category:
        await callback.message.edit_text(
            f"<b>Создание SEO-описания</b>\n\n"
            f"<b>Товар:</b> {session.product_name}\n"
            f"<b>Категория:</b> {session.category}\n\n"
            "Использовать эти данные или ввести новые?",
            reply_markup=get_use_existing_keyboard()
        )
        await callback.answer()
        return

    await state.set_state(SEOStates.waiting_for_product_name)

    await callback.message.edit_text(
        "<b>Создание SEO-описания для WB/Ozon</b>\n\n"
        "Введите название товара:\n\n"
        "<i>Например: Куртка женская зимняя с капюшоном</i>",
        reply_markup=get_cancel_keyboard()
    )
    await callback.answer()


def get_use_existing_keyboard():
    """Keyboard for using existing data"""
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Использовать", callback_data="seo_use_existing")
    )
    builder.row(
        InlineKeyboardButton(text="📝 Ввести новые", callback_data="seo_new_data")
    )
    builder.row(
        InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")
    )
    return builder.as_markup()


@router.callback_query(F.data == "seo_use_existing")
async def use_existing_data(callback: CallbackQuery, state: FSMContext):
    """Use existing product data for SEO"""
    await callback.answer()
    await process_seo(callback.message, state, callback.from_user.id)


@router.callback_query(F.data == "seo_new_data")
async def enter_new_data(callback: CallbackQuery, state: FSMContext):
    """Enter new product data"""
    session_manager.reset_session(callback.from_user.id)
    await state.set_state(SEOStates.waiting_for_product_name)

    await callback.message.edit_text(
        "<b>Создание SEO-описания</b>\n\n"
        "Введите название товара:",
        reply_markup=get_cancel_keyboard()
    )
    await callback.answer()


@router.message(SEOStates.waiting_for_product_name, F.text)
async def receive_product_name(message: Message, state: FSMContext):
    """Receive product name"""
    product_name = message.text.strip()

    if len(product_name) < 3:
        await message.answer(
            "⚠️ Название слишком короткое.",
            reply_markup=get_cancel_keyboard()
        )
        return

    session = session_manager.get_session(message.from_user.id)
    session.product_name = product_name

    await state.set_state(SEOStates.waiting_for_category)

    await message.answer(
        f"<b>Товар:</b> {product_name}\n\n"
        "Выберите категорию:",
        reply_markup=get_category_keyboard()
    )


@router.callback_query(SEOStates.waiting_for_category, F.data.startswith("cat_"))
async def receive_category(callback: CallbackQuery, state: FSMContext):
    """Receive category"""
    if callback.data == "cat_custom":
        await state.set_state(SEOStates.waiting_for_custom_category)
        await callback.message.edit_text(
            "Введите категорию:",
            reply_markup=get_cancel_keyboard()
        )
        await callback.answer()
        return

    category = CATEGORY_NAMES.get(callback.data, "Другое")
    session = session_manager.get_session(callback.from_user.id)
    session.category = category

    await callback.answer()
    await process_seo(callback.message, state, callback.from_user.id)


@router.message(SEOStates.waiting_for_custom_category, F.text)
async def receive_custom_category(message: Message, state: FSMContext):
    """Receive custom category"""
    session = session_manager.get_session(message.from_user.id)
    session.category = message.text.strip()

    await process_seo(message, state, message.from_user.id)


async def process_seo(message: Message, state: FSMContext, user_id: int):
    """Process SEO generation"""
    await state.set_state(SEOStates.processing)

    session = session_manager.get_session(user_id)

    processing_msg = await message.answer(
        f"📝 Генерирую SEO-контент...\n\n"
        f"<b>Товар:</b> {session.product_name}\n"
        f"<b>Категория:</b> {session.category}\n\n"
        "Анализирую ключевые слова и создаю описание..."
    )

    try:
        # Get full analysis (keywords + SEO)
        analysis = await grok_service.generate_full_analysis(
            session.product_name,
            session.category,
            num_slides=5  # Default for SEO-only mode
        )

        if analysis:
            session.full_analysis = analysis
            session.keywords = analysis.get("keywords", {})

            # Format SEO response
            seo = analysis.get("seo", {})

            response_parts = [
                f"<b>SEO-контент для товара:</b>\n",
                f"<b>Заголовок:</b>\n{seo.get('title', 'Не сгенерирован')}\n",
            ]

            if seo.get("card_bullets"):
                response_parts.append("<b>Буллеты для карточки:</b>")
                for bullet in seo["card_bullets"][:7]:
                    response_parts.append(f"• {bullet}")
                response_parts.append("")

            if seo.get("description"):
                desc = seo["description"]
                if len(desc) > 800:
                    desc = desc[:800] + "..."
                response_parts.append(f"<b>Описание:</b>\n{desc}\n")

            # Add keywords summary
            keywords = analysis.get("keywords", {})
            if keywords.get("high_frequency"):
                response_parts.append(
                    f"<b>Топ ключевые слова:</b>\n"
                    f"{', '.join(keywords['high_frequency'][:5])}"
                )

            await processing_msg.edit_text(
                "\n".join(response_parts),
                reply_markup=get_back_to_menu_keyboard()
            )
        else:
            await processing_msg.edit_text(
                "❌ Не удалось сгенерировать SEO-контент.\n"
                "Попробуйте позже.",
                reply_markup=get_back_to_menu_keyboard()
            )

    except Exception as e:
        logger.error(f"Error generating SEO: {e}")
        await processing_msg.edit_text(
            "❌ Произошла ошибка.\nПопробуйте позже.",
            reply_markup=get_back_to_menu_keyboard()
        )

    await state.clear()


@router.message(SEOStates.waiting_for_product_name)
async def invalid_input(message: Message):
    """Handle invalid input"""
    await message.answer(
        "⚠️ Введите название товара текстом.",
        reply_markup=get_cancel_keyboard()
    )
