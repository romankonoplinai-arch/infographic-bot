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


class EditPhotoStates(StatesGroup):
    waiting_for_photo = State()
    waiting_for_prompt = State()
    processing = State()


@router.callback_query(F.data == "edit_photo")
async def start_edit_photo(callback: CallbackQuery, state: FSMContext):
    """Start photo editing flow"""
    await state.set_state(EditPhotoStates.waiting_for_photo)

    await callback.message.edit_text(
        "<b>✏️ Умный редактор фото</b>\n\n"
        "Отправьте фотографию для редактирования.\n\n"
        "<b>Возможности:</b>\n"
        "• Удаление фона\n"
        "• Редактирование по описанию\n"
        "• Улучшение качества\n"
        "• Добавление элементов\n\n"
        "📸 Отправьте фото:",
        reply_markup=get_cancel_keyboard()
    )
    await callback.answer()


@router.message(EditPhotoStates.waiting_for_photo, F.photo)
async def receive_photo_for_edit(message: Message, state: FSMContext, bot: Bot):
    """Receive photo for editing"""
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

        await state.set_state(EditPhotoStates.waiting_for_prompt)

        await message.answer(
            "✅ Фото загружено!\n\n"
            "<b>Опишите, что нужно сделать:</b>\n\n"
            "Примеры:\n"
            "• <i>Товар - кровать, убери всё вокруг, оставь только товар на белом фоне</i>\n"
            "• <i>Сделай фон белым</i>\n"
            "• <i>Убери фон, оставь только товар</i>\n"
            "• <i>Улучши освещение и цвета</i>\n"
            "• <i>Добавь текст 'СКИДКА 50%' красным</i>\n"
            "• <i>Убери лишние объекты</i>\n\n"
            "✏️ Напишите ваш промт:",
            reply_markup=get_cancel_keyboard()
        )

    except Exception as e:
        logger.error(f"Error receiving photo: {e}")
        await message.answer(
            "❌ Ошибка при загрузке фото. Попробуйте другое.",
            reply_markup=get_cancel_keyboard()
        )


@router.message(EditPhotoStates.waiting_for_prompt, F.text)
async def receive_edit_prompt(message: Message, state: FSMContext, bot: Bot):
    """Receive editing prompt and process"""
    prompt = message.text.strip()

    if len(prompt) < 3:
        await message.answer(
            "⚠️ Промт слишком короткий. Опишите подробнее, что нужно изменить.",
            reply_markup=get_cancel_keyboard()
        )
        return

    await state.set_state(EditPhotoStates.processing)

    session = session_manager.get_session(message.from_user.id)

    if not session.original_image:
        await message.answer(
            "❌ Фото не найдено. Начните заново.",
            reply_markup=get_back_to_menu_keyboard()
        )
        await state.clear()
        return

    # Send processing message
    processing_msg = await message.answer(
        f"⏳ Обрабатываю изображение...\n\n"
        f"<b>Ваш промт:</b> {prompt[:100]}{'...' if len(prompt) > 100 else ''}\n\n"
        "Это может занять до минуты..."
    )

    try:
        # Edit image using Nano Banana Pro
        edited_image = await nanobanana_service.edit_image_by_prompt(
            image_bytes=session.original_image,
            prompt=prompt
        )

        if edited_image:
            # Compress and resize for Telegram
            processed_image = resize_for_telegram(edited_image)
            processed_image = compress_image(processed_image, max_size_mb=5)

            await processing_msg.delete()

            await message.answer_photo(
                photo=BufferedInputFile(
                    processed_image,
                    filename="edited_photo.jpg"
                ),
                caption=(
                    f"✅ <b>Фото отредактировано!</b>\n\n"
                    f"<b>Промт:</b> {prompt[:200]}{'...' if len(prompt) > 200 else ''}"
                ),
                reply_markup=get_back_to_menu_keyboard()
            )
        else:
            await processing_msg.edit_text(
                "❌ Не удалось отредактировать изображение.\n"
                "Попробуйте другой промт или другое фото.",
                reply_markup=get_back_to_menu_keyboard()
            )

    except Exception as e:
        logger.error(f"Error editing photo: {e}")
        await processing_msg.edit_text(
            "❌ Произошла ошибка при обработке.\n"
            "Попробуйте позже.",
            reply_markup=get_back_to_menu_keyboard()
        )

    await state.clear()


@router.message(EditPhotoStates.waiting_for_photo)
async def invalid_photo_input(message: Message):
    """Handle non-photo input when photo is expected"""
    await message.answer(
        "⚠️ Пожалуйста, отправьте фотографию.",
        reply_markup=get_cancel_keyboard()
    )


@router.message(EditPhotoStates.waiting_for_prompt)
async def invalid_prompt_input(message: Message):
    """Handle non-text input when prompt is expected"""
    await message.answer(
        "⚠️ Пожалуйста, напишите текстом, что нужно изменить на фото.",
        reply_markup=get_cancel_keyboard()
    )
