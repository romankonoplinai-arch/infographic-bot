import json
import logging
import re
import aiohttp
from typing import Optional

from bot.config import config

logger = logging.getLogger(__name__)


def extract_json_from_text(text: str) -> Optional[str]:
    """Extract JSON from text that may contain markdown or extra content"""
    # Remove markdown code blocks
    text = text.strip()

    # Try to find JSON in code block
    code_block_match = re.search(r'```(?:json)?\s*([\s\S]*?)```', text)
    if code_block_match:
        text = code_block_match.group(1).strip()

    # Try to find JSON object or array
    json_match = re.search(r'(\{[\s\S]*\}|\[[\s\S]*\])', text)
    if json_match:
        return json_match.group(1)

    return text


class GrokService:
    """Service for working with xAI Grok 4 API"""

    def __init__(self):
        self.api_url = config.grok_api_url
        self.api_key = config.grok_api_key
        self.model = config.grok_model

    async def _make_request(self, messages: list, temperature: float = 0.7) -> Optional[str]:
        """Make request to Grok API"""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": 8192
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.api_url,
                    headers=headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=120)  # Increased timeout
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"Grok API error: {response.status} - {error_text}")
                        return None

                    data = await response.json()
                    content = data["choices"][0]["message"]["content"]
                    logger.info(f"Grok response received, length: {len(content)}")
                    return content

        except aiohttp.ClientError as e:
            logger.error(f"Grok API connection error: {e}")
            return None
        except Exception as e:
            logger.error(f"Grok API unexpected error: {e}")
            return None

    async def analyze_keywords(self, product_name: str, category: str) -> Optional[dict]:
        """Analyze product and generate keywords for WB/Ozon"""
        system_prompt = """Ты - эксперт по SEO для маркетплейсов Wildberries и Ozon в России.
Твоя задача - анализировать товары и находить релевантные ключевые слова для поиска.

ВАЖНО: Отвечай ТОЛЬКО валидным JSON без markdown-форматирования и без ```json блоков.

Формат ответа:
{
    "keywords": ["ключ1", "ключ2", ...],
    "high_frequency": ["высокочастотный1", "высокочастотный2", ...],
    "mid_frequency": ["среднечастотный1", ...],
    "low_frequency": ["низкочастотный1", ...]
}"""

        user_prompt = f"""Проанализируй товар и найди ключевые слова для продвижения на WB и Ozon:

Товар: {product_name}
Категория: {category}

Найди 15-20 релевантных ключевых слов и фраз, которые покупатели в России используют для поиска такого товара.
Раздели их на высокочастотные (3-5), среднечастотные (5-7) и низкочастотные/длиннохвостые (5-8).

Отвечай ТОЛЬКО валидным JSON."""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        response = await self._make_request(messages, temperature=0.5)

        if not response:
            return None

        try:
            clean_response = extract_json_from_text(response)
            result = json.loads(clean_response)
            logger.info(f"Keywords parsed successfully")
            return result
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse keywords JSON: {e}, response: {response[:500]}")
            return None

    async def generate_seo_content(
        self,
        product_name: str,
        category: str,
        keywords: list[str]
    ) -> Optional[dict]:
        """Generate SEO content for product card and description"""
        system_prompt = """Ты - копирайтер-эксперт по созданию продающих описаний для маркетплейсов Wildberries и Ozon.
Создавай убедительные, SEO-оптимизированные тексты на русском языке.

ВАЖНО: Отвечай ТОЛЬКО валидным JSON без markdown-форматирования и без ```json блоков.

Формат ответа:
{
    "title": "SEO-заголовок до 60 символов",
    "card_bullets": ["УТП 1", "УТП 2", "УТП 3", ...],
    "description": "Полное описание товара 500-1000 символов",
    "optimal_slides": 5,
    "slides_content": [
        {"slide": 1, "focus": "Главное УТП", "text": "Текст для слайда"},
        {"slide": 2, "focus": "Преимущество", "text": "Текст для слайда"},
        ...
    ]
}"""

        keywords_str = ", ".join(keywords[:15])

        user_prompt = f"""Создай SEO-контент для товара:

Товар: {product_name}
Категория: {category}
Ключевые слова: {keywords_str}

Требования:
1. SEO-заголовок (до 60 символов) - включи главное ключевое слово
2. Буллеты для карточки (5-7 коротких УТП)
3. Описание товара (500-1000 символов) - естественно включи ключевые слова
4. Определи оптимальное количество слайдов для инфографики (3-7)
5. Для каждого слайда укажи фокус и короткий текст

Отвечай ТОЛЬКО валидным JSON."""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        response = await self._make_request(messages, temperature=0.7)

        if not response:
            return None

        try:
            clean_response = extract_json_from_text(response)
            result = json.loads(clean_response)
            logger.info(f"SEO content parsed successfully")
            return result
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse SEO JSON: {e}, response: {response[:500]}")
            return None

    async def generate_slide_prompts(
        self,
        product_name: str,
        category: str,
        seo_content: dict,
        num_slides: int
    ) -> Optional[list[dict]]:
        """Generate image generation prompts for each infographic slide"""
        system_prompt = """Ты - эксперт по созданию промтов для генерации изображений инфографики товаров.
Создавай детальные промты на английском языке для AI-генерации изображений карточек товаров.

ВАЖНО: Отвечай ТОЛЬКО валидным JSON без markdown-форматирования.

Формат ответа:
{
    "style_guide": "Описание общего стиля для всех слайдов",
    "prompts": [
        {
            "slide": 1,
            "is_main": true,
            "prompt": "Детальный промт на английском",
            "text_overlay": "Текст на русском для наложения"
        },
        ...
    ]
}"""

        slides_content = seo_content.get("slides_content", [])[:num_slides]
        slides_info = "\n".join([
            f"Слайд {s['slide']}: {s['focus']} - {s['text']}"
            for s in slides_content
        ])

        user_prompt = f"""Создай промты для генерации {num_slides} слайдов инфографики:

Товар: {product_name}
Категория: {category}
Заголовок: {seo_content.get('title', '')}

Контент слайдов:
{slides_info}

Требования к промтам:
1. Первый слайд - главный (is_main: true), задает стиль для остальных
2. Все слайды должны быть в едином стиле
3. Промты на английском языке
4. Укажи текст на русском для наложения на каждый слайд
5. Стиль: профессиональная инфографика для маркетплейса, чистый фон, яркие акценты

Включи в промты:
- Размер 900x1200 (3:4 ratio)
- Профессиональный продуктовый дизайн
- Место для текста
- Современный минималистичный стиль

Отвечай ТОЛЬКО валидным JSON."""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        response = await self._make_request(messages, temperature=0.8)

        if not response:
            return None

        try:
            clean_response = extract_json_from_text(response)
            data = json.loads(clean_response)
            logger.info(f"Slide prompts parsed successfully, {len(data.get('prompts', []))} prompts")
            return data
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse prompts JSON: {e}, response: {response[:500]}")
            return None

    async def generate_full_analysis(
        self,
        product_name: str,
        category: str,
        num_slides: Optional[int] = None
    ) -> Optional[dict]:
        """Complete product analysis: keywords + SEO + slide prompts"""

        # Step 1: Get keywords
        keywords_data = await self.analyze_keywords(product_name, category)
        if not keywords_data:
            logger.error("Failed to get keywords")
            return None

        all_keywords = (
            keywords_data.get("high_frequency", []) +
            keywords_data.get("mid_frequency", []) +
            keywords_data.get("low_frequency", [])
        )

        if not all_keywords:
            all_keywords = keywords_data.get("keywords", [])

        # Step 2: Generate SEO content
        seo_content = await self.generate_seo_content(product_name, category, all_keywords)
        if not seo_content:
            logger.error("Failed to generate SEO content")
            return None

        # Determine slides count
        if num_slides is None:
            num_slides = seo_content.get("optimal_slides", config.default_slides_count)
        num_slides = max(config.min_slides, min(config.max_slides, num_slides))

        # Step 3: Generate slide prompts
        prompts_data = await self.generate_slide_prompts(
            product_name, category, seo_content, num_slides
        )
        if not prompts_data:
            logger.error("Failed to generate slide prompts")
            return None

        return {
            "product_name": product_name,
            "category": category,
            "keywords": keywords_data,
            "seo": seo_content,
            "num_slides": num_slides,
            "style_guide": prompts_data.get("style_guide", ""),
            "slide_prompts": prompts_data.get("prompts", [])
        }

    async def generate_seo_with_ctr_prompts(
        self,
        product_description: str,
        num_slides: int = 5
    ) -> Optional[dict]:
        """Generate SEO and CTR-optimized slide prompts based on user description"""
        system_prompt = """Ты - эксперт по созданию продающего контента для маркетплейсов WB/Ozon с фокусом на максимальный CTR.

ВАЖНО: Отвечай ТОЛЬКО валидным JSON без markdown.

Твоя задача:
1. Проанализировать описание товара и пожелания клиента
2. Создать SEO-контент для карточки
3. Создать промты для каждого слайда инфографики с МАКСИМАЛЬНЫМ CTR

Формат ответа:
{
    "keywords": {
        "high_frequency": ["ключ1", "ключ2"],
        "mid_frequency": ["ключ1", "ключ2"],
        "low_frequency": ["ключ1", "ключ2"]
    },
    "seo": {
        "title": "SEO заголовок",
        "description": "Полное описание 500-1000 символов",
        "bullets": ["УТП 1", "УТП 2"]
    },
    "slide_prompts": [
        {
            "slide": 1,
            "is_main": true,
            "focus": "Краткое описание фокуса слайда",
            "text_ru": "Текст на русском для слайда",
            "ctr_elements": ["элемент1", "элемент2"]
        }
    ]
}"""

        user_prompt = f"""Описание товара и пожелания клиента:
{product_description}

Количество слайдов: {num_slides}

ТРЕБОВАНИЯ К ПРОМТАМ ДЛЯ СЛАЙДОВ:
1. Каждый промт должен быть направлен на МАКСИМАЛЬНЫЙ CTR
2. Слайд 1 - самый важный, должен привлекать внимание
3. Используй продающие элементы: яркие акценты, контрасты, чёткие УТП
4. НЕ ограничивай фантазию - укажи ЧТО показать, но не КАК именно
5. Все тексты на русском языке
6. Учти пожелания клиента по каждому слайду

Для каждого слайда укажи:
- focus: что главное на слайде
- text_ru: текст для отображения на слайде
- ctr_elements: какие элементы повысят CTR (например: "яркая цена", "бейдж скидки", "стрелка внимания")

Отвечай ТОЛЬКО валидным JSON."""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        response = await self._make_request(messages, temperature=0.7)

        if not response:
            return None

        try:
            clean_response = extract_json_from_text(response)
            result = json.loads(clean_response)
            logger.info(f"SEO with CTR prompts generated: {len(result.get('slide_prompts', []))} slides")
            return result
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse SEO CTR JSON: {e}, response: {response[:500]}")
            return None


# Singleton instance
grok_service = GrokService()
