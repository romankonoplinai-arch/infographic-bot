import io
import logging

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, BufferedInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from bot.keyboards.menus import get_cancel_keyboard, get_back_to_menu_keyboard
from bot.models.session import session_manager
from bot.services.nanobanana_service import nanobanana_service
from bot.utils.image_utils import compress_image, resize_for_telegram

logger = logging.getLogger(__name__)
router = Router()


class RemoveBgStates(StatesGroup):
    waiting_for_photo = State()
    processing = State()


@router.callback_query(F.data == "remove_bg")
async def start_remove_bg(callback: CallbackQuery, state: FSMContext):
    """Start background removal flow"""
    await state.set_state(RemoveBgStates.waiting_for_photo)

    await callback.message.edit_text(
        "<b>Удаление фона с фото</b>\n\n"
        "Отправьте фотографию товара, и я удалю с неё фон.\n\n"
        "📸 Отправьте фото:",
        reply_markup=get_cancel_keyboard()
    )
    await callback.answer()


@router.message(RemoveBgStates.waiting_for_photo, F.photo)
async def process_photo_for_bg_removal(message: Message, state: FSMContext, bot: Bot):
    """Process received photo for background removal"""
    await state.set_state(RemoveBgStates.processing)

    # Send processing message
    processing_msg = await message.answer(
        "⏳ Обрабатываю изображение...\n"
        "Это может занять несколько секунд."
    )

    try:
        # Get the largest photo
        photo = message.photo[-1]

        # Download photo
        file = await bot.get_file(photo.file_id)
        file_bytes = await bot.download_file(file.file_path)
        image_bytes = file_bytes.read()

        # Save to session
        session = session_manager.get_session(message.from_user.id)
        session.original_image = image_bytes

        # Analyze product image
        analysis = await nanobanana_service.analyze_product_image(image_bytes)

        if analysis:
            # For now, we send back the original with analysis
            # In production, integrate with actual background removal API

            # Compress and resize for Telegram
            processed_image = resize_for_telegram(image_bytes)
            processed_image = compress_image(processed_image, max_size_mb=5)

            # Save processed image
            session.no_bg_image = processed_image

            # Send result
            await processing_msg.delete()

            await message.answer_photo(
                photo=BufferedInputFile(
                    processed_image,
                    filename="product_no_bg.jpg"
                ),
                caption=(
                    "<b>Анализ изображения:</b>\n\n"
                    f"{analysis[:800]}...\n\n"
                    "✅ Изображение сохранено для дальнейшей работы."
                ),
                reply_markup=get_back_to_menu_keyboard()
            )
        else:
            await processing_msg.edit_text(
                "❌ Не удалось обработать изображение.\n"
                "Попробуйте другое фото.",
                reply_markup=get_back_to_menu_keyboard()
            )

    except Exception as e:
        logger.error(f"Error processing photo: {e}")
        await processing_msg.edit_text(
            "❌ Произошла ошибка при обработке.\n"
            "Попробуйте позже.",
            reply_markup=get_back_to_menu_keyboard()
        )

    await state.clear()


@router.message(RemoveBgStates.waiting_for_photo)
async def invalid_photo_input(message: Message):
    """Handle non-photo input when photo is expected"""
    await message.answer(
        "⚠️ Пожалуйста, отправьте фотографию.\n"
        "Я жду изображение товара.",
        reply_markup=get_cancel_keyboard()
    )
