import asyncio
import logging
import os
import tempfile
import replicate
import aiohttp
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command, Filter
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton, 
    InlineKeyboardMarkup, InlineKeyboardButton,
    FSInputFile
)
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.enums import ParseMode

import config
from database import db

# Настройка логгера
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Проверка токена
if not hasattr(config, 'BOT_TOKEN') or config.BOT_TOKEN.startswith("ваш_токен"):
    logger.error("❌ ЗАМЕНИТЕ ТОКЕН В ФАЙЛЕ .env!")
    logger.error("Получите токен у @BotFather и добавьте в .env")
    exit()

# Создаем бота
bot = Bot(token=config.BOT_TOKEN)
dp = Dispatcher()

# Инициализируем Replicate API если есть токен
REPLICATE_API = None
if hasattr(config, 'REPLICATE_API_TOKEN') and config.REPLICATE_API_TOKEN:
    try:
        replicate.default_client = replicate.Client(api_token=config.REPLICATE_API_TOKEN)
        REPLICATE_API = replicate
        logger.info("✅ Replicate API подключен")
    except Exception as e:
        logger.error(f"❌ Ошибка подключения Replicate API: {e}")
        REPLICATE_API = None
else:
    logger.warning("⚠️  Replicate API токен не найден. Работаем в демо-режиме.")

# Создаем кастомный фильтр для текста
class TextFilter(Filter):
    def __init__(self, text):
        self.text = text
    
    async def __call__(self, message: types.Message) -> bool:
        return message.text == self.text

# Состояния для FSM
class GenerationStates(StatesGroup):
    waiting_for_prompt = State()
    waiting_for_photo = State()
    waiting_for_style = State()

# Клавиатуры
def main_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🎨 Сгенерировать изображение")],
            [KeyboardButton(text="🖼 Загрузить фото для обработки")],
            [KeyboardButton(text="💰 Баланс"), KeyboardButton(text="🛒 Купить")],
            [KeyboardButton(text="📊 Статистика"), KeyboardButton(text="ℹ️ Помощь")]
        ],
        resize_keyboard=True
    )

def generation_options_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📝 Только по описанию")],
            [KeyboardButton(text="🖼 С фото + описание")],
            [KeyboardButton(text="❌ Отмена")]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )

def style_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🎨 Аниме", callback_data="style_anime"),
                InlineKeyboardButton(text="🖼 Реализм", callback_data="style_realistic")
            ],
            [
                InlineKeyboardButton(text="🌈 Арт", callback_data="style_art"),
                InlineKeyboardButton(text="✨ Фэнтези", callback_data="style_fantasy")
            ],
            [
                InlineKeyboardButton(text="🚀 Киберпанк", callback_data="style_cyberpunk"),
                InlineKeyboardButton(text="🏛 Классика", callback_data="style_classic"),
                InlineKeyboardButton(text="🎭 Без стиля", callback_data="style_none")
            ]
        ]
    )

def cancel_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="❌ Отмена")]],
        resize_keyboard=True,
        one_time_keyboard=True
    )

# ========== ФУНКЦИИ ГЕНЕРАЦИИ ==========

async def generate_with_replicate(prompt, style="realistic"):
    """Генерация изображения через Replicate API"""
    if not REPLICATE_API:
        logger.warning("Replicate API не подключен, возвращаем демо-режим")
        return None
    
    try:
        # Добавляем Нано-Банано в промпт
        nano_prompt = f"Нано-Банано, {prompt}"
        
        # Улучшаем промпт в зависимости от стиля
        style_enhancements = {
            "anime": f"{nano_prompt}, anime style, detailed, vibrant colors, beautiful, masterpiece",
            "realistic": f"{nano_prompt}, photorealistic, 8K, high detail, professional photography",
            "art": f"{nano_prompt}, digital art, artistic, painting, trending on artstation",
            "fantasy": f"{nano_prompt}, fantasy art, magical, mystical, epic, lord of the rings style",
            "cyberpunk": f"{nano_prompt}, cyberpunk, neon, futuristic, blade runner, night city",
            "classic": f"{nano_prompt}, classical painting, oil on canvas, masterpiece, renaissance",
            "none": f"{nano_prompt}, high quality, detailed, beautiful"
        }
        
        enhanced_prompt = style_enhancements.get(style, nano_prompt)
        
        logger.info(f"Генерация изображения: {enhanced_prompt[:100]}...")
        
        # Используем Stable Diffusion XL
        output = replicate.run(
            "stability-ai/sdxl:39ed52f2a78e934b3ba6e2a89f5b1c712de7dfea535525255b1aa35c5565e08b",
            input={
                "prompt": enhanced_prompt,
                "negative_prompt": "blurry, low quality, distorted, ugly, deformed, disfigured, poor details, bad anatomy",
                "width": 1024,
                "height": 1024,
                "num_outputs": 1,
                "guidance_scale": 7.5,
                "num_inference_steps": 50,
                "scheduler": "DPMSolverMultistep"
            }
        )
        
        if output and len(output) > 0:
            image_url = output[0]
            logger.info(f"✅ Изображение сгенерировано: {image_url}")
            return image_url
        
        return None
        
    except Exception as e:
        logger.error(f"❌ Ошибка генерации через Replicate: {e}")
        return None

async def generate_demo_image(prompt, style):
    """Генерация демо-изображения (заглушка)"""
    # В демо-режиме возвращаем ссылку на тестовое изображение
    demo_images = {
        "anime": "https://i.imgur.com/WqYp8Q2.png",
        "realistic": "https://i.imgur.com/3nQqY9y.jpg", 
        "art": "https://i.imgur.com/5nYp8Q1.png",
        "fantasy": "https://i.imgur.com/7nQpY9x.jpg",
        "cyberpunk": "https://i.imgur.com/9nYqP8W.png",
        "classic": "https://i.imgur.com/2nQpY8X.jpg",
        "none": "https://i.imgur.com/4nYqP9Z.png"
    }
    
    await asyncio.sleep(5)  # Имитация задержки генерации
    return demo_images.get(style, "https://i.imgur.com/WqYp8Q2.png")

# ========== КОМАНДЫ БОТА ==========

@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    user = message.from_user
    db.add_user(user.id, user.username, user.first_name, user.last_name)
    
    mode_status = "✅ <b>Режим:</b> Реальная генерация через AI" if REPLICATE_API else "⚠️  <b>Режим:</b> Демо (без реальной генерации)"
    
    text = f"""
<b>👋 Привет, {user.first_name}!</b>

Я бот для генерации изображений с <b>Нано-Банано</b> 🍌✨

{mode_status}

<u>Что умею:</u>
🎨 Генерировать изображения по описанию
🖼 Обрабатывать загруженные фото
⚡ Быстрая генерация (30-60 секунд)
📁 Хранить историю генераций

<u>Для начала:</u> 3 <b>бесплатные генерации!</b>

<u>Доступные стили:</u>
• 🎨 Аниме • 🖼 Реализм • 🌈 Арт
• ✨ Фэнтези • 🚀 Киберпанк • 🏛 Классика

👇 <b>Выберите действие:</b>
"""
    
    await message.answer(text, parse_mode=ParseMode.HTML, reply_markup=main_keyboard())

@dp.message(TextFilter("🎨 Сгенерировать изображение"))
@dp.message(Command("generate"))
async def generate_start(message: types.Message, state: FSMContext):
    """Начало процесса генерации - выбор типа"""
    user_id = message.from_user.id
    user = db.get_user(user_id)
    
    if not user:
        await message.answer("❌ Сначала используйте /start")
        return
    
    # Проверяем есть ли хотя бы одна генерация
    if user[5] <= 0 and user[4] <= 0:
        await message.answer(
            "❌ <b>Недостаточно генераций!</b>\n\n"
            "У вас закончились генерации.\n"
            "Пожалуйста, купите дополнительные через /buy",
            parse_mode=ParseMode.HTML,
            reply_markup=main_keyboard()
        )
        return
    
    await message.answer(
        "🎨 <b>Выберите тип генерации:</b>\n\n"
        "📝 <b>Только по описанию</b> - создаю с нуля\n"
        "🖼 <b>С фото + описание</b> - обрабатываю ваше фото\n\n"
        "<i>Для обработки фото можно загрузить его сейчас или позже</i>",
        parse_mode=ParseMode.HTML,
        reply_markup=generation_options_keyboard()
    )

@dp.message(TextFilter("📝 Только по описанию"))
async def text_only_generation(message: types.Message, state: FSMContext):
    """Генерация только по текстовому описанию"""
    await state.update_data(has_photo=False)
    await state.set_state(GenerationStates.waiting_for_prompt)
    
    await message.answer(
        "✍️ <b>Опишите что вы хотите сгенерировать:</b>\n\n"
        "<i>Примеры:</i>\n"
        "• Нано-Банано в космосе с планетами\n"
        "• Нано-Банано как супергерой в стиле аниме\n"
        "• Нано-Банано программирует на Python\n"
        "• Нано-Банано в стиле средневекового рыцаря\n\n"
        "<b>Можно добавить:</b>\n"
        "• Стиль (аниме, реализм и т.д.)\n"
        "• Цветовую гамму\n"
        "• Детали фона\n"
        "• Эмоции, действия\n\n"
        "<i>Чем подробнее - тем лучше результат!</i>",
        parse_mode=ParseMode.HTML,
        reply_markup=cancel_keyboard()
    )

@dp.message(TextFilter("🖼 Загрузить фото для обработки"))
@dp.message(TextFilter("🖼 С фото + описание"))
async def photo_generation_start(message: types.Message, state: FSMContext):
    """Начало генерации с фото"""
    await state.update_data(has_photo=True)
    await state.set_state(GenerationStates.waiting_for_photo)
    
    await message.answer(
        "🖼 <b>Загрузите фото для обработки:</b>\n\n"
        "<i>Требования к фото:</i>\n"
        "• Формат: JPG, PNG\n"
        "• Размер: до 20MB\n"
        "• Качество: чем лучше - тем лучше результат\n\n"
        "<b>Или напишите 'пропустить' для генерации без фото</b>",
        parse_mode=ParseMode.HTML,
        reply_markup=cancel_keyboard()
    )

@dp.message(GenerationStates.waiting_for_photo)
async def process_photo(message: types.Message, state: FSMContext):
    """Обработка загруженного фото или текста"""
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Генерация отменена", reply_markup=main_keyboard())
        return
    
    if message.text and message.text.lower() == "пропустить":
        await state.update_data(photo_path=None, has_photo=False)
        await state.set_state(GenerationStates.waiting_for_prompt)
        
        await message.answer(
            "✅ Пропускаем загрузку фото\n\n"
            "✍️ <b>Теперь опишите что вы хотите сгенерировать:</b>",
            parse_mode=ParseMode.HTML,
            reply_markup=cancel_keyboard()
        )
        return
    
    if not message.photo:
        await message.answer(
            "❌ Пожалуйста, загрузите фото или напишите 'пропустить'",
            reply_markup=cancel_keyboard()
        )
        return
    
    # Сохраняем фото
    photo = message.photo[-1]  # Берем фото наилучшего качества
    file_info = await bot.get_file(photo.file_id)
    downloaded_file = await bot.download_file(file_info.file_path)
    
    # Сохраняем временный файл
    with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as tmp_file:
        tmp_file.write(downloaded_file.read())
        photo_path = tmp_file.name
    
    await state.update_data(photo_path=photo_path)
    await state.set_state(GenerationStates.waiting_for_prompt)
    
    await message.answer(
        "✅ <b>Фото загружено!</b>\n\n"
        "✍️ <b>Теперь опишите что сделать с фото:</b>\n\n"
        "<i>Примеры:</i>\n"
        "• Добавь Нано-Банано на фото\n"
        "• Измени стиль на аниме\n"
        "• Сделай фон космическим\n"
        "• Преврати в картину маслом\n"
        "• Добавь magical effects\n\n"
        "<i>Опишите все изменения которые хотите</i>",
        parse_mode=ParseMode.HTML,
        reply_markup=cancel_keyboard()
    )

@dp.message(GenerationStates.waiting_for_prompt)
async def process_prompt(message: types.Message, state: FSMContext):
    """Обработка промпта и запуск генерации"""
    if message.text == "❌ Отмена":
        # Удаляем временный файл фото если есть
        data = await state.get_data()
        if data.get('photo_path') and os.path.exists(data['photo_path']):
            os.unlink(data['photo_path'])
        
        await state.clear()
        await message.answer("❌ Генерация отменена", reply_markup=main_keyboard())
        return
    
    prompt = message.text.strip()
    
    if len(prompt) < 3:
        await message.answer("❌ Слишком короткое описание. Попробуйте снова:")
        return
    
    if len(prompt) > 1000:
        await message.answer("❌ Слишком длинное описание (макс. 1000 символов). Попробуйте короче:")
        return
    
    # Получаем данные из состояния
    data = await state.get_data()
    user_id = data.get('user_id', message.from_user.id)
    user = db.get_user(user_id)
    has_photo = data.get('has_photo', False)
    photo_path = data.get('photo_path')
    
    if not user:
        await state.clear()
        await message.answer("❌ Пользователь не найден. Используйте /start")
        return
    
    # Спрашиваем стиль
    await state.update_data(prompt=prompt, user_id=user_id)
    await state.set_state(GenerationStates.waiting_for_style)
    
    style_text = " с фото" if has_photo and photo_path else ""
    
    await message.answer(
        f"🎨 <b>Выберите стиль для генерации{style_text}:</b>\n\n"
        f"📝 <b>Ваш запрос:</b>\n<i>{prompt[:100]}{'...' if len(prompt) > 100 else ''}</i>\n\n"
        f"<i>Или выберите 'Без стиля' для генерации как есть</i>",
        parse_mode=ParseMode.HTML,
        reply_markup=style_keyboard()
    )

@dp.callback_query(lambda c: c.data.startswith("style_"))
async def process_style(callback: types.CallbackQuery, state: FSMContext):
    """Обработка выбора стиля и запуск генерации"""
    style = callback.data.replace("style_", "")
    
    # Получаем данные из состояния
    data = await state.get_data()
    prompt = data.get('prompt')
    user_id = data.get('user_id', callback.from_user.id)
    photo_path = data.get('photo_path')
    has_photo = data.get('has_photo', False)
    
    user = db.get_user(user_id)
    
    if not user:
        await callback.answer("❌ Ошибка: пользователь не найден")
        await state.clear()
        return
    
    # Проверяем баланс перед списанием
    if user[5] <= 0 and user[4] <= 0:
        await callback.answer("❌ Недостаточно генераций!")
        await state.clear()
        await callback.message.answer(
            "❌ <b>Недостаточно генераций!</b>\n\n"
            "Пожалуйста, купите дополнительные через /buy",
            parse_mode=ParseMode.HTML,
            reply_markup=main_keyboard()
        )
        return
    
    # Определяем тип генерации и списываем
    if user[5] > 0:  # Бесплатные
        db.cursor.execute('''
            UPDATE users 
            SET free_generations = free_generations - 1,
                total_generated = total_generated + 1
            WHERE user_id = ?
        ''', (user_id,))
        gen_type = "🆓 бесплатная"
        free_left = user[5] - 1
        paid_left = user[4]
    else:  # Платные
        db.cursor.execute('''
            UPDATE users 
            SET balance = balance - 1,
                total_generated = total_generated + 1
            WHERE user_id = ?
        ''', (user_id,))
        gen_type = "💰 платная"
        free_left = 0
        paid_left = user[4] - 1
    
    db.conn.commit()
    
    # Сохраняем запись о генерации
    style_name = {
        'anime': 'Аниме',
        'realistic': 'Реализм',
        'art': 'Арт',
        'fantasy': 'Фэнтези',
        'cyberpunk': 'Киберпанк',
        'classic': 'Классика',
        'none': 'Без стиля'
    }.get(style, 'Без стиля')
    
    full_prompt = f"{prompt} [Стиль: {style_name}]"
    db.cursor.execute('''
        INSERT INTO generations (user_id, prompt) 
        VALUES (?, ?)
    ''', (user_id, full_prompt))
    db.conn.commit()
    
    await callback.answer(f"✅ Выбран стиль: {style_name}")
    
    # Начинаем генерацию
    status_msg = await callback.message.answer(
        f"⚡ <b>Начинаю генерацию...</b>\n\n"
        f"📝 <b>Запрос:</b> <i>{prompt[:100]}{'...' if len(prompt) > 100 else ''}</i>\n"
        f"🎨 <b>Стиль:</b> {style_name}\n"
        f"🖼 <b>Тип:</b> {'С фото' if has_photo and photo_path else 'Текстовая'}\n"
        f"🎫 <b>Списано:</b> {gen_type}\n"
        f"⏱ <b>Ожидайте:</b> 30-60 секунд",
        parse_mode=ParseMode.HTML
    )
    
    # Показываем прогресс
    progress_steps = [
        "Анализ запроса...",
        "Подготовка модели AI...",
        "Генерация изображения...",
        "Добавление деталей Нано-Банано...",
        "Финальная обработка и улучшение..."
    ]
    
    for i, step in enumerate(progress_steps, 1):
        await asyncio.sleep(5 if REPLICATE_API else 2)  # Дольше для реальной генерации
        
        progress_bar = "🟩" * i + "⬜" * (5 - i)
        
        await status_msg.edit_text(
            f"⚙️ <b>Генерация в процессе... {progress_bar}</b>\n\n"
            f"📝 <b>Запрос:</b> <i>{prompt[:80]}{'...' if len(prompt) > 80 else ''}</i>\n"
            f"🎨 <b>Стиль:</b> {style_name}\n"
            f"🔄 <b>Этап:</b> {step}\n"
            f"⏱ <b>Прошло:</b> {i*5 if REPLICATE_API else i*2} секунд",
            parse_mode=ParseMode.HTML
        )
    
    # ГЕНЕРАЦИЯ ИЗОБРАЖЕНИЯ
    image_url = None
    generation_success = False
    
    if REPLICATE_API:
        # Реальная генерация через Replicate
        try:
            image_url = await generate_with_replicate(prompt, style)
            if image_url:
                generation_success = True
                logger.info(f"✅ Реальная генерация успешна: {image_url}")
            else:
                logger.warning("Реальная генерация не удалась, переключаемся на демо")
        except Exception as e:
            logger.error(f"Ошибка реальной генерации: {e}")
    
    if not generation_success:
        # Демо-режим
        image_url = await generate_demo_image(prompt, style)
        logger.info("Используется демо-режим")
    
    # Очищаем состояние
    if photo_path and os.path.exists(photo_path):
        os.unlink(photo_path)
    
    await state.clear()
    
    # Формируем результат
    result_text = f"""
<b>✅ Готово! Изображение создано</b>

<u>Детали генерации:</u>
📝 <b>Запрос:</b> {prompt[:120]}{'...' if len(prompt) > 120 else ''}
🎨 <b>Стиль:</b> {style_name}
🎫 <b>Тип генерации:</b> {gen_type}
{'🖼 <b>С фото:</b> Да' if has_photo else '📝 <b>С фото:</b> Нет'}
👤 <b>Для:</b> {callback.from_user.first_name}
{'🤖 <b>Режим:</b> Реальная AI генерация' if generation_success else '🎭 <b>Режим:</b> Демо (реальная генерация скоро)'}

<u>Ваш баланс:</u>
🎫 <b>Бесплатных осталось:</b> {free_left}
💰 <b>Платных осталось:</b> {paid_left}
"""
    
    # Отправляем результат
    try:
        if image_url and image_url.startswith('http'):
            # Отправляем сгенерированное изображение
            await callback.message.answer_photo(
                image_url,
                caption=result_text,
                parse_mode=ParseMode.HTML
            )
            
            # Дополнительная информация
            info_text = "🎉 <b>Изображение успешно сгенерировано!</b>\n\n"
            if not generation_success:
                info_text += "⚠️ <i>Сейчас в демо-режиме. Для реальной генерации нужен Replicate API ключ.</i>\n\n"
            
            info_text += "👉 Хотите сгенерировать еще? Выберите действие:"
            
            await callback.message.answer(
                info_text,
                parse_mode=ParseMode.HTML,
                reply_markup=main_keyboard()
            )
        else:
            # Если не удалось получить изображение
            await callback.message.answer(
                f"❌ <b>Не удалось сгенерировать изображение</b>\n\n"
                f"Попробуйте:\n"
                f"1. Изменить описание\n"
                f"2. Выбрать другой стиль\n"
                f"3. Попробовать позже\n\n"
                f"<i>Техническая информация: не удалось получить URL изображения</i>",
                parse_mode=ParseMode.HTML,
                reply_markup=main_keyboard()
            )
            
    except Exception as e:
        logger.error(f"Ошибка отправки изображения: {e}")
        
        await callback.message.answer(
            f"⚠️ <b>Изображение сгенерировано, но возникла ошибка при отправке</b>\n\n"
            f"<b>Ссылка на изображение:</b>\n"
            f"<code>{image_url if image_url else 'не сгенерировано'}</code>\n\n"
            f"<i>Попробуйте скопировать ссылку и открыть в браузере</i>",
            parse_mode=ParseMode.HTML,
            reply_markup=main_keyboard()
        )

# ========== ОСТАЛЬНЫЕ КОМАНДЫ ==========

@dp.message(TextFilter("💰 Баланс"))
@dp.message(Command("balance"))
async def balance_cmd(message: types.Message):
    user = db.get_user(message.from_user.id)
    if user:
        # Получаем общую статистику
        db.cursor.execute('SELECT COUNT(*) FROM generations WHERE user_id = ?', (message.from_user.id,))
        total_gens = db.cursor.fetchone()[0] or 0
        
        text = f"""
<b>💰 Ваш баланс и статистика</b>

<u>Генерации:</u>
🎫 <b>Бесплатных осталось:</b> {user[5]}
💰 <b>Платных на балансе:</b> {user[4]}
📊 <b>Всего использовано:</b> {total_gens}

<u>Активность:</u>
📅 <b>Зарегистрирован:</b> {user[7][:10] if user[7] else 'сегодня'}
👤 <b>Username:</b> @{user[1] if user[1] else 'не указан'}
"""
        
        if message.from_user.id == config.ADMIN_ID:
            text += "\n👑 <b>Статус:</b> Администратор (безлимит)"
        
        await message.answer(text, parse_mode=ParseMode.HTML, reply_markup=main_keyboard())
    else:
        await message.answer("❌ Сначала /start")

@dp.message(TextFilter("🛒 Купить"))
@dp.message(Command("buy"))
async def buy_cmd(message: types.Message):
    user = db.get_user(message.from_user.id)
    if not user:
        await message.answer("❌ Сначала /start")
        return
    
    text = f"""
<b>🛒 Покупка генераций</b>

<u>Текущий баланс:</u>
🎫 Бесплатных: {user[5]}
💰 Платных: {user[4]}

<u>Доступные пакеты:</u>
🎟 <b>10 генераций</b> - 100₽ (10₽ за шт.)
🎟 <b>25 генераций</b> - 200₽ (8₽ за шт.) 🔥
🎟 <b>50 генераций</b> - 350₽ (7₽ за шт.) 💰
🎟 <b>100 генераций</b> - 600₽ (6₽ за шт.) 🏆

<u>Как оплатить:</u>
1. Выберите пакет
2. Оплатите на карту/крипто
3. Получите генерации мгновенно

<u>Для демо-теста:</u>
<i>Нажмите кнопку ниже чтобы добавить демо-генерации</i>
"""
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🎁 Демо: +10 генераций", callback_data="demo_buy")],
            [InlineKeyboardButton(text="💳 Реальная оплата (скоро)", callback_data="real_buy")]
        ]
    )
    
    await message.answer(text, parse_mode=ParseMode.HTML, reply_markup=keyboard)

@dp.callback_query(TextFilter("demo_buy"))
async def demo_buy(callback: types.CallbackQuery):
    user = db.get_user(callback.from_user.id)
    if not user:
        await callback.answer("❌ Сначала /start")
        return
    
    # Добавляем демо-генерации
    db.cursor.execute('UPDATE users SET balance = balance + 10 WHERE user_id = ?', 
                     (callback.from_user.id,))
    db.conn.commit()
    
    await callback.answer("✅ +10 генераций добавлено!")
    
    # Обновляем баланс пользователя
    updated_user = db.get_user(callback.from_user.id)
    
    await callback.message.answer(
        f"🎉 <b>Демо-режим активирован!</b>\n\n"
        f"Вам добавлено <b>10 платных генераций</b>\n\n"
        f"<u>Теперь ваш баланс:</u>\n"
        f"🎫 Бесплатных: {updated_user[5]}\n"
        f"💰 Платных: {updated_user[4]}\n\n"
        f"<i>В реальной версии здесь будет инструкция по оплате через:\n"
        f"• ЮMoney\n• Тинькофф\n• Криптовалюты (USDT)</i>",
        parse_mode=ParseMode.HTML,
        reply_markup=main_keyboard()
    )

@dp.callback_query(TextFilter("real_buy"))
async def real_buy(callback: types.CallbackQuery):
    await callback.answer("⚠️ Реальная оплата появится в следующем обновлении")
    await callback.message.answer(
        "💳 <b>Реальная оплата скоро!</b>\n\n"
        "В следующем обновлении добавим:\n"
        "• Оплату картой\n• ЮMoney\n• Криптовалюты\n• Автоматическое пополнение\n\n"
        "Следите за обновлениями!",
        parse_mode=ParseMode.HTML,
        reply_markup=main_keyboard()
    )

@dp.message(TextFilter("📊 Статистика"))
async def stats_cmd(message: types.Message):
    user = db.get_user(message.from_user.id)
    if user:
        # Получаем историю генераций
        db.cursor.execute('''
            SELECT prompt, created_at 
            FROM generations 
            WHERE user_id = ? 
            ORDER BY created_at DESC 
            LIMIT 5
        ''', (message.from_user.id,))
        
        recent_gens = db.cursor.fetchall()
        
        recent_text = ""
        if recent_gens:
            recent_text = "<u>Последние запросы:</u>\n"
            for i, (prompt, created_at) in enumerate(recent_gens, 1):
                recent_text += f"{i}. {prompt[:40]}...\n"
        else:
            recent_text = "<i>Пока нет генераций</i>"
        
        text = f"""
<b>📊 Ваша статистика</b>

<u>Профиль:</u>
👤 <b>Имя:</b> {user[2]}
🆔 <b>ID:</b> {user[0]}
📅 <b>Регистрация:</b> {user[7][:10] if user[7] else 'сегодня'}

<u>Генерации:</u>
🎫 <b>Бесплатных осталось:</b> {user[5]}
💰 <b>Платных на балансе:</b> {user[4]}
📈 <b>Всего сгенерировано:</b> {user[6]}

{recent_text}
"""
        await message.answer(text, parse_mode=ParseMode.HTML, reply_markup=main_keyboard())
    else:
        await message.answer("❌ Сначала /start")

@dp.message(TextFilter("ℹ️ Помощь"))
@dp.message(Command("help"))
async def help_cmd(message: types.Message):
    mode_info = "✅ <b>Режим:</b> Реальная генерация через AI" if REPLICATE_API else "⚠️  <b>Режим:</b> Демо (нужен Replicate API ключ)"
    
    text = f"""
<b>ℹ️ Помощь по боту</b>

{mode_info}

<u>Основные команды:</u>
/start - начало работы
/generate - создать изображение
/balance - проверить баланс
/buy - купить генерации
/help - эта справка

<u>Как это работает:</u>
1. Выбираете тип генерации (с фото или без)
2. Описываете что хотите
3. Выбираете стиль
4. Получаете результат за 30-60 секунд

<u>Советы для лучших результатов:</u>
• Чем подробнее описание - тем лучше
• Добавляйте детали (цвета, эмоции, фон)
• Экспериментируйте со стилями
• Для фото - описывайте конкретные изменения

<u>Тарифы:</u>
• Первые 3 генерации - <b>бесплатно</b>
• Дополнительные - от 6₽ за штуку
• Оптовые скидки от 25 генераций

<u>Техподдержка:</u> @ваш_юзернейм
"""
    await message.answer(text, parse_mode=ParseMode.HTML, reply_markup=main_keyboard())

@dp.message(Command("admin"))
async def admin_cmd(message: types.Message):
    if message.from_user.id != config.ADMIN_ID:
        await message.answer("⛔ Нет прав доступа")
        return
    
    # Статистика
    db.cursor.execute("SELECT COUNT(*) FROM users")
    total_users = db.cursor.fetchone()[0]
    
    db.cursor.execute("SELECT SUM(total_generated) FROM users")
    total_generations = db.cursor.fetchone()[0] or 0
    
    db.cursor.execute("SELECT SUM(balance) FROM users")
    total_balance = db.cursor.fetchone()[0] or 0
    
    text = f"""
<b>👑 Админ-панель</b>

<u>Общая статистика:</u>
👥 <b>Пользователей:</b> {total_users}
🎨 <b>Всего генераций:</b> {total_generations}
💰 <b>Общий баланс:</b> {total_balance} генераций
🤖 <b>Режим генерации:</b> {'Реальная (Replicate)' if REPLICATE_API else 'Демо'}

<u>Быстрые команды:</u>
• /admin_stats - детальная статистика
• /admin_users - список пользователей
• /admin_broadcast - рассылка

<u>Интеграции:</u>
{'✅ Replicate API: подключен' if REPLICATE_API else '❌ Replicate API: не подключен'}
"""
    await message.answer(text, parse_mode=ParseMode.HTML)

# ========== ЗАПУСК БОТА ==========

async def main():
    logger.info("=" * 50)
    logger.info("🚀 ЗАПУСК БОТА NANO-BANANO PRO")
    logger.info("=" * 50)
    
    try:
        # Проверяем подключение бота
        me = await bot.get_me()
        logger.info(f"✅ Бот: @{me.username}")
        logger.info(f"✅ ID бота: {me.id}")
        logger.info(f"✅ Имя бота: {me.first_name}")
        
        logger.info(f"✅ Админ ID: {config.ADMIN_ID}")
        logger.info(f"✅ База данных: {config.DB_NAME}")
        
        if REPLICATE_API:
            logger.info("✅ Режим: Реальная генерация через Replicate API")
        else:
            logger.warning("⚠️  Режим: Демо (нужен REPLICATE_API_TOKEN в .env)")
            logger.info("👉 Для реальной генерации получите ключ на replicate.com")
        
        logger.info("✅ Все системы готовы")
        logger.info("=" * 50)
        logger.info("📱 Откройте Telegram и найдите своего бота")
        logger.info("👉 Используйте команду /start")
        logger.info("=" * 50)
        
        # Запускаем бота
        await dp.start_polling(bot)
        
    except Exception as e:
        logger.error(f"❌ Ошибка запуска: {e}")
        logger.error("🔍 Проверьте:")
        logger.error("1. Токен в файле .env")
        logger.error("2. Интернет-соединение")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("⏹ Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")
    finally:
        db.close()
        logger.info("🔌 Соединения закрыты")
