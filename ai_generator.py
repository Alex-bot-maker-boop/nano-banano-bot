import aiohttp
from config import REPLICATE_API_TOKEN

async def generate_image_with_replicate(prompt: str, style: str = "классика", input_image_url: str = None) -> str:
    """Генерация через Replicate API"""
    if not REPLICATE_API_TOKEN or REPLICATE_API_TOKEN == "":
        return None
     try:
        # Упрощённая версия без replicate, если нет токена
        return None
    except:
        return None

async def generate_demo_image() -> str:
    """Демо-изображение"""
    return "https://images.unsplash.com/photo-1544005313-94ddf0286df2?w=800&h=1200&fit=crop"
