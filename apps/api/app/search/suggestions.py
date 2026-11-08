"""Predefined example prompts. They double as a smoke corpus: every one must parse to something useful."""

from app.schemas.search import Suggestion

SUGGESTIONS: tuple[Suggestion, ...] = (
    Suggestion(
        id="hamra-furnished",
        text_en="Furnished 2 bedroom in Hamra under $1,000 with 24/7 electricity",
        text_ar="شقة مفروشة بغرفتين في الحمرا حتى 1000$ مع كهرباء 24/24",
    ),
    Suggestion(
        id="quiet-safe-family",
        text_en="Quiet and safe 3 bedroom in Baabda with parking for 2 cars",
        text_ar="شقة 3 غرف نوم في بعبدا هادئة وآمنة مع موقفين",
    ),
    Suggestion(
        id="low-bills",
        text_en="Apartment in Metn with solar and low electricity bill",
        text_ar="شقة في المتن مع طاقة شمسية وفاتورة كهرباء منخفضة",
    ),
    Suggestion(
        id="warm-winter",
        text_en="Warm in winter, elevator with backup, Achrafieh up to $1,500",
        text_ar="شقة دافئة بالشتاء مع مصعد يعمل على المولد في الأشرفية حتى 1500$",
    ),
    Suggestion(
        id="pets-garden",
        text_en="Pet friendly house with a garden in Keserwan",
        text_ar="بيت مع حديقة ويسمح بالحيوانات في كسروان",
    ),
    Suggestion(
        id="sea-view-sale",
        text_en="Sea view apartment for sale in Beirut",
        text_ar="شقة مطلة على البحر للبيع في بيروت",
    ),
)
