import random
import requests
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import replicate
from config import REPLICATE_API_TOKEN

async def generate_image(prompt: str, input_photo_url: str = None, style: str = "советские сказки") -> bytes:
    """
    Гибридный генератор:
    1. Пробует Replicate (если есть токен и лимит)
    2. Иначе использует бесплатные методы
    """
    
    # Если есть Replicate API токен
    if REPLICATE_API_TOKEN and REPLICATE_API_TOKEN != "ваш_токен":
        try:
            output = replicate.run(
                "stability-ai/sdxl:39ed52f2a78e934b3ba6e2a89f5b1c712de7dfea535525255b1aa35c5565e08b",
                input={
                    "prompt": f"{prompt}, {style}, высокое качество",
                    "negative_prompt": "уродливое, размытое",
                    "width": 768,
                    "height": 1024
                }
            )
            if output:
                img_response = requests.get(output[0])
                return img_response.content
        except:
            pass  # Если не получилось — переходим к бесплатному методу
    
    # БЕСПЛАТНЫЙ МЕТОД: наложение фильтров на фото
    try:
        # 1. Получаем фото (входное или случайное)
        if input_photo_url:
            response = requests.get(input_photo_url)
            img = Image.open(BytesIO(response.content))
        else:
            # Бесплатные стоковые фото с Pexels
            pexels_url = "https://images.pexels.com/photos/1239291/pexels-photo-1239291.jpeg"
            img = Image.open(BytesIO(requests.get(pexels_url).content))
        
        # 2. Применяем эффекты под стиль
        img = img.resize((768, 1024))
        
        if "советские" in style.lower():
            # Винтажные цвета
            img = img.convert("RGB")
            r, g, b = img.split()
            r = r.point(lambda i: i * 1.2)
            b = b.point(lambda i: i * 0.8)
            img = Image.merge("RGB", (r, g, b))
            
            # Добавляем текст
            draw = ImageDraw.Draw(img)
            try:
                font = ImageFont.truetype("arial.ttf", 40)
            except:
                font = ImageFont.load_default()
            
            draw.text((50, 50), "С Новым Годом!", fill=(255, 50, 50), font=font)
            draw.text((50, 100), "1970-е", fill=(100, 100, 255), font=font)
        
        # 3. Добавляем "снег"
        draw = ImageDraw.Draw(img)
        for _ in range(150):
            x, y = random.randint(0, img.width), random.randint(0, img.height)
            size = random.randint(2, 5)
            draw.ellipse([x, y, x+size, y+size], fill="white")
        
        # 4. Конвертируем в bytes
        img_bytes = BytesIO()
        img.save(img_bytes, format='JPEG', quality=90)
        return img_bytes.getvalue()
        
    except Exception as e:
        # Если всё сломалось — возвращаем запасное изображение
        print(f"Ошибка генерации: {e}")
        response = requests.get("https://i.imgur.com/demo_image.jpg")
        return response.content
