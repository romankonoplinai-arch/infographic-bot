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
    get_edit_plan_keyboard,
    CATEGORY_NAMES
)
from bot.models.session import session_manager
from bot.services.grok_service import grok_service
from bot.services.nanobanana_service import nanobanana_service
from bot.utils.image_utils import compress_image, resize_for_telegram

logger = logging.getLogger(__name__)
router = Router()


class InfographicStates(StatesGroup):
    waiting_for_photo = State()
    waiting_for_product_name = State()
    waiting_for_category = State()
    waiting_for_custom_category = State()
    waiting_for_slides_count = State()
    confirming_plan = State()
    generating = State()


@router.callback_query(F.data == "infographic")
async def start_infographic(callback: CallbackQuery, state: FSMContext):
    """Start infographic creation flow"""
    session = session_manager.get_session(callback.from_user.id)

    # Check if we already have an image from previous steps
    if session.has_image():
        await callback.message.edit_text(
            "<b>Создание инфографики</b>\n\n"
            "У вас уже загружено изображение товара.\n"
            "Использовать его или загрузить новое?",
            reply_markup=get_use_image_keyboard()
        )
        await callback.answer()
        return

    await state.set_state(InfographicStates.waiting_for_photo)

    await callback.message.edit_text(
        "<b>Создание инфографики для WB/Ozon</b>\n\n"
        "Этот процесс включает:\n"
        "1️⃣ Загрузка фото товара\n"
        "2️⃣ Анализ и SEO-оптимизация\n"
        "3️⃣ Генерация слайдов инфографики\n\n"
        "📸 <b>Шаг 1:</b> Отправьте фото товара:",
        reply_markup=get_cancel_keyboard()
    )
    await callback.answer()


def get_use_image_keyboard():
    """Keyboard for using existing image"""
    from aiogram.types import InlineKeyboardButton
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Использовать это фото", callback_data="infographic_use_existing")
    )
    builder.row(
        InlineKeyboardButton(text="📷 Загрузить новое", callback_data="infographic_new_photo")
    )
    builder.row(
        InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")
    )
    return builder.as_markup()


@router.callback_query(F.data == "infographic_use_existing")
async def use_existing_image(callback: CallbackQuery, state: FSMContext):
    """Use existing image"""
    session = session_manager.get_session(callback.from_user.id)

    if session.has_product_info():
        # Skip to slides count selection
        await state.set_state(InfographicStates.waiting_for_slides_count)
        await callback.message.edit_text(
            f"<b>Товар:</b> {session.product_name}\n"
            f"<b>Категория:</b> {session.category}\n\n"
            "Выберите количество слайдов или доверьте выбор AI:",
            reply_markup=get_slides_count_keyboard()
        )
    else:
        # Need product info
        await state.set_state(InfographicStates.waiting_for_product_name)
        await callback.message.edit_text(
            "📝 <b>Шаг 2:</b> Введите название товара:",
            reply_markup=get_cancel_keyboard()
        )
    await callback.answer()


@router.callback_query(F.data == "infographic_new_photo")
async def request_new_photo(callback: CallbackQuery, state: FSMContext):
    """Request new photo"""
    session_manager.reset_session(callback.from_user.id)
    await state.set_state(InfographicStates.waiting_for_photo)

    await callback.message.edit_text(
        "📸 Отправьте фото товара:",
        reply_markup=get_cancel_keyboard()
    )
    await callback.answer()


@router.message(InfographicStates.waiting_for_photo, F.photo)
async def receive_photo(message: Message, state: FSMContext, bot: Bot):
    """Receive product photo"""
    processing_msg = await message.answer("⏳ Загружаю изображение...")

    try:
        photo = message.photo[-1]
        file = await bot.get_file(photo.file_id)
        file_bytes = await bot.download_file(file.file_path)
        image_bytes = file_bytes.read()

        session = session_manager.get_session(message.from_user.id)
        session.original_image = image_bytes

        # Analyze image
        analysis = await nanobanana_service.analyze_product_image(image_bytes)

        await processing_msg.delete()

        if analysis:
            # Show analysis and ask for product name
            await message.answer(
                f"✅ Изображение загружено!\n\n"
                f"<b>Анализ:</b>\n{analysis[:500]}...\n\n"
                "📝 <b>Шаг 2:</b> Введите название товара:",
                reply_markup=get_cancel_keyboard()
            )
        else:
            await message.answer(
                "✅ Изображение загружено!\n\n"
                "📝 <b>Шаг 2:</b> Введите название товара:",
                reply_markup=get_cancel_keyboard()
            )

        await state.set_state(InfographicStates.waiting_for_product_name)

    except Exception as e:
        logger.error(f"Error receiving photo: {e}")
        await processing_msg.edit_text(
            "❌ Ошибка загрузки. Попробуйте другое фото.",
            reply_markup=get_cancel_keyboard()
        )


@router.message(InfographicStates.waiting_for_product_name, F.text)
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

    await state.set_state(InfographicStates.waiting_for_category)

    await message.answer(
        f"<b>Товар:</b> {product_name}\n\n"
        "📁 <b>Шаг 3:</b> Выберите категорию:",
        reply_markup=get_category_keyboard()
    )


@router.callback_query(InfographicStates.waiting_for_category, F.data.startswith("cat_"))
async def receive_category(callback: CallbackQuery, state: FSMContext):
    """Receive category"""
    if callback.data == "cat_custom":
        await state.set_state(InfographicStates.waiting_for_custom_category)
        await callback.message.edit_text(
            "Введите категорию:",
            reply_markup=get_cancel_keyboard()
        )
        await callback.answer()
        return

    category = CATEGORY_NAMES.get(callback.data, "Другое")
    session = session_manager.get_session(callback.from_user.id)
    session.category = category

    await state.set_state(InfographicStates.waiting_for_slides_count)

    await callback.message.edit_text(
        f"<b>Товар:</b> {session.product_name}\n"
        f"<b>Категория:</b> {category}\n\n"
        "🎨 <b>Шаг 4:</b> Выберите количество слайдов:",
        reply_markup=get_slides_count_keyboard()
    )
    await callback.answer()


@router.message(InfographicStates.waiting_for_custom_category, F.text)
async def receive_custom_category(message: Message, state: FSMContext):
    """Receive custom category"""
    session = session_manager.get_session(message.from_user.id)
    session.category = message.text.strip()

    await state.set_state(InfographicStates.waiting_for_slides_count)

    await message.answer(
        f"<b>Товар:</b> {session.product_name}\n"
        f"<b>Категория:</b> {session.category}\n\n"
        "🎨 <b>Шаг 4:</b> Выберите количество слайдов:",
        reply_markup=get_slides_count_keyboard()
    )


@router.callback_query(InfographicStates.waiting_for_slides_count, F.data.startswith("slides_"))
async def receive_slides_count(callback: CallbackQuery, state: FSMContext):
    """Receive slides count selection"""
    slides_data = callback.data.replace("slides_", "")

    session = session_manager.get_session(callback.from_user.id)

    if slides_data == "auto":
        num_slides = None  # Will be determined by AI
    else:
        num_slides = int(slides_data)

    await callback.answer("Анализирую и создаю план...")

    # Show processing message
    processing_msg = await callback.message.edit_text(
        "⏳ <b>Создаю план инфографики...</b>\n\n"
        "🔍 Анализирую ключевые слова\n"
        "📝 Генерирую SEO-контент\n"
        "🎨 Создаю промты для слайдов\n\n"
        "Это может занять до минуты..."
    )

    try:
        # Get full analysis
        analysis = await grok_service.generate_full_analysis(
            session.product_name,
            session.category,
            num_slides=num_slides
        )

        if analysis:
            session.full_analysis = analysis
            session.num_slides = analysis.get("num_slides", 5)
            session.style_guide = analysis.get("style_guide", "")
            session.slide_prompts = analysis.get("slide_prompts", [])

            # Format plan message
            plan_text = format_plan_preview(analysis)

            await state.set_state(InfographicStates.confirming_plan)

            await processing_msg.edit_text(
                plan_text,
                reply_markup=get_edit_plan_keyboard()
            )
        else:
            await processing_msg.edit_text(
                "❌ Не удалось создать план.\nПопробуйте позже.",
                reply_markup=get_back_to_menu_keyboard()
            )
            await state.clear()

    except Exception as e:
        logger.error(f"Error creating plan: {e}")
        await processing_msg.edit_text(
            "❌ Ошибка при создании плана.",
            reply_markup=get_back_to_menu_keyboard()
        )
        await state.clear()


def format_plan_preview(analysis: dict) -> str:
    """Format analysis result as plan preview"""
    lines = [
        "<b>План создания инфографики</b>\n",
        f"<b>Количество слайдов:</b> {analysis.get('num_slides', 5)}",
        ""
    ]

    # SEO preview
    seo = analysis.get("seo", {})
    if seo.get("title"):
        lines.append(f"<b>SEO-заголовок:</b>\n{seo['title']}\n")

    # Slides preview
    lines.append("<b>Слайды:</b>")
    for prompt in analysis.get("slide_prompts", [])[:7]:
        slide_num = prompt.get("slide", "?")
        is_main = "👑 " if prompt.get("is_main") else "   "
        text = prompt.get("text_overlay", "")[:40]
        lines.append(f"{is_main}<b>Слайд {slide_num}:</b> {text}...")

    lines.append("\n<i>Нажмите 'Генерировать' для создания изображений</i>")

    return "\n".join(lines)


@router.callback_query(InfographicStates.confirming_plan, F.data == "generate_start")
async def start_generation(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Start image generation"""
    await state.set_state(InfographicStates.generating)

    session = session_manager.get_session(callback.from_user.id)

    if not session.original_image or not session.full_analysis:
        await callback.message.edit_text(
            "❌ Данные сессии утеряны. Начните заново.",
            reply_markup=get_back_to_menu_keyboard()
        )
        await state.clear()
        await callback.answer()
        return

    await callback.answer("Начинаю генерацию...")

    processing_msg = await callback.message.edit_text(
        "🎨 <b>Генерация инфографики...</b>\n\n"
        f"Создаю {session.num_slides} слайдов...\n\n"
        "⏳ Это может занять несколько минут."
    )

    try:
        # Generate all slides
        slides = await nanobanana_service.generate_all_slides(
            product_image_bytes=session.original_image,
            slide_prompts=session.slide_prompts,
            style_guide=session.style_guide
        )

        if slides:
            session.slides_designs = slides

            # Format results
            results_text = [
                "<b>✅ Инфографика создана!</b>\n",
                f"<b>Товар:</b> {session.product_name}",
                f"<b>Слайдов:</b> {len(slides)}\n",
                "<b>Дизайн-спецификации для каждого слайда:</b>\n"
            ]

            for slide in slides:
                slide_num = slide.get("slide_num", "?")
                is_main = "👑 " if slide.get("is_main") else ""
                text = slide.get("text_overlay", "")[:50]
                results_text.append(f"{is_main}<b>Слайд {slide_num}:</b> {text}")

            results_text.append("\n<i>Дизайн-спецификации сохранены.</i>")
            results_text.append("<i>Используйте их для создания изображений в Midjourney/DALL-E.</i>")

            await processing_msg.edit_text(
                "\n".join(results_text),
                reply_markup=get_back_to_menu_keyboard()
            )

            # Send detailed specs as separate messages
            for slide in slides:
                spec_text = (
                    f"<b>Слайд {slide.get('slide_num', '?')}</b>\n"
                    f"{'👑 Главный слайд' if slide.get('is_main') else ''}\n\n"
                    f"<b>Текст:</b> {slide.get('text_overlay', '')}\n\n"
                    f"<b>Дизайн:</b>\n{slide.get('design_spec', '')[:1500]}..."
                )
                await callback.message.answer(spec_text)

        else:
            await processing_msg.edit_text(
                "❌ Не удалось создать слайды.\nПопробуйте позже.",
                reply_markup=get_back_to_menu_keyboard()
            )

    except Exception as e:
        logger.error(f"Error generating slides: {e}")
        await processing_msg.edit_text(
            "❌ Ошибка при генерации.",
            reply_markup=get_back_to_menu_keyboard()
        )

    await state.clear()


@router.callback_query(InfographicStates.confirming_plan, F.data == "edit_slides_count")
async def edit_slides_count(callback: CallbackQuery, state: FSMContext):
    """Edit slides count"""
    await state.set_state(InfographicStates.waiting_for_slides_count)

    await callback.message.edit_text(
        "Выберите новое количество слайдов:",
        reply_markup=get_slides_count_keyboard()
    )
    await callback.answer()


@router.callback_query(InfographicStates.confirming_plan, F.data == "edit_prompts")
async def edit_prompts(callback: CallbackQuery, state: FSMContext):
    """Show prompts for editing"""
    session = session_manager.get_session(callback.from_user.id)

    if not session.slide_prompts:
        await callback.answer("Промты не найдены")
        return

    # Show all prompts
    prompts_text = ["<b>Текущие промты для слайдов:</b>\n"]

    for prompt in session.slide_prompts:
        slide_num = prompt.get("slide", "?")
        is_main = "👑 " if prompt.get("is_main") else ""
        text = prompt.get("text_overlay", "")
        prompt_text = prompt.get("prompt", "")[:300]

        prompts_text.append(
            f"{is_main}<b>Слайд {slide_num}:</b>\n"
            f"Текст: {text}\n"
            f"Промт: {prompt_text}...\n"
        )

    prompts_text.append("\n<i>Для редактирования промтов обратитесь к разработчику</i>")

    await callback.message.edit_text(
        "\n".join(prompts_text),
        reply_markup=get_edit_plan_keyboard()
    )
    await callback.answer()


@router.message(InfographicStates.waiting_for_photo)
async def invalid_photo_input(message: Message):
    """Handle non-photo input"""
    await message.answer(
        "⚠️ Отправьте фотографию товара.",
        reply_markup=get_cancel_keyboard()
    )


@router.message(InfographicStates.waiting_for_product_name)
async def invalid_name_input(message: Message):
    """Handle non-text input for name"""
    await message.answer(
        "⚠️ Введите название товара текстом.",
        reply_markup=get_cancel_keyboard()
    )
