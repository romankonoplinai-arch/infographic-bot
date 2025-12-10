import logging

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, BufferedInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from bot.keyboards.menus import (
    get_cancel_keyboard,
    get_back_to_menu_keyboard,
    get_category_keyboard,
    get_slides_count_keyboard,
    CATEGORY_NAMES
)
from bot.models.session import session_manager
from bot.services.grok_service import grok_service
from bot.services.nanobanana_service import nanobanana_service

logger = logging.getLogger(__name__)
router = Router()


class SEOSlidesStates(StatesGroup):
    waiting_for_photo = State()
    waiting_for_description = State()
    waiting_for_slides_count = State()
    processing = State()


@router.callback_query(F.data == "seo_slides")
async def start_seo_slides(callback: CallbackQuery, state: FSMContext):
    """Start SEO + slides planning flow"""
    await state.set_state(SEOSlidesStates.waiting_for_photo)

    await callback.message.edit_text(
        "<b>📝 SEO + План слайдов для инфографики</b>\n\n"
        "Этот инструмент создаст:\n"
        "• SEO-описание для карточки товара\n"
        "• Промты для каждого слайда с фокусом на CTR\n\n"
        "📸 <b>Шаг 1:</b> Отправьте фото товара:",
        reply_markup=get_cancel_keyboard()
    )
    await callback.answer()


@router.message(SEOSlidesStates.waiting_for_photo, F.photo)
async def receive_photo(message: Message, state: FSMContext, bot: Bot):
    """Receive product photo"""
    try:
        photo = message.photo[-1]
        file = await bot.get_file(photo.file_id)
        file_bytes = await bot.download_file(file.file_path)
        image_bytes = file_bytes.read()

        session = session_manager.get_session(message.from_user.id)
        session.original_image = image_bytes

        # Analyze image
        processing_msg = await message.answer("⏳ Анализирую товар на фото...")

        analysis = await nanobanana_service.analyze_product_image(image_bytes)

        await processing_msg.delete()

        analysis_text = ""
        if analysis:
            analysis_text = f"\n\n<b>Анализ фото:</b>\n{analysis[:300]}..."

        await state.set_state(SEOSlidesStates.waiting_for_description)

        await message.answer(
            f"✅ Фото загружено!{analysis_text}\n\n"
            "<b>📝 Шаг 2:</b> Опишите товар и ваши пожелания по слайдам.\n\n"
            "<b>Важно указать:</b>\n"
            "• Название товара\n"
            "• Что должно быть на каждом слайде\n"
            "• Особенности (размеры, материал, доставка и т.д.)\n\n"
            "<b>Пример:</b>\n"
            "<i>Кроссовки Nike Air Max\n"
            "Слайд 1 - главная с товаром и ценой\n"
            "Слайд 2 - таблица размеров\n"
            "Слайд 3 - преимущества материала\n"
            "Слайд 4 - удобная доставка и возврат</i>\n\n"
            "✏️ Введите описание:",
            reply_markup=get_cancel_keyboard()
        )

    except Exception as e:
        logger.error(f"Error receiving photo: {e}")
        await message.answer(
            "❌ Ошибка загрузки фото. Попробуйте другое.",
            reply_markup=get_cancel_keyboard()
        )


@router.message(SEOSlidesStates.waiting_for_description, F.text)
async def receive_description(message: Message, state: FSMContext):
    """Receive product description and wishes"""
    description = message.text.strip()

    if len(description) < 10:
        await message.answer(
            "⚠️ Описание слишком короткое. Добавьте больше деталей.",
            reply_markup=get_cancel_keyboard()
        )
        return

    session = session_manager.get_session(message.from_user.id)
    session.product_description = description

    await state.set_state(SEOSlidesStates.waiting_for_slides_count)

    await message.answer(
        f"<b>Описание сохранено!</b>\n\n"
        "<b>📊 Шаг 3:</b> Выберите количество слайдов:",
        reply_markup=get_slides_count_keyboard()
    )


@router.callback_query(SEOSlidesStates.waiting_for_slides_count, F.data.startswith("slides_"))
async def receive_slides_count(callback: CallbackQuery, state: FSMContext):
    """Process SEO and slides generation"""
    slides_data = callback.data.replace("slides_", "")

    if slides_data == "auto":
        num_slides = 5  # Default
    else:
        num_slides = int(slides_data)

    await state.set_state(SEOSlidesStates.processing)

    session = session_manager.get_session(callback.from_user.id)

    await callback.answer("Генерирую SEO и план слайдов...")

    processing_msg = await callback.message.edit_text(
        "⏳ <b>Создаю SEO и план слайдов...</b>\n\n"
        "🔍 Анализирую ключевые слова\n"
        "📝 Генерирую SEO-описание\n"
        "🎯 Создаю промты для максимального CTR\n\n"
        "Это может занять до минуты..."
    )

    try:
        # Generate SEO and slide prompts with CTR focus
        result = await grok_service.generate_seo_with_ctr_prompts(
            product_description=session.product_description,
            num_slides=num_slides
        )

        if result:
            session.full_analysis = result
            session.seo_content = result.get("seo", {})
            session.slide_prompts = result.get("slide_prompts", [])

            # Message 1: SEO Description
            seo = result.get("seo", {})
            seo_parts = [
                "<b>✅ SEO-описание для карточки:</b>\n",
                f"<b>📌 Заголовок:</b>\n{seo.get('title', 'N/A')}\n",
            ]

            if seo.get("description"):
                seo_parts.append(f"\n<b>📝 Описание:</b>\n{seo['description']}")

            await processing_msg.edit_text("\n".join(seo_parts))

            # Message 2: Keywords
            keywords = result.get("keywords", {})
            if keywords:
                kw_parts = ["<b>🔑 Ключевые слова:</b>\n"]
                if keywords.get("high_frequency"):
                    kw_parts.append(f"<b>ВЧ:</b> {', '.join(keywords['high_frequency'][:5])}")
                if keywords.get("mid_frequency"):
                    kw_parts.append(f"<b>СЧ:</b> {', '.join(keywords['mid_frequency'][:5])}")
                await callback.message.answer("\n".join(kw_parts))

            # Message 3: Slide prompts
            prompts = result.get("slide_prompts", [])
            if prompts:
                prompts_parts = ["<b>🎨 План слайдов (CTR-оптимизированный):</b>\n"]
                for p in prompts:
                    slide_num = p.get("slide", "?")
                    focus = p.get("focus", "")
                    text = p.get("text_ru", "")
                    prompts_parts.append(f"\n<b>Слайд {slide_num}:</b> {focus}\n<i>{text}</i>")

                await callback.message.answer(
                    "\n".join(prompts_parts),
                    reply_markup=get_back_to_menu_keyboard()
                )

                # Save for later use in slide generation
                await callback.message.answer(
                    "💡 <b>Совет:</b> Теперь перейдите в «Создать первый слайд» "
                    "чтобы сгенерировать инфографику на основе этого плана."
                )
            else:
                await callback.message.answer(
                    "⚠️ Промты для слайдов не созданы.",
                    reply_markup=get_back_to_menu_keyboard()
                )

        else:
            await processing_msg.edit_text(
                "❌ Не удалось создать SEO и план.\nПопробуйте позже.",
                reply_markup=get_back_to_menu_keyboard()
            )

    except Exception as e:
        logger.error(f"Error generating SEO slides: {e}")
        await processing_msg.edit_text(
            "❌ Ошибка при создании.\nПопробуйте позже.",
            reply_markup=get_back_to_menu_keyboard()
        )

    await state.clear()


@router.message(SEOSlidesStates.waiting_for_photo)
async def invalid_photo_input(message: Message):
    """Handle non-photo input"""
    await message.answer(
        "⚠️ Отправьте фотографию товара.",
        reply_markup=get_cancel_keyboard()
    )


@router.message(SEOSlidesStates.waiting_for_description)
async def invalid_desc_input(message: Message):
    """Handle non-text input"""
    await message.answer(
        "⚠️ Введите описание текстом.",
        reply_markup=get_cancel_keyboard()
    )
