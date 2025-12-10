import logging

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, BufferedInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.keyboards.menus import get_cancel_keyboard, get_back_to_menu_keyboard
from bot.services.nanobanana_service import nanobanana_service
from bot.utils.image_utils import compress_image, resize_for_telegram

logger = logging.getLogger(__name__)
router = Router()


class FreeImageStates(StatesGroup):
    waiting_for_prompt = State()
    processing = State()
    viewing_result = State()


def get_result_keyboard():
    """Keyboard after generation"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🔄 Ещё вариант", callback_data="free_regenerate")
    )
    builder.row(
        InlineKeyboardButton(text="✏️ Новый промпт", callback_data="free_new_prompt"),
        InlineKeyboardButton(text="🏠 Меню", callback_data="back_to_menu")
    )
    return builder.as_markup()


@router.callback_query(F.data == "free_image")
async def start_free_image(callback: CallbackQuery, state: FSMContext):
    """Start free image generation"""
    await state.set_state(FreeImageStates.waiting_for_prompt)

    await callback.message.edit_text(
        "<b>🖼 Генерация изображения по промпту</b>\n\n"
        "Опишите что хотите сгенерировать.\n"
        "Модель создаст изображение по вашему описанию.\n\n"
        "<b>Примеры промптов:</b>\n"
        "• <i>Инфографика для маркетплейса: кроссовки Nike на белом фоне, цена 4990₽, бейдж скидка -30%</i>\n"
        "• <i>Баннер для рекламы: яркий фон, текст РАСПРОДАЖА, летняя тема</i>\n"
        "• <i>Иконка для приложения: минималистичный дизайн, корзина покупок</i>\n\n"
        "✏️ Введите ваш промпт:",
        reply_markup=get_cancel_keyboard()
    )
    await callback.answer()


@router.message(FreeImageStates.waiting_for_prompt, F.text)
async def receive_prompt(message: Message, state: FSMContext):
    """Receive prompt and generate image"""
    prompt = message.text.strip()

    if len(prompt) < 5:
        await message.answer(
            "⚠️ Промпт слишком короткий. Опишите подробнее.",
            reply_markup=get_cancel_keyboard()
        )
        return

    # Save prompt for regeneration
    await state.update_data(prompt=prompt)

    await generate_and_show_image(message, state, prompt)


async def generate_and_show_image(message: Message, state: FSMContext, prompt: str):
    """Generate image and show with result keyboard"""
    await state.set_state(FreeImageStates.processing)

    processing_msg = await message.answer(
        "🎨 <b>Генерирую изображение...</b>\n\n"
        "Это может занять до минуты."
    )

    try:
        image_bytes = await nanobanana_service.generate_from_prompt(prompt)

        await processing_msg.delete()

        if image_bytes:
            processed = resize_for_telegram(image_bytes)
            processed = compress_image(processed, max_size_mb=5)

            await state.set_state(FreeImageStates.viewing_result)

            await message.answer_photo(
                photo=BufferedInputFile(processed, filename="generated.jpg"),
                caption=(
                    "<b>✅ Изображение готово!</b>\n\n"
                    f"<b>Промпт:</b> <i>{prompt[:100]}{'...' if len(prompt) > 100 else ''}</i>"
                ),
                reply_markup=get_result_keyboard()
            )
        else:
            await message.answer(
                "❌ Не удалось сгенерировать изображение.\nПопробуйте другой промпт.",
                reply_markup=get_result_keyboard()
            )
            await state.set_state(FreeImageStates.viewing_result)

    except Exception as e:
        logger.error(f"Error generating free image: {e}")
        await processing_msg.edit_text(
            "❌ Ошибка при генерации.\nПопробуйте ещё раз.",
            reply_markup=get_result_keyboard()
        )
        await state.set_state(FreeImageStates.viewing_result)


@router.callback_query(F.data == "free_regenerate")
async def regenerate_image(callback: CallbackQuery, state: FSMContext):
    """Regenerate with same prompt"""
    data = await state.get_data()
    prompt = data.get("prompt")

    if not prompt:
        await callback.message.answer(
            "❌ Промпт потерян. Введите новый.",
            reply_markup=get_cancel_keyboard()
        )
        await state.set_state(FreeImageStates.waiting_for_prompt)
        await callback.answer()
        return

    await callback.answer("Генерирую новый вариант...")
    await generate_and_show_image(callback.message, state, prompt)


@router.callback_query(F.data == "free_new_prompt")
async def new_prompt(callback: CallbackQuery, state: FSMContext):
    """Enter new prompt"""
    await state.set_state(FreeImageStates.waiting_for_prompt)

    await callback.message.answer(
        "✏️ Введите новый промпт:",
        reply_markup=get_cancel_keyboard()
    )
    await callback.answer()


@router.message(FreeImageStates.waiting_for_prompt)
async def invalid_prompt_input(message: Message):
    """Handle non-text input"""
    await message.answer(
        "⚠️ Введите текстовый промпт.",
        reply_markup=get_cancel_keyboard()
    )
