"""Rules for taking a listing live.

* Each completeness requirement is a small ``PublishRule`` (Specification pattern): rules are independent,
  individually testable, and new ones are added without editing the others (Open/Closed).
* ``PublishPolicy`` (Strategy) decides *where* a complete listing goes: straight to ``published`` (MVP,
  ADR-009) or to ``pending_review`` once moderation is switched on with ``MODERATION_REQUIRED=true``.
"""

from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass

from app.core.config import Settings
from app.models import Listing
from app.models.enums import RESIDENTIAL_TYPES, ListingStatus


class PublishRule(ABC):
    @abstractmethod
    def violation(self, listing: Listing) -> str | None:
        """Return a human-readable problem, or None when the listing satisfies the rule."""


class HasTitle(PublishRule):
    def violation(self, listing: Listing) -> str | None:
        return None if (listing.title_en or listing.title_ar) else "A title in English or Arabic is required"


class HasWhatsAppContact(PublishRule):
    def violation(self, listing: Listing) -> str | None:
        return None if listing.contact_whatsapp_e164 else "A WhatsApp contact number is required"


class ResidentialHasBedrooms(PublishRule):
    def violation(self, listing: Listing) -> str | None:
        prop = listing.property
        if prop.property_type in RESIDENTIAL_TYPES and prop.bedrooms is None:
            return "Number of bedrooms is required for residential properties"
        return None


class HasPhoto(PublishRule):
    def violation(self, listing: Listing) -> str | None:
        return None if listing.media else "At least one photo is required"


@dataclass(frozen=True)
class PublishPolicy(ABC):
    rules: Sequence[PublishRule]

    def problems(self, listing: Listing) -> list[str]:
        return [msg for rule in self.rules if (msg := rule.violation(listing)) is not None]

    @property
    @abstractmethod
    def target_status(self) -> ListingStatus: ...


class AutoPublishPolicy(PublishPolicy):
    @property
    def target_status(self) -> ListingStatus:
        return ListingStatus.published


class ModerationPolicy(PublishPolicy):
    @property
    def target_status(self) -> ListingStatus:
        return ListingStatus.pending_review


def publish_policy_for(settings: Settings) -> PublishPolicy:
    """Factory: assemble rules and pick the policy from configuration."""
    rules: list[PublishRule] = [HasTitle(), HasWhatsAppContact(), ResidentialHasBedrooms()]
    if settings.publish_requires_media:
        rules.append(HasPhoto())
    policy_cls = ModerationPolicy if settings.moderation_required else AutoPublishPolicy
    return policy_cls(rules=rules)
