import logging
import os
import sys
from datetime import datetime
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import Message, InputFile, FSInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
import aiohttp
from config import BOT_TOKEN, ADMIN_ID, REPLICATE_API_TOKEN
from database import init_db, add_user, get_user, update_balance
from ai_generator import generate_image_with_replicate, generate_demo_image
from aiohttp import web
import threading
import asyncio

# Минимальный HTTP-сервер для health check
async def handle_health(request):
    return web.Response(text="OK")

def run_health_server():
    app = web.Application()
    app.router.add_get('/health', handle_health)
    app.router.add_get('/', handle_health)
    web.run_app(app, port=8080, host='0.0.0.0')

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Проверка токенов
if not BOT_TOKEN:
    logger.error("❌ BOT_TOKEN не найден в .env")
    sys.exit(1)

if not REPLICATE_API_TOKEN:
    logger.warning("⚠️ REPLICATE_API_TOKEN не найден. Бот будет работать в демо-режиме.")

# Инициализация бота
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Состояния
class UserState(StatesGroup):
    waiting_for_photo = State()
    waiting_for_prompt = State()

# Команда /start
@dp.message(Command("start"))
async def cmd_start(message: Message):
    user_id = message.from_user.id
    user_name = message.from_user.full_name
    
    # Добавляем пользователя в БД
    add_user(user_id, user_name)
    
    # Приветственное сообщение
    welcome_text = (
        f"👋 Привет, {user_name}!\n\n"
        f"Я бот для генерации изображений в стиле советских открыток.\n"
        f"Отправь мне фото и описание — и я создам новогоднюю открытку!\n\n"
        f"📸 Сначала отправь фото (можно селфи или портрет)\n"
        f"✏️ Затем напиши описание (например: 'Сделай новогоднюю открытку в стиле советских сказок')\n\n"
        f"🎁 Бесплатных генераций: 3\n"
        f"💎 Платных генераций: 0"
    )
    
    await message.answer(welcome_text)
    await message.answer("📸 Отправьте фото для обработки:")

# Приём фото
@dp.message(lambda message: message.photo)
async def handle_photo(message: Message, state: FSMContext):
    user_id = message.from_user.id
    
    # Сохраняем ID фото
    photo_id = message.photo[-1].file_id
    await state.update_data(photo_id=photo_id)
    
    await message.answer("✅ Фото принято! Теперь опишите, что вы хотите получить:")
    await state.set_state(UserState.waiting_for_prompt)

# Приём текстового описания
@dp.message(UserState.waiting_for_prompt)
async def handle_prompt(message: Message, state: FSMContext):
    user_id = message.from_user.id
    prompt = message.text
    
    # Проверяем баланс
    user = get_user(user_id)
    if user and user[3] <= 0:  # user[3] — бесплатные генерации
        await message.answer("❌ У вас закончились бесплатные генерации. Обратитесь к администратору.")
        return
    
    # Получаем сохранённое фото
    data = await state.get_data()
    photo_id = data.get('photo_id')
    
    if not photo_id:
        await message.answer("❌ Фото не найдено. Отправьте фото заново.")
        return
    
    # Уменьшаем баланс
    update_balance(user_id, free_uses=-1)
    
    # Информируем о начале генерации
    msg = await message.answer("🔄 Генерация изображения началась... Это займет 15-30 секунд.")
    
    try:
        # Получаем URL фото
        file = await bot.get_file(photo_id)
        file_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file.file_path}"
        
        # Генерация изображения
        if REPLICATE_API_TOKEN and REPLICATE_API_TOKEN != "ваш_токен":
            # Реальная генерация
            image_url = await generate_image_with_replicate(
                prompt=prompt,
                style="советские сказки",
                input_image_url=file_url
            )
        else:
            # Демо-режим
            image_url = await generate_demo_image()
        
        if image_url:
            # Скачиваем изображение
            async with aiohttp.ClientSession() as session:
                async with session.get(image_url) as resp:
                    if resp.status == 200:
                        image_data = await resp.read()
                        
                        # Отправляем изображение
                        await message.answer_photo(
                            types.BufferedInputFile(image_data, filename="generated.jpg"),
                            caption=(
                                f"✅ Изображение создано!\n\n"
                                f"📝 Запрос: {prompt}\n"
                                f"🎨 Стиль: Советские сказки\n"
                                f"🆓 Бесплатных осталось: {max(0, user[3]-1)}\n\n"
                                f"Хотите сгенерировать еще? Отправьте новое фото!"
                            )
                        )
                    else:
                        await message.answer("❌ Ошибка загрузки сгенерированного изображения.")
        else:
            await message.answer("❌ Ошибка генерации изображения.")
    
    except Exception as e:
        logger.error(f"Ошибка в генерации: {e}")
        await message.answer("❌ Произошла ошибка при генерации. Попробуйте позже.")
    
    # Сбрасываем состояние
    await state.clear()

# Запуск бота
async def main():
    # Инициализация БД
    init_db()
    
    logger.info("="*60)
    logger.info("✅ ЗАПУСК БОТА NANO-BANANO v2.0")
    logger.info("="*60)
    logger.info(f"✅ Бот: @NanoBananoGeneratorBot")
    logger.info(f"✅ ID бота: {await bot.get_me().id}")
    logger.info(f"✅ Имя бота: {await bot.get_me().full_name}")
    logger.info(f"✅ Админ ID: {ADMIN_ID}")
    logger.info(f"✅ База данных: users.db")
    
    if REPLICATE_API_TOKEN and REPLICATE_API_TOKEN != "ваш_токен":
        logger.info("✅ Режим: РЕАЛЬНАЯ генерация через Replicate API")
    else:
        logger.info("⚠️ Режим: ДЕМО (без реальной генерации)")
    
    logger.info("✅ Все системы готовы")
    logger.info("="*60)
    logger.info("✅ Откройте Telegram и найдите своего бота")
    logger.info("✅ Используйте команду /start")
    logger.info("="*60)
    
    # Запускаем HTTP-сервер для health check
    health_thread = threading.Thread(target=run_health_server, daemon=True)
    health_thread.start()
    logger.info("🌐 HTTP health server started on port 8080")
    
    # Запуск бота
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("📴 Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"🔥 Критическая ошибка: {e}")
