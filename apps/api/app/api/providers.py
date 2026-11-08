"""Composition root for request-scoped services (Dependency Injection).

Routes declare *what* they need (``ListingServiceDep``); this module decides *how* it is built. Tests and
future variants (e.g. a moderation policy, a Redis cache, another notifier) change wiring here only.
"""

from typing import Annotated

from fastapi import BackgroundTasks, Depends

from app.api.deps import SessionDep
from app.core.config import Settings, get_settings
from app.core.events import BackgroundEventRecorder, EventRecorder, get_event_bus
from app.repositories.locations import LocationDirectory
from app.search.engine import SmartSearch
from app.services.api_tokens import ApiTokenService
from app.services.areas import AreaProfileService
from app.services.auth import AccountService, TokenService
from app.services.discovery import DiscoveryService
from app.services.import_csv import ListingImporter
from app.services.leads import LeadService
from app.services.listings import ContactService, ListingMediaService, ListingService
from app.services.tickets import TicketService
from app.services.user_admin import UserAdminService
from app.storage import StorageBackend, get_storage

SettingsDep = Annotated[Settings, Depends(get_settings)]
StorageDep = Annotated[StorageBackend, Depends(get_storage)]


def get_event_recorder(background: BackgroundTasks) -> EventRecorder:
    return BackgroundEventRecorder(get_event_bus(), background)


EventsDep = Annotated[EventRecorder, Depends(get_event_recorder)]


def get_listing_service(session: SessionDep, settings: SettingsDep, events: EventsDep) -> ListingService:
    return ListingService(session, settings=settings, events=events)


ListingServiceDep = Annotated[ListingService, Depends(get_listing_service)]


def get_media_service(
    session: SessionDep, settings: SettingsDep, storage: StorageDep, listings: ListingServiceDep
) -> ListingMediaService:
    return ListingMediaService(session, settings=settings, storage=storage, listings=listings)


def get_contact_service(
    session: SessionDep, settings: SettingsDep, listings: ListingServiceDep
) -> ContactService:
    return ContactService(session, settings=settings, listings=listings)


def get_lead_service(
    session: SessionDep, settings: SettingsDep, events: EventsDep, listings: ListingServiceDep
) -> LeadService:
    return LeadService(session, settings=settings, events=events, listings=listings)


def get_importer(session: SessionDep, events: EventsDep, listings: ListingServiceDep) -> ListingImporter:
    return ListingImporter(session, listings=listings, events=events)


def get_account_service(session: SessionDep, events: EventsDep) -> AccountService:
    return AccountService(session, events=events)


def get_token_service(session: SessionDep, settings: SettingsDep) -> TokenService:
    return TokenService(session, settings=settings)


def get_location_directory(session: SessionDep) -> LocationDirectory:
    return LocationDirectory(session)


MediaServiceDep = Annotated[ListingMediaService, Depends(get_media_service)]
ContactServiceDep = Annotated[ContactService, Depends(get_contact_service)]
LeadServiceDep = Annotated[LeadService, Depends(get_lead_service)]
ImporterDep = Annotated[ListingImporter, Depends(get_importer)]
AccountServiceDep = Annotated[AccountService, Depends(get_account_service)]
TokenServiceDep = Annotated[TokenService, Depends(get_token_service)]
LocationDirectoryDep = Annotated[LocationDirectory, Depends(get_location_directory)]


def get_ticket_service(
    session: SessionDep, settings: SettingsDep, storage: StorageDep, events: EventsDep
) -> TicketService:
    return TicketService(session, settings=settings, storage=storage, events=events)


def get_user_admin(session: SessionDep) -> UserAdminService:
    return UserAdminService(session)


def get_api_tokens(session: SessionDep) -> ApiTokenService:
    return ApiTokenService(session)


TicketServiceDep = Annotated[TicketService, Depends(get_ticket_service)]
UserAdminDep = Annotated[UserAdminService, Depends(get_user_admin)]
ApiTokensDep = Annotated[ApiTokenService, Depends(get_api_tokens)]


def get_area_service(session: SessionDep, settings: SettingsDep) -> AreaProfileService:
    return AreaProfileService(session, include_demo=settings.demo_mode)


AreaServiceDep = Annotated[AreaProfileService, Depends(get_area_service)]


def get_smart_search(session: SessionDep, listings: ListingServiceDep, areas: AreaServiceDep) -> SmartSearch:
    return SmartSearch(session, listings=listings, areas=areas)


SmartSearchDep = Annotated[SmartSearch, Depends(get_smart_search)]


def get_discovery(
    session: SessionDep, settings: SettingsDep, listings: ListingServiceDep
) -> DiscoveryService:
    return DiscoveryService(session, settings=settings, listings=listings)


DiscoveryDep = Annotated[DiscoveryService, Depends(get_discovery)]
