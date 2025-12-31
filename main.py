import logging
import sys
import threading
import asyncio
from aiohttp import web

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN, ADMIN_ID, REPLICATE_API_TOKEN
from database import init_db, add_user, get_user, update_balance
from ai_generator import generate_image_with_replicate, generate_demo_image

# ==================== HTTP SERVER FOR RENDER HEALTH CHECK ====================
async def handle_health(request):
    """Health check endpoint для Render"""
    return web.Response(text="OK")

def run_health_server():
    """Запуск HTTP-сервера в отдельном потоке"""
    app = web.Application()
    app.router.add_get('/health', handle_health)
    app.router.add_get('/', handle_health)
    web.run_app(app, port=10000, host='0.0.0.0')

# ==================== LOGGING SETUP ====================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# ==================== BOT INITIALIZATION ====================
# Проверка токенов
if not BOT_TOKEN:
    logger.error("❌ BOT_TOKEN не найден в .env")
    sys.exit(1)

bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# ==================== STATES ====================
class UserState(StatesGroup):
    waiting_for_photo = State()
    waiting_for_prompt = State()

# ==================== COMMAND HANDLERS ====================
@dp.message(Command("start"))
async def cmd_start(message: Message):
    """Обработчик команды /start"""
    user_id = message.from_user.id
    user_name = message.from_user.full_name or "Пользователь"
    
    # Добавляем пользователя в БД
    add_user(user_id, user_name)
    
    welcome_text = (
        f"👋 Привет, {user_name}!\n\n"
        f"Я бот для генерации изображений в стиле советских открыток.\n"
        f"Отправь мне фото и описание — и я создам новогоднюю открытку!\n\n"
        f"📸 Сначала отправь фото (можно селфи или портрет)\n"
        f"✏️ Затем напиши описание (например: 'Сделай новогоднюю открытку')\n\n"
        f"🎁 Бесплатных генераций: 3\n"
        f"💎 Платных генераций: 0"
    )
    
    await message.answer(welcome_text)
    await message.answer("📸 Отправьте фото для обработки:")

@dp.message(lambda message: message.photo)
async def handle_photo(message: Message, state: FSMContext):
    """Обработчик загрузки фото"""
    user_id = message.from_user.id
    
    # Сохраняем ID фото
    photo_id = message.photo[-1].file_id
    await state.update_data(photo_id=photo_id)
    
    await message.answer("✅ Фото принято! Теперь опишите, что вы хотите получить:")
    await state.set_state(UserState.waiting_for_prompt)

@dp.message(UserState.waiting_for_prompt)
async def handle_prompt(message: Message, state: FSMContext):
    """Обработчик текстового описания"""
    user_id = message.from_user.id
    prompt = message.text
    
    # Проверяем баланс
    user = get_user(user_id)
    if user and user[3] <= 0:  # user[3] — бесплатные генерации
        await message.answer("❌ У вас закончились бесплатные генерации.")
        await state.clear()
        return
    
    # Получаем сохранённое фото
    data = await state.get_data()
    photo_id = data.get('photo_id')
    
    if not photo_id:
        await message.answer("❌ Фото не найдено. Отправьте фото заново.")
        await state.clear()
        return
    
    # Уменьшаем баланс
    update_balance(user_id, free_uses=-1)
    
    # Информируем о начале генерации
    msg = await message.answer("🔄 Генерация изображения... Это займет 15-30 секунд.")
    
    try:
        # Получаем URL фото
        file = await bot.get_file(photo_id)
        file_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file.file_path}"
        
        # Генерация изображения
        if REPLICATE_API_TOKEN and REPLICATE_API_TOKEN != "ваш_токен":
            image_url = await generate_image_with_replicate(
                prompt=prompt,
                style="советские сказки",
                input_image_url=file_url
            )
        else:
            image_url = await generate_demo_image()
        
        if image_url:
            # Скачиваем изображение
            import aiohttp
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
                                f"🆓 Бесплатных осталось: {max(0, (user[3] if user else 3) - 1)}\n\n"
                                f"Хотите сгенерировать еще? Отправьте новое фото!"
                            )
                        )
                    else:
                        await message.answer("❌ Ошибка загрузки изображения.")
        else:
            await message.answer("❌ Ошибка генерации.")
    
    except Exception as e:
        logger.error(f"Ошибка генерации: {e}")
        await message.answer("❌ Произошла ошибка. Попробуйте позже.")
    
    # Сбрасываем состояние
    await state.clear()

# ==================== MAIN FUNCTION ====================
async def main():
    """Основная функция запуска бота"""
    # Инициализация БД
    init_db()
    
    logger.info("="*60)
    logger.info("✅ ЗАПУСК БОТА NANO-BANANO v2.0")
    logger.info("="*60)
    
    # Получаем информацию о боте
    try:
        bot_info = await bot.get_me()
        logger.info(f"✅ Бот: @{bot_info.username}")
        logger.info(f"✅ ID бота: {bot_info.id}")
        logger.info(f"✅ Имя бота: {bot_info.full_name}")
    except Exception as e:
        logger.error(f"❌ Ошибка получения информации о боте: {e}")
        return
    
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
    try:
        health_thread = threading.Thread(target=run_health_server, daemon=True)
        health_thread.start()
        logger.info("🌐 HTTP health server started on port 10000")
    except Exception as e:
        logger.warning(f"⚠️ Не удалось запустить HTTP-сервер: {e}")
    
    # Запуск бота
    try:
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"🔥 Критическая ошибка polling: {e}")

# ==================== ENTRY POINT ====================
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("📴 Бот остановлен")
    except Exception as e:
        logger.error(f"💥 Фатальная ошибка: {e}")
