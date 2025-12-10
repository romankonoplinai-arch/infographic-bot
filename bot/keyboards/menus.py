from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


def get_main_menu() -> InlineKeyboardMarkup:
    """Main menu keyboard - new structure"""
    builder = InlineKeyboardBuilder()

    # 1. Photo editor (remove bg + edit)
    builder.row(
        InlineKeyboardButton(
            text="✏️ Умный редактор фото",
            callback_data="edit_photo"
        )
    )
    # 2. SEO + slide prompts
    builder.row(
        InlineKeyboardButton(
            text="📝 SEO + план слайдов",
            callback_data="seo_slides"
        )
    )
    # 3. First slide generation (3 variants)
    builder.row(
        InlineKeyboardButton(
            text="🎨 Создать первый слайд",
            callback_data="first_slide"
        )
    )
    # 4. Slides from reference
    builder.row(
        InlineKeyboardButton(
            text="📑 Слайды по референсу",
            callback_data="slides_from_ref"
        )
    )
    # 5. Free image generation
    builder.row(
        InlineKeyboardButton(
            text="🖼 Генерация по промпту",
            callback_data="free_image"
        )
    )
    # 6. Keywords (keep)
    builder.row(
        InlineKeyboardButton(
            text="🔍 Найти ключевые слова",
            callback_data="keywords"
        )
    )

    return builder.as_markup()


def get_cancel_keyboard() -> InlineKeyboardMarkup:
    """Cancel action keyboard"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="❌ Отмена",
            callback_data="cancel"
        )
    )
    return builder.as_markup()


def get_back_to_menu_keyboard() -> InlineKeyboardMarkup:
    """Back to main menu keyboard"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="🏠 В главное меню",
            callback_data="main_menu"
        )
    )
    return builder.as_markup()


def get_confirm_keyboard(confirm_data: str = "confirm", cancel_data: str = "cancel") -> InlineKeyboardMarkup:
    """Confirm/Cancel keyboard"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Подтвердить", callback_data=confirm_data),
        InlineKeyboardButton(text="❌ Отмена", callback_data=cancel_data)
    )
    return builder.as_markup()


def get_slides_count_keyboard() -> InlineKeyboardMarkup:
    """Select number of slides keyboard"""
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(text="3", callback_data="slides_3"),
        InlineKeyboardButton(text="4", callback_data="slides_4"),
        InlineKeyboardButton(text="5", callback_data="slides_5"),
    )
    builder.row(
        InlineKeyboardButton(text="6", callback_data="slides_6"),
        InlineKeyboardButton(text="7", callback_data="slides_7"),
        InlineKeyboardButton(text="🤖 Авто", callback_data="slides_auto"),
    )
    builder.row(
        InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")
    )

    return builder.as_markup()


def get_category_keyboard() -> InlineKeyboardMarkup:
    """Popular categories for WB/Ozon"""
    builder = InlineKeyboardBuilder()

    categories = [
        ("👕 Одежда", "cat_clothing"),
        ("👟 Обувь", "cat_shoes"),
        ("📱 Электроника", "cat_electronics"),
        ("🏠 Дом и сад", "cat_home"),
        ("💄 Красота", "cat_beauty"),
        ("🧸 Детские товары", "cat_kids"),
        ("🏋️ Спорт", "cat_sport"),
        ("🛠 Инструменты", "cat_tools"),
    ]

    for i in range(0, len(categories), 2):
        row = [InlineKeyboardButton(text=categories[i][0], callback_data=categories[i][1])]
        if i + 1 < len(categories):
            row.append(InlineKeyboardButton(text=categories[i + 1][0], callback_data=categories[i + 1][1]))
        builder.row(*row)

    builder.row(
        InlineKeyboardButton(text="✏️ Ввести свою", callback_data="cat_custom")
    )
    builder.row(
        InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")
    )

    return builder.as_markup()


def get_edit_plan_keyboard() -> InlineKeyboardMarkup:
    """Edit infographic plan keyboard"""
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(text="✅ Генерировать", callback_data="generate_start"),
    )
    builder.row(
        InlineKeyboardButton(text="📝 Изменить кол-во слайдов", callback_data="edit_slides_count"),
    )
    builder.row(
        InlineKeyboardButton(text="✏️ Редактировать промты", callback_data="edit_prompts"),
    )
    builder.row(
        InlineKeyboardButton(text="❌ Отмена", callback_data="cancel"),
    )

    return builder.as_markup()


CATEGORY_NAMES = {
    "cat_clothing": "Одежда",
    "cat_shoes": "Обувь",
    "cat_electronics": "Электроника",
    "cat_home": "Дом и сад",
    "cat_beauty": "Красота и здоровье",
    "cat_kids": "Детские товары",
    "cat_sport": "Спорт и отдых",
    "cat_tools": "Инструменты",
}
