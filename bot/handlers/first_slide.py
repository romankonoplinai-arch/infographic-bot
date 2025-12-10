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


class FirstSlideStates(StatesGroup):
    waiting_for_product_photo = State()
    waiting_for_reference = State()
    waiting_for_prompt = State()
    processing = State()


def get_reference_keyboard():
    """Keyboard for reference choice"""
    from aiogram.types import InlineKeyboardButton
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📷 С референсом", callback_data="first_with_ref")
    )
    builder.row(
        InlineKeyboardButton(text="🎨 Без референса", callback_data="first_no_ref")
    )
    builder.row(
        InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")
    )
    return builder.as_markup()


@router.callback_query(F.data == "first_slide")
async def start_first_slide(callback: CallbackQuery, state: FSMContext):
    """Start first slide generation"""
    await state.set_state(FirstSlideStates.waiting_for_product_photo)

    await callback.message.edit_text(
        "<b>🎨 Создание первого слайда инфографики</b>\n\n"
        "Первый слайд - самый важный для CTR!\n"
        "Вы получите 3 варианта в разных стилях.\n\n"
        "📸 <b>Шаг 1:</b> Отправьте фото товара:",
        reply_markup=get_cancel_keyboard()
    )
    await callback.answer()


@router.message(FirstSlideStates.waiting_for_product_photo, F.photo)
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
            "<b>Шаг 2:</b> Хотите добавить референс?\n\n"
            "Референс - это пример слайда, стиль которого нужно повторить.",
            reply_markup=get_reference_keyboard()
        )

    except Exception as e:
        logger.error(f"Error receiving photo: {e}")
        await message.answer(
            "❌ Ошибка загрузки. Попробуйте другое фото.",
            reply_markup=get_cancel_keyboard()
        )


@router.callback_query(F.data == "first_with_ref")
async def choose_with_reference(callback: CallbackQuery, state: FSMContext):
    """User wants to add reference"""
    await state.set_state(FirstSlideStates.waiting_for_reference)

    await callback.message.edit_text(
        "<b>📷 Загрузка референса</b>\n\n"
        "Отправьте фото-референс первого слайда.\n"
        "Модель возьмёт стиль и композицию из референса.\n\n"
        "📸 Отправьте фото референса:",
        reply_markup=get_cancel_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data == "first_no_ref")
async def choose_no_reference(callback: CallbackQuery, state: FSMContext):
    """User doesn't want reference"""
    await state.set_state(FirstSlideStates.waiting_for_prompt)

    session = session_manager.get_session(callback.from_user.id)
    session.reference_image = None

    await callback.message.edit_text(
        "<b>✏️ Опишите первый слайд</b>\n\n"
        "Что должно быть на главном слайде?\n\n"
        "<b>Пример:</b>\n"
        "<i>Главный слайд для кроссовок Nike.\n"
        "Показать товар крупно, цену 4990₽,\n"
        "бейдж 'Хит продаж', акцент на качество.</i>\n\n"
        "✏️ Введите описание:",
        reply_markup=get_cancel_keyboard()
    )
    await callback.answer()


@router.message(FirstSlideStates.waiting_for_reference, F.photo)
async def receive_reference(message: Message, state: FSMContext, bot: Bot):
    """Receive reference photo"""
    try:
        photo = message.photo[-1]
        file = await bot.get_file(photo.file_id)
        file_bytes = await bot.download_file(file.file_path)
        image_bytes = file_bytes.read()

        session = session_manager.get_session(message.from_user.id)
        session.reference_image = image_bytes

        await state.set_state(FirstSlideStates.waiting_for_prompt)

        await message.answer(
            "✅ Референс загружен!\n\n"
            "<b>✏️ Опишите первый слайд</b>\n\n"
            "Модель возьмёт стиль из референса.\n"
            "Укажите что именно показать на слайде.\n\n"
            "<b>Пример:</b>\n"
            "<i>Сделай в стиле референса.\n"
            "Товар - постельное бельё.\n"
            "Цена 2990₽, премиум качество,\n"
            "акцент на натуральные материалы.</i>\n\n"
            "✏️ Введите описание:",
            reply_markup=get_cancel_keyboard()
        )

    except Exception as e:
        logger.error(f"Error receiving reference: {e}")
        await message.answer(
            "❌ Ошибка загрузки референса.",
            reply_markup=get_cancel_keyboard()
        )


@router.message(FirstSlideStates.waiting_for_prompt, F.text)
async def receive_prompt_and_generate(message: Message, state: FSMContext, bot: Bot):
    """Generate 3 variants of first slide"""
    prompt = message.text.strip()

    if len(prompt) < 10:
        await message.answer(
            "⚠️ Описание слишком короткое.",
            reply_markup=get_cancel_keyboard()
        )
        return

    await state.set_state(FirstSlideStates.processing)

    session = session_manager.get_session(message.from_user.id)

    if not session.original_image:
        await message.answer(
            "❌ Фото товара не найдено. Начните заново.",
            reply_markup=get_back_to_menu_keyboard()
        )
        await state.clear()
        return

    processing_msg = await message.answer(
        "🎨 <b>Генерирую 3 варианта первого слайда...</b>\n\n"
        "Это может занять 2-3 минуты.\n"
        "Каждый вариант в уникальном стиле для максимального CTR."
    )

    try:
        # Generate 3 variants
        variants = await nanobanana_service.generate_first_slide_variants(
            product_image_bytes=session.original_image,
            reference_image_bytes=session.reference_image,
            prompt=prompt,
            num_variants=3
        )

        await processing_msg.delete()

        if variants:
            success_count = sum(1 for v in variants if v.get("image_bytes"))

            await message.answer(
                f"<b>✅ Готово!</b>\n\n"
                f"Создано {success_count} из 3 вариантов.\n"
                f"Выберите лучший для генерации остальных слайдов."
            )

            for i, variant in enumerate(variants, 1):
                style = variant.get("style", f"Стиль {i}")

                if variant.get("image_bytes"):
                    processed = resize_for_telegram(variant["image_bytes"])
                    processed = compress_image(processed, max_size_mb=5)

                    await message.answer_photo(
                        photo=BufferedInputFile(processed, filename=f"variant_{i}.jpg"),
                        caption=f"<b>Вариант {i}:</b> {style}"
                    )
                else:
                    await message.answer(f"❌ Вариант {i} не удалось сгенерировать")

            await message.answer(
                "💡 <b>Совет:</b> Сохраните лучший вариант и используйте его "
                "как референс в «Создать слайды по референсу».",
                reply_markup=get_back_to_menu_keyboard()
            )
        else:
            await message.answer(
                "❌ Не удалось сгенерировать варианты.\nПопробуйте другой промт.",
                reply_markup=get_back_to_menu_keyboard()
            )

    except Exception as e:
        logger.error(f"Error generating first slide: {e}")
        await processing_msg.edit_text(
            "❌ Ошибка при генерации.\nПопробуйте позже.",
            reply_markup=get_back_to_menu_keyboard()
        )

    await state.clear()


@router.message(FirstSlideStates.waiting_for_product_photo)
async def invalid_product_photo(message: Message):
    await message.answer("⚠️ Отправьте фотографию товара.", reply_markup=get_cancel_keyboard())


@router.message(FirstSlideStates.waiting_for_reference)
async def invalid_reference(message: Message):
    await message.answer("⚠️ Отправьте фото референса.", reply_markup=get_cancel_keyboard())


@router.message(FirstSlideStates.waiting_for_prompt)
async def invalid_prompt(message: Message):
    await message.answer("⚠️ Введите описание текстом.", reply_markup=get_cancel_keyboard())
