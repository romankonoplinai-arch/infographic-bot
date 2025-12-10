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


class SlidesFromRefStates(StatesGroup):
    waiting_for_main_reference = State()
    waiting_for_product_photo = State()
    waiting_for_additional_ref = State()
    waiting_for_description = State()
    waiting_for_more_slides = State()
    processing = State()


def get_additional_ref_keyboard():
    """Keyboard for additional reference choice"""
    from aiogram.types import InlineKeyboardButton
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="➕ Добавить референс", callback_data="add_extra_ref")
    )
    builder.row(
        InlineKeyboardButton(text="⏭ Пропустить", callback_data="skip_extra_ref")
    )
    builder.row(
        InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")
    )
    return builder.as_markup()


def get_more_slides_keyboard():
    """Keyboard for generating more slides"""
    from aiogram.types import InlineKeyboardButton
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="➕ Ещё слайд", callback_data="generate_more_slide")
    )
    builder.row(
        InlineKeyboardButton(text="✅ Готово", callback_data="slides_done")
    )
    return builder.as_markup()


@router.callback_query(F.data == "slides_from_ref")
async def start_slides_from_ref(callback: CallbackQuery, state: FSMContext):
    """Start slide generation from reference"""
    await state.set_state(SlidesFromRefStates.waiting_for_main_reference)

    # Reset slide counter
    await state.update_data(slide_count=0)

    await callback.message.edit_text(
        "<b>📑 Создание слайдов по референсу</b>\n\n"
        "Генерация слайдов в стиле вашего первого слайда.\n\n"
        "<b>📸 Шаг 1:</b> Отправьте референс первого слайда\n"
        "(это задаст стиль для всех остальных)",
        reply_markup=get_cancel_keyboard()
    )
    await callback.answer()


@router.message(SlidesFromRefStates.waiting_for_main_reference, F.photo)
async def receive_main_reference(message: Message, state: FSMContext, bot: Bot):
    """Receive main style reference"""
    try:
        photo = message.photo[-1]
        file = await bot.get_file(photo.file_id)
        file_bytes = await bot.download_file(file.file_path)
        image_bytes = file_bytes.read()

        session = session_manager.get_session(message.from_user.id)
        session.reference_image = image_bytes

        await state.set_state(SlidesFromRefStates.waiting_for_product_photo)

        await message.answer(
            "✅ Референс стиля загружен!\n\n"
            "<b>📸 Шаг 2:</b> Отправьте фото товара\n"
            "(или отправьте любое сообщение чтобы пропустить)",
            reply_markup=get_cancel_keyboard()
        )

    except Exception as e:
        logger.error(f"Error receiving reference: {e}")
        await message.answer(
            "❌ Ошибка загрузки. Попробуйте другое фото.",
            reply_markup=get_cancel_keyboard()
        )


@router.message(SlidesFromRefStates.waiting_for_product_photo, F.photo)
async def receive_product_photo(message: Message, state: FSMContext, bot: Bot):
    """Receive product photo"""
    try:
        photo = message.photo[-1]
        file = await bot.get_file(photo.file_id)
        file_bytes = await bot.download_file(file.file_path)
        image_bytes = file_bytes.read()

        session = session_manager.get_session(message.from_user.id)
        session.original_image = image_bytes

        await message.answer(
            "✅ Фото товара загружено!\n\n"
            "<b>📸 Шаг 3:</b> Дополнительный референс?\n\n"
            "Можете добавить референс для контента/структуры слайда\n"
            "(например, слайд с размерами для примера)",
            reply_markup=get_additional_ref_keyboard()
        )

    except Exception as e:
        logger.error(f"Error receiving product photo: {e}")
        await message.answer(
            "❌ Ошибка. Попробуйте другое фото.",
            reply_markup=get_cancel_keyboard()
        )


@router.message(SlidesFromRefStates.waiting_for_product_photo, F.text)
async def skip_product_photo(message: Message, state: FSMContext):
    """Skip product photo"""
    session = session_manager.get_session(message.from_user.id)
    session.original_image = None

    await message.answer(
        "⏭ Фото товара пропущено.\n\n"
        "<b>📸 Шаг 3:</b> Дополнительный референс?\n\n"
        "Можете добавить референс для контента/структуры слайда.",
        reply_markup=get_additional_ref_keyboard()
    )


@router.callback_query(F.data == "add_extra_ref")
async def add_additional_reference(callback: CallbackQuery, state: FSMContext):
    """User wants to add additional reference"""
    await state.set_state(SlidesFromRefStates.waiting_for_additional_ref)

    await callback.message.edit_text(
        "<b>📷 Дополнительный референс</b>\n\n"
        "Отправьте фото-референс для структуры/контента.\n"
        "Стиль возьмётся из основного референса,\n"
        "а структура - из этого.\n\n"
        "📸 Отправьте фото:",
        reply_markup=get_cancel_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data == "skip_extra_ref")
async def skip_additional_reference(callback: CallbackQuery, state: FSMContext):
    """Skip additional reference"""
    session = session_manager.get_session(callback.from_user.id)
    session.additional_reference = None

    await state.set_state(SlidesFromRefStates.waiting_for_description)

    await callback.message.edit_text(
        "<b>✏️ Опишите слайд</b>\n\n"
        "Что должно быть на этом слайде?\n\n"
        "<b>Пример:</b>\n"
        "<i>Слайд 2 - размеры. Показать таблицу размеров\n"
        "для обуви: EU 36-45, US 5-12. Текст 'Выберите\n"
        "свой размер' и указатель на таблицу.</i>\n\n"
        "✏️ Введите описание:",
        reply_markup=get_cancel_keyboard()
    )
    await callback.answer()


@router.message(SlidesFromRefStates.waiting_for_additional_ref, F.photo)
async def receive_additional_reference(message: Message, state: FSMContext, bot: Bot):
    """Receive additional reference"""
    try:
        photo = message.photo[-1]
        file = await bot.get_file(photo.file_id)
        file_bytes = await bot.download_file(file.file_path)
        image_bytes = file_bytes.read()

        session = session_manager.get_session(message.from_user.id)
        session.additional_reference = image_bytes

        await state.set_state(SlidesFromRefStates.waiting_for_description)

        await message.answer(
            "✅ Дополнительный референс загружен!\n\n"
            "<b>✏️ Опишите слайд</b>\n\n"
            "Что должно быть на этом слайде?\n\n"
            "✏️ Введите описание:",
            reply_markup=get_cancel_keyboard()
        )

    except Exception as e:
        logger.error(f"Error receiving additional ref: {e}")
        await message.answer(
            "❌ Ошибка. Попробуйте другое фото.",
            reply_markup=get_cancel_keyboard()
        )


@router.message(SlidesFromRefStates.waiting_for_description, F.text)
async def receive_description_and_generate(message: Message, state: FSMContext, bot: Bot):
    """Generate slide based on description"""
    description = message.text.strip()

    if len(description) < 5:
        await message.answer(
            "⚠️ Описание слишком короткое.",
            reply_markup=get_cancel_keyboard()
        )
        return

    await state.set_state(SlidesFromRefStates.processing)

    session = session_manager.get_session(message.from_user.id)
    data = await state.get_data()
    slide_count = data.get("slide_count", 0) + 1

    if not session.reference_image:
        await message.answer(
            "❌ Референс не найден. Начните заново.",
            reply_markup=get_back_to_menu_keyboard()
        )
        await state.clear()
        return

    processing_msg = await message.answer(
        f"🎨 <b>Генерирую слайд {slide_count + 1}...</b>\n\n"
        "Это может занять до минуты."
    )

    try:
        slide_image = await nanobanana_service.generate_slide_from_reference(
            reference_image_bytes=session.reference_image,
            product_image_bytes=session.original_image,
            additional_reference_bytes=getattr(session, 'additional_reference', None),
            slide_description=description,
            slide_number=slide_count + 1
        )

        await processing_msg.delete()

        if slide_image:
            processed = resize_for_telegram(slide_image)
            processed = compress_image(processed, max_size_mb=5)

            await message.answer_photo(
                photo=BufferedInputFile(processed, filename=f"slide_{slide_count + 1}.jpg"),
                caption=f"<b>✅ Слайд {slide_count + 1}</b>\n\n{description[:200]}..."
            )

            # Update slide count
            await state.update_data(slide_count=slide_count)
            await state.set_state(SlidesFromRefStates.waiting_for_more_slides)

            await message.answer(
                "Хотите создать ещё слайд?",
                reply_markup=get_more_slides_keyboard()
            )
        else:
            await message.answer(
                "❌ Не удалось сгенерировать слайд.\nПопробуйте другое описание.",
                reply_markup=get_more_slides_keyboard()
            )
            await state.set_state(SlidesFromRefStates.waiting_for_more_slides)

    except Exception as e:
        logger.error(f"Error generating slide: {e}")
        await processing_msg.edit_text(
            "❌ Ошибка при генерации.",
            reply_markup=get_back_to_menu_keyboard()
        )
        await state.clear()


@router.callback_query(F.data == "generate_more_slide")
async def generate_more_slides(callback: CallbackQuery, state: FSMContext):
    """User wants more slides"""
    # Clear additional reference for new slide
    session = session_manager.get_session(callback.from_user.id)
    session.additional_reference = None

    await state.set_state(SlidesFromRefStates.waiting_for_description)

    data = await state.get_data()
    slide_count = data.get("slide_count", 0)

    await callback.message.edit_text(
        f"<b>📑 Слайд {slide_count + 2}</b>\n\n"
        "Хотите добавить референс для этого слайда?",
        reply_markup=get_additional_ref_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data == "slides_done")
async def slides_done(callback: CallbackQuery, state: FSMContext):
    """User is done with slides"""
    data = await state.get_data()
    slide_count = data.get("slide_count", 0)

    await callback.message.edit_text(
        f"<b>✅ Готово!</b>\n\n"
        f"Создано слайдов: {slide_count}\n\n"
        "Все слайды сгенерированы в едином стиле.",
        reply_markup=get_back_to_menu_keyboard()
    )
    await state.clear()
    await callback.answer()


@router.message(SlidesFromRefStates.waiting_for_main_reference)
async def invalid_main_ref(message: Message):
    await message.answer("⚠️ Отправьте фото референса.", reply_markup=get_cancel_keyboard())


@router.message(SlidesFromRefStates.waiting_for_additional_ref)
async def invalid_add_ref(message: Message):
    await message.answer("⚠️ Отправьте фото референса.", reply_markup=get_cancel_keyboard())


@router.message(SlidesFromRefStates.waiting_for_description)
async def invalid_desc(message: Message):
    await message.answer("⚠️ Введите описание текстом.", reply_markup=get_cancel_keyboard())
