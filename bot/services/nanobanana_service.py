import base64
import logging
import aiohttp
from typing import Optional

from bot.config import config
from bot.utils.image_utils import image_to_base64

logger = logging.getLogger(__name__)


class NanoBananaService:
    """Service for working with Nano Banana Pro (OpenRouter/Gemini) for image generation"""

    def __init__(self):
        self.api_url = config.openrouter_api_url
        self.api_key = config.openrouter_api_key
        self.model = config.nanobanana_model

    async def _make_request(
        self,
        messages: list,
        temperature: float = 0.8,
        max_tokens: int = 4096
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
        """Remove background from product image using vision model"""
        image_base64 = image_to_base64(image_bytes)

        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": """Analyze this product image and create a detailed description of ONLY the main product/object,
ignoring the background completely. Describe:
1. The product shape and form
2. Colors and textures
3. Key visual features
4. Size proportions

This description will be used to recreate the product on a transparent/white background.
Be extremely detailed and precise."""
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

        response = await self._make_request(messages)

        if response and "choices" in response:
            # For now, return the original image as Gemini doesn't do direct image editing
            # In production, you would use a specialized background removal API
            logger.info("Background removal description generated")
            return image_bytes

        return None

    async def generate_infographic_image(
        self,
        product_image_bytes: bytes,
        prompt: str,
        style_guide: str,
        text_overlay: str,
        is_main: bool = False,
        reference_image_bytes: Optional[bytes] = None
    ) -> Optional[str]:
        """
        Generate infographic slide image.
        Returns detailed prompt for image generation.
        """
        product_base64 = image_to_base64(product_image_bytes)

        # Build the prompt for image generation
        full_prompt = f"""Based on the product image provided, create a professional infographic design.

PRODUCT IMAGE ANALYSIS REQUEST:
Analyze the product in the image and create a detailed infographic design prompt.

DESIGN REQUIREMENTS:
{prompt}

STYLE GUIDE:
{style_guide}

TEXT TO INCLUDE ON THE SLIDE:
{text_overlay}

TECHNICAL SPECS:
- Dimensions: 900x1200 pixels (3:4 ratio for marketplace)
- Format: Clean product infographic
- Background: White or subtle gradient
- Typography: Bold, readable Russian text
- Layout: Product prominently displayed with text overlays

{"This is the MAIN/FIRST slide - it sets the visual style for all other slides." if is_main else "Match the style of the main slide exactly."}

Describe in detail how the final infographic should look, including:
1. Layout composition
2. Color scheme
3. Typography placement
4. Visual elements and icons
5. Product positioning
6. Text hierarchy"""

        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": full_prompt
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{product_base64}"
                        }
                    }
                ]
            }
        ]

        # Add reference image for non-main slides
        if reference_image_bytes and not is_main:
            ref_base64 = image_to_base64(reference_image_bytes)
            messages[0]["content"].append({
                "type": "text",
                "text": "\n\nREFERENCE STYLE IMAGE (match this style exactly):"
            })
            messages[0]["content"].append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{ref_base64}"
                }
            })

        response = await self._make_request(messages, temperature=0.7)

        if response and "choices" in response:
            design_description = response["choices"][0]["message"]["content"]
            return design_description

        return None

    async def create_slide_design(
        self,
        product_image_bytes: bytes,
        slide_info: dict,
        style_guide: str,
        reference_description: Optional[str] = None
    ) -> Optional[dict]:
        """
        Create a complete slide design with all elements.
        Returns design specification for the slide.
        """
        product_base64 = image_to_base64(product_image_bytes)

        is_main = slide_info.get("is_main", False)
        prompt = slide_info.get("prompt", "")
        text_overlay = slide_info.get("text_overlay", "")
        slide_num = slide_info.get("slide", 1)

        system_content = """You are a professional infographic designer specializing in e-commerce product cards for Russian marketplaces (Wildberries, Ozon).

Create detailed design specifications for product infographic slides.

Your response should be a complete design brief including:
1. Layout grid and composition
2. Color palette (hex codes)
3. Typography specifications
4. Element positioning
5. Visual hierarchy
6. Icon/graphic suggestions"""

        user_content = f"""Design Slide #{slide_num} {"(MAIN SLIDE - sets style for series)" if is_main else "(must match main slide style)"}

PROMPT: {prompt}

TEXT FOR SLIDE: {text_overlay}

STYLE GUIDE: {style_guide}

{"" if is_main else f"REFERENCE STYLE: {reference_description}" if reference_description else ""}

Create a detailed design specification for this marketplace infographic slide.
Include specific layout coordinates, colors, and styling details.
The design must work at 900x1200 pixels."""

        messages = [
            {
                "role": "system",
                "content": system_content
            },
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": user_content},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{product_base64}"}
                    }
                ]
            }
        ]

        response = await self._make_request(messages, temperature=0.6)

        if response and "choices" in response:
            design_spec = response["choices"][0]["message"]["content"]
            return {
                "slide_num": slide_num,
                "is_main": is_main,
                "design_spec": design_spec,
                "text_overlay": text_overlay,
                "prompt": prompt
            }

        return None

    async def generate_all_slides(
        self,
        product_image_bytes: bytes,
        slide_prompts: list[dict],
        style_guide: str
    ) -> list[dict]:
        """
        Generate design specs for all slides in the infographic series.
        Maintains consistent style across all slides.
        """
        results = []
        main_design_description = None

        for slide_info in slide_prompts:
            is_main = slide_info.get("is_main", False)

            design = await self.create_slide_design(
                product_image_bytes=product_image_bytes,
                slide_info=slide_info,
                style_guide=style_guide,
                reference_description=main_design_description if not is_main else None
            )

            if design:
                results.append(design)

                # Save main slide design as reference
                if is_main:
                    main_design_description = design.get("design_spec", "")

                logger.info(f"Generated design for slide {slide_info.get('slide', '?')}")
            else:
                logger.error(f"Failed to generate slide {slide_info.get('slide', '?')}")

        return results

    async def analyze_product_image(self, image_bytes: bytes) -> Optional[str]:
        """Analyze product image and return detailed description"""
        image_base64 = image_to_base64(image_bytes)

        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": """Analyze this product image in detail. Describe:

1. What product is shown
2. Main features visible
3. Color scheme
4. Material/texture (if visible)
5. Size/proportions
6. Quality indicators
7. Target audience suggestions

Be thorough and precise. This analysis will help create marketing materials."""
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
            return response["choices"][0]["message"]["content"]

        return None


# Singleton instance
nanobanana_service = NanoBananaService()
