import base64
import logging
import aiohttp
from typing import Optional

from bot.config import config
from bot.utils.image_utils import image_to_base64

logger = logging.getLogger(__name__)


class NanoBananaService:
    """Service for working with Nano Banana Pro (Google Gemini 3 Pro Image) for image generation"""

    def __init__(self):
        self.api_url = config.openrouter_api_url
        self.api_key = config.openrouter_api_key
        self.model = config.nanobanana_model

    async def _make_request(
        self,
        messages: list,
        temperature: float = 0.8,
        max_tokens: int = 8192
    ) -> Optional[dict]:
        """Make request to OpenRouter API"""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://infographic-bot.railway.app",
            "X-Title": "Infographic Bot"
        }

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.api_url,
                    headers=headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=config.image_timeout_seconds)
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"OpenRouter API error: {response.status} - {error_text}")
                        return None

                    return await response.json()

        except aiohttp.ClientError as e:
            logger.error(f"OpenRouter API connection error: {e}")
            return None
        except Exception as e:
            logger.error(f"OpenRouter API unexpected error: {e}")
            return None

    async def remove_background(self, image_bytes: bytes) -> Optional[bytes]:
        """
        Remove background from product image.
        Uses Nano Banana Pro to generate product on white background.
        """
        image_base64 = image_to_base64(image_bytes)

        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": """Проанализируй это изображение товара и создай новое изображение:

ЗАДАЧА: Удали фон и оставь ТОЛЬКО товар на чистом белом фоне.

ТРЕБОВАНИЯ:
1. Сохрани товар в точности как на оригинале
2. Фон должен быть идеально белым (#FFFFFF)
3. Сохрани все детали, цвета и текстуры товара
4. Товар должен быть по центру
5. Оставь небольшие поля вокруг товара

Сгенерируй изображение товара на белом фоне."""
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{image_base64}"
                        }
                    }
                ]
            }
        ]

        response = await self._make_request(messages, temperature=0.3)

        if response and "choices" in response:
            content = response["choices"][0]["message"].get("content", "")

            # Check if response contains base64 image
            if "data:image" in str(content) or isinstance(content, list):
                # Extract image from response
                extracted_image = self._extract_image_from_response(response)
                if extracted_image:
                    return extracted_image

            logger.info("Background removal: returning original (model didn't generate image)")
            return image_bytes

        return None

    def _extract_image_from_response(self, response: dict) -> Optional[bytes]:
        """Extract base64 image from API response"""
        try:
            content = response["choices"][0]["message"].get("content", "")

            # Handle list content (multimodal response)
            if isinstance(content, list):
                for item in content:
                    if isinstance(item, dict):
                        if item.get("type") == "image_url":
                            url = item.get("image_url", {}).get("url", "")
                            if url.startswith("data:image"):
                                base64_data = url.split(",")[1]
                                return base64.b64decode(base64_data)

            # Handle string content with embedded base64
            if isinstance(content, str) and "data:image" in content:
                import re
                match = re.search(r'data:image/[^;]+;base64,([A-Za-z0-9+/=]+)', content)
                if match:
                    return base64.b64decode(match.group(1))

        except Exception as e:
            logger.error(f"Error extracting image: {e}")

        return None

    async def generate_infographic_slide(
        self,
        product_image_bytes: bytes,
        slide_number: int,
        slide_text: str,
        product_name: str,
        style_description: str = "",
        is_main: bool = False,
        reference_image_bytes: Optional[bytes] = None
    ) -> Optional[bytes]:
        """
        Generate infographic slide with Russian text.
        Returns generated image bytes.
        """
        product_base64 = image_to_base64(product_image_bytes)

        # Build prompt for Russian marketplace infographic
        if is_main:
            prompt = f"""Создай профессиональную инфографику для маркетплейса (Wildberries/Ozon).

ТОВАР: {product_name}

ТЕКСТ НА РУССКОМ ДЛЯ СЛАЙДА:
{slide_text}

ТРЕБОВАНИЯ К ДИЗАЙНУ:
1. Размер: 900x1200 пикселей (соотношение 3:4)
2. Товар с фото должен быть главным элементом
3. Фон: чистый белый или светлый градиент
4. Текст: крупный, читаемый, НА РУССКОМ ЯЗЫКЕ
5. Стиль: современный, минималистичный, премиальный
6. Добавь графические элементы (иконки, стрелки) для акцентов
7. Яркие акцентные цвета для привлечения внимания

ЭТО ГЛАВНЫЙ СЛАЙД - он задает стиль для всей серии.
Текст должен быть ТОЛЬКО на русском языке!

Сгенерируй готовое изображение инфографики."""
        else:
            prompt = f"""Создай слайд #{slide_number} инфографики для маркетплейса.

ТОВАР: {product_name}

ТЕКСТ НА РУССКОМ ДЛЯ ЭТОГО СЛАЙДА:
{slide_text}

СТИЛЬ (должен совпадать с главным слайдом):
{style_description}

ТРЕБОВАНИЯ:
1. Размер: 900x1200 пикселей
2. ТОЧНО повтори стиль главного слайда
3. Те же цвета, шрифты, элементы дизайна
4. Текст ТОЛЬКО на русском языке
5. Товар должен быть виден на слайде

Сгенерируй изображение в едином стиле с серией."""

        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{product_base64}"}
                    }
                ]
            }
        ]

        # Add reference image for style consistency
        if reference_image_bytes and not is_main:
            ref_base64 = image_to_base64(reference_image_bytes)
            messages[0]["content"].append({
                "type": "text",
                "text": "\n\nРЕФЕРЕНС СТИЛЯ (повтори этот стиль точно):"
            })
            messages[0]["content"].append({
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{ref_base64}"}
            })

        response = await self._make_request(messages, temperature=0.7)

        if response:
            extracted_image = self._extract_image_from_response(response)
            if extracted_image:
                logger.info(f"Generated slide {slide_number}")
                return extracted_image
            else:
                logger.warning(f"Slide {slide_number}: no image in response")

        return None

    async def generate_all_slides(
        self,
        product_image_bytes: bytes,
        slide_prompts: list[dict],
        style_guide: str,
        product_name: str
    ) -> list[dict]:
        """
        Generate all infographic slides.
        Returns list of dicts with slide_num, image_bytes, text.
        """
        results = []
        main_slide_image = None
        main_style_description = style_guide

        for slide_info in slide_prompts:
            is_main = slide_info.get("is_main", False)
            slide_num = slide_info.get("slide", 1)
            text_overlay = slide_info.get("text_overlay", "")

            logger.info(f"Generating slide {slide_num}...")

            image_bytes = await self.generate_infographic_slide(
                product_image_bytes=product_image_bytes,
                slide_number=slide_num,
                slide_text=text_overlay,
                product_name=product_name,
                style_description=main_style_description,
                is_main=is_main,
                reference_image_bytes=main_slide_image if not is_main else None
            )

            if image_bytes:
                results.append({
                    "slide_num": slide_num,
                    "is_main": is_main,
                    "image_bytes": image_bytes,
                    "text_overlay": text_overlay
                })

                # Save main slide as reference for style
                if is_main:
                    main_slide_image = image_bytes

                logger.info(f"Slide {slide_num} generated successfully")
            else:
                logger.error(f"Failed to generate slide {slide_num}")
                results.append({
                    "slide_num": slide_num,
                    "is_main": is_main,
                    "image_bytes": None,
                    "text_overlay": text_overlay,
                    "error": True
                })

        return results

    async def edit_image_by_prompt(self, image_bytes: bytes, prompt: str) -> Optional[bytes]:
        """
        Edit image based on user prompt.
        Returns edited image bytes.
        """
        image_base64 = image_to_base64(image_bytes)

        full_prompt = f"""Отредактируй это изображение согласно инструкции:

ИНСТРУКЦИЯ ПО РЕДАКТИРОВАНИЮ:
{prompt}

ТРЕБОВАНИЯ:
1. Выполни ТОЛЬКО то, что указано в инструкции
2. Сохрани остальные элементы изображения без изменений
3. Результат должен выглядеть профессионально и естественно
4. Если нужен текст - используй русский язык

Сгенерируй отредактированное изображение."""

        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": full_prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"}
                    }
                ]
            }
        ]

        response = await self._make_request(messages, temperature=0.5)

        if response:
            extracted_image = self._extract_image_from_response(response)
            if extracted_image:
                logger.info("Image edited successfully")
                return extracted_image
            else:
                logger.warning("Edit image: no image in response")

        return None

    async def analyze_product_image(self, image_bytes: bytes) -> Optional[str]:
        """Analyze product image and return detailed description in Russian"""
        image_base64 = image_to_base64(image_bytes)

        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": """Проанализируй это изображение товара. Опиши на русском языке:

1. Что за товар на фото
2. Основные характеристики и особенности
3. Цветовая гамма
4. Материал (если видно)
5. Для какой аудитории подходит
6. Ключевые преимущества для продажи

Ответ дай на русском языке, кратко и по делу."""
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{image_base64}"
                        }
                    }
                ]
            }
        ]

        response = await self._make_request(messages, temperature=0.5)

        if response and "choices" in response:
            content = response["choices"][0]["message"].get("content", "")
            if isinstance(content, str):
                return content
            elif isinstance(content, list):
                # Extract text from multimodal response
                for item in content:
                    if isinstance(item, dict) and item.get("type") == "text":
                        return item.get("text", "")
                    elif isinstance(item, str):
                        return item

        return None


# Singleton instance
nanobanana_service = NanoBananaService()
