import aiohttp
import replicate
from config import REPLICATE_API_TOKEN

async def generate_image_with_replicate(prompt: str, style: str = "классика", input_image_url: str = None) -> str:
    """Генерация через Replicate API"""
    if not REPLICATE_API_TOKEN:
        return None
    
    try:
        full_prompt = f"{prompt}, {style}, high quality, digital art"
        
        input_params = {
            "prompt": full_prompt,
            "negative_prompt": "ugly, blurry, bad quality, artifacts",
            "width": 768,
            "height": 1024,
            "num_outputs": 1
        }
        
        if input_image_url:
            input_params["image"] = input_image_url
        
        output = replicate.run(
            "stability-ai/sdxl:39ed52f2a78e934b3ba6e2a89f5b1c712de7dfea535525255b1aa35c5565e08b",
            input=input_params
        )
        
        if isinstance(output, list) and len(output) > 0:
            return output[0]
        return None
        
    except Exception:
        return None

async def generate_demo_image() -> str:
    """Демо-изображение"""
    return "https://i.imgur.com/demo_image.jpg"
