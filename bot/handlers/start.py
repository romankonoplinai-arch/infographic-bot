from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from bot.keyboards.menus import get_main_menu, get_back_to_menu_keyboard
from bot.models.session import session_manager

router = Router()

WELCOME_MESSAGE = """
<b>Добро пожаловать в бот создания инфографики для маркетплейсов!</b>

Я помогу вам создать профессиональную инфографику для товаров на Wildberries и Ozon.

<b>Что я умею:</b>

🖼 <b>Убрать фон</b> - удаление фона с фото товара

🔍 <b>Ключевые слова</b> - поиск релевантных ключевых слов для SEO

📝 <b>SEO-описание</b> - генерация оптимизированных описаний для карточек

🎨 <b>Создать инфографику</b> - полный цикл создания продающих карточек товара

Выберите нужную функцию:
"""


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    """Handle /start command"""
    # Reset any existing state
    await state.clear()

    # Reset session
    session_manager.reset_session(message.from_user.id)

    await message.answer(
        WELCOME_MESSAGE,
        reply_markup=get_main_menu()
    )


@router.message(Command("help"))
async def cmd_help(message: Message):
    """Handle /help command"""
    help_text = """
<b>Справка по боту</b>

<b>Команды:</b>
/start - Главное меню
/help - Эта справка

<b>Функции:</b>

<b>1. Убрать фон</b>
Отправьте фото товара, и бот удалит фон, оставив только товар.

<b>2. Ключевые слова</b>
Введите название товара и категорию - получите список ключевых слов для продвижения на WB/Ozon.

<b>3. SEO-описание</b>
На основе товара и ключевых слов создается:
• SEO-заголовок
• Буллеты для карточки
• Полное описание товара

<b>4. Создать инфографику</b>
Полный цикл:
1. Загрузка фото товара
2. Удаление фона
3. Анализ и SEO
4. Генерация слайдов инфографики

<b>Советы:</b>
• Используйте качественные фото товара
• Указывайте точную категорию товара
• Проверяйте и корректируйте промты перед генерацией
"""
    await message.answer(help_text, reply_markup=get_back_to_menu_keyboard())


@router.message(Command("menu"))
async def cmd_menu(message: Message, state: FSMContext):
    """Handle /menu command"""
    await state.clear()
    await message.answer(
        "Главное меню:",
        reply_markup=get_main_menu()
    )


@router.callback_query(F.data == "main_menu")
async def callback_main_menu(callback: CallbackQuery, state: FSMContext):
    """Handle main menu callback"""
    await state.clear()
    session_manager.reset_session(callback.from_user.id)

    await callback.message.edit_text(
        WELCOME_MESSAGE,
        reply_markup=get_main_menu()
    )
    await callback.answer()


@router.callback_query(F.data == "cancel")
async def callback_cancel(callback: CallbackQuery, state: FSMContext):
    """Handle cancel callback - return to main menu"""
    await state.clear()
    session_manager.reset_session(callback.from_user.id)

    await callback.message.edit_text(
        "Действие отменено.\n\n" + WELCOME_MESSAGE,
        reply_markup=get_main_menu()
    )
    await callback.answer("Отменено")
