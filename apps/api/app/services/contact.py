"""WhatsApp hand-off links."""

from dataclasses import dataclass
from urllib.parse import quote

from app.models import Listing

_TEMPLATES = {
    "en": "Hi, I'm interested in this property on 2ajar: {title}\n{link}\nRef: {ref}",
    "ar": "مرحباً، أنا مهتم بهذا العقار على إيجار: {title}\n{link}\nالمرجع: {ref}",
}


@dataclass(frozen=True)
class WhatsAppLinkBuilder:
    """Builds ``wa.me`` deep links with a prefilled, localized message that references the listing."""

    web_base_url: str

    def build(self, listing: Listing, locale: str) -> str:
        if not listing.contact_whatsapp_e164:
            raise ValueError("listing has no WhatsApp contact")
        lang = "ar" if locale == "ar" else "en"
        primary, fallback = (
            (listing.title_ar, listing.title_en) if lang == "ar" else (listing.title_en, listing.title_ar)
        )
        text = _TEMPLATES[lang].format(
            title=primary or fallback or "",
            link=f"{self.web_base_url.rstrip('/')}/{lang}/listings/{listing.id}",
            ref=str(listing.id)[:8].upper(),
        )
        return f"https://wa.me/{listing.contact_whatsapp_e164.lstrip('+')}?text={quote(text)}"
