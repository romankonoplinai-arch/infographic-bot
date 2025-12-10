from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime


@dataclass
class UserSession:
    """User session for tracking infographic creation progress"""
    user_id: int
    created_at: datetime = field(default_factory=datetime.now)

    # Product info
    product_name: Optional[str] = None
    category: Optional[str] = None

    # Images
    original_image: Optional[bytes] = None
    no_bg_image: Optional[bytes] = None
    reference_image: Optional[bytes] = None

    # First slide generation
    slide_prompt: Optional[str] = None
    product_description: Optional[str] = None

    # SEO data
    keywords: Optional[dict] = None
    seo_title: Optional[str] = None
    seo_card_content: Optional[list] = None
    seo_description: Optional[str] = None

    # Slide generation
    num_slides: Optional[int] = None
    slide_prompts: Optional[list] = None
    style_guide: Optional[str] = None

    # Generated slides
    main_slide_design: Optional[dict] = None
    slides_designs: Optional[list] = None

    # Full analysis result
    full_analysis: Optional[dict] = None

    def reset(self):
        """Reset session to initial state"""
        self.product_name = None
        self.category = None
        self.original_image = None
        self.no_bg_image = None
        self.reference_image = None
        self.slide_prompt = None
        self.product_description = None
        self.keywords = None
        self.seo_title = None
        self.seo_card_content = None
        self.seo_description = None
        self.num_slides = None
        self.slide_prompts = None
        self.style_guide = None
        self.main_slide_design = None
        self.slides_designs = None
        self.full_analysis = None

    def has_image(self) -> bool:
        """Check if product image is loaded"""
        return self.original_image is not None

    def has_product_info(self) -> bool:
        """Check if product info is complete"""
        return self.product_name is not None and self.category is not None

    def has_analysis(self) -> bool:
        """Check if full analysis is complete"""
        return self.full_analysis is not None

    def get_keywords_list(self) -> list[str]:
        """Get flat list of all keywords"""
        if not self.keywords:
            return []

        all_keywords = []
        for key in ['high_frequency', 'mid_frequency', 'low_frequency', 'keywords']:
            if key in self.keywords:
                all_keywords.extend(self.keywords[key])

        return list(set(all_keywords))

    def format_keywords_message(self) -> str:
        """Format keywords for display in Telegram"""
        if not self.keywords:
            return "Ключевые слова не найдены"

        lines = ["<b>Ключевые слова для WB/Ozon:</b>\n"]

        if self.keywords.get("high_frequency"):
            lines.append("<b>Высокочастотные:</b>")
            lines.append(", ".join(self.keywords["high_frequency"]))
            lines.append("")

        if self.keywords.get("mid_frequency"):
            lines.append("<b>Среднечастотные:</b>")
            lines.append(", ".join(self.keywords["mid_frequency"]))
            lines.append("")

        if self.keywords.get("low_frequency"):
            lines.append("<b>Низкочастотные:</b>")
            lines.append(", ".join(self.keywords["low_frequency"]))

        return "\n".join(lines)

    def format_seo_message(self) -> str:
        """Format SEO content for display in Telegram"""
        if not self.full_analysis:
            return "SEO контент не сгенерирован"

        seo = self.full_analysis.get("seo", {})
        lines = ["<b>SEO-контент для товара:</b>\n"]

        if seo.get("title"):
            lines.append(f"<b>Заголовок:</b> {seo['title']}\n")

        if seo.get("card_bullets"):
            lines.append("<b>Буллеты для карточки:</b>")
            for bullet in seo["card_bullets"]:
                lines.append(f"• {bullet}")
            lines.append("")

        if seo.get("description"):
            lines.append("<b>Описание:</b>")
            lines.append(seo["description"][:500] + "..." if len(seo.get("description", "")) > 500 else seo["description"])

        return "\n".join(lines)

    def format_plan_message(self) -> str:
        """Format infographic plan for display"""
        if not self.full_analysis:
            return "План не сформирован"

        lines = [
            f"<b>План создания инфографики</b>\n",
            f"<b>Товар:</b> {self.product_name}",
            f"<b>Категория:</b> {self.category}",
            f"<b>Количество слайдов:</b> {self.full_analysis.get('num_slides', 5)}\n",
            f"<b>Стиль:</b> {self.full_analysis.get('style_guide', 'Профессиональный')[:200]}...\n",
            "<b>Слайды:</b>"
        ]

        for prompt in self.full_analysis.get("slide_prompts", []):
            slide_num = prompt.get("slide", "?")
            is_main = "👑 " if prompt.get("is_main") else ""
            text = prompt.get("text_overlay", "")[:50]
            lines.append(f"{is_main}Слайд {slide_num}: {text}...")

        return "\n".join(lines)


class SessionManager:
    """Manager for user sessions"""

    def __init__(self):
        self._sessions: dict[int, UserSession] = {}

    def get_session(self, user_id: int) -> UserSession:
        """Get or create session for user"""
        if user_id not in self._sessions:
            self._sessions[user_id] = UserSession(user_id=user_id)
        return self._sessions[user_id]

    def reset_session(self, user_id: int):
        """Reset user session"""
        if user_id in self._sessions:
            self._sessions[user_id].reset()

    def delete_session(self, user_id: int):
        """Delete user session"""
        if user_id in self._sessions:
            del self._sessions[user_id]

    def has_session(self, user_id: int) -> bool:
        """Check if user has active session"""
        return user_id in self._sessions


# Global session manager
session_manager = SessionManager()
