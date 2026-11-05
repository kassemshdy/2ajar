"""Lead capture: consented, normalized and deduplicated contact requests."""

import uuid
from collections.abc import Callable
from datetime import datetime, timedelta

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.authz.policies import Principal
from app.core.config import Settings
from app.core.errors import ValidationFailed
from app.core.events import EventRecorder
from app.core.phone import normalize_phone
from app.core.security import utcnow
from app.domain.events import LeadReceived
from app.models import Lead, Listing
from app.models.enums import LeadSource, ListingEventType
from app.repositories.leads import LeadRepository
from app.schemas.lead import LeadCreate
from app.services.audit import record_event
from app.services.listings import ListingService

DEDUPE_WINDOW = timedelta(hours=24)
MAX_MESSAGE_HISTORY = 4000  # characters kept when repeat contacts append messages

Clock = Callable[[], datetime]


class LeadService:
    def __init__(
        self,
        session: AsyncSession,
        *,
        settings: Settings,
        events: EventRecorder,
        listings: ListingService,
        clock: Clock = utcnow,
    ) -> None:
        self._session = session
        self._settings = settings
        self._events = events
        self._listings = listings
        self._clock = clock
        self.repo = LeadRepository(session)

    async def submit(
        self,
        listing_id: uuid.UUID,
        data: LeadCreate,
        user_id: uuid.UUID | None,
        request: Request | None = None,
        source: LeadSource = LeadSource.web,
    ) -> tuple[Lead, bool]:
        """Create a lead, or merge into a recent one from the same phone. Returns (lead, deduplicated)."""
        listing = await self._listings.get_public(listing_id)
        phone = normalize_phone(data.phone)
        if phone is None:
            raise ValidationFailed("Invalid phone number", details=[{"loc": ["body", "phone"]}])
        if data.consent_text_version != self._settings.consent_text_version:
            # The visitor consented to a different wording than the current one: ask them to reload.
            raise ValidationFailed("Consent text is outdated, please reload the page")

        await self.repo.lock_contact(listing.id, phone)
        now = self._clock()
        existing = await self.repo.recent_from(listing.id, phone, since=now - DEDUPE_WINDOW)
        if existing is not None:
            self._merge_repeat_contact(existing, data.message, now)
            await self._session.commit()
            return existing, True

        lead = Lead(
            listing_id=listing.id,
            seeker_user_id=user_id,
            name=data.name,
            phone_e164=phone,
            email=data.email.lower() if data.email else None,
            message=data.message,
            source=source,
            consent_at=now,
            consent_text_version=data.consent_text_version,
            last_contact_at=now,
        )
        self.repo.add(lead)
        record_event(
            self._session,
            listing_id=listing.id,
            event_type=ListingEventType.lead,
            user_id=user_id,
            request=request,
        )
        await self._session.commit()
        self._events.record(
            LeadReceived(listing.id, listing.title_en or listing.title_ar, lead.source.value, lead.phone_e164)
        )
        return lead, False

    async def inbox(self, p: Principal, listing_id: uuid.UUID | None = None) -> list[tuple[Lead, Listing]]:
        return await self.repo.inbox(p, listing_id)

    @staticmethod
    def _merge_repeat_contact(lead: Lead, message: str | None, now: datetime) -> None:
        lead.duplicate_count += 1
        lead.last_contact_at = now
        if message and message != lead.message:
            combined = f"{lead.message}\n---\n{message}" if lead.message else message
            lead.message = combined[-MAX_MESSAGE_HISTORY:]
