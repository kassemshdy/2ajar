import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.authz.policies import (
    ListingRef,
    Principal,
    can_create_listing,
    can_manage_listing,
    can_view_listing,
    is_publicly_visible,
)
from app.models.enums import ListingStatus, OrgRole, UserRole

NOW = datetime(2026, 11, 5, tzinfo=UTC)
ORG_A, ORG_B = uuid.uuid4(), uuid.uuid4()
CREATOR = uuid.uuid4()


def listing(**kw: object) -> ListingRef:
    base: dict[str, object] = dict(
        created_by_user_id=CREATOR,
        organization_id=ORG_A,
        status=ListingStatus.published,
        expires_at=NOW + timedelta(days=5),
        is_demo=False,
    )
    base.update(kw)
    return ListingRef(**base)  # type: ignore[arg-type]


CASES = [
    ("creator", Principal(CREATOR, UserRole.broker, {ORG_A: OrgRole.agent}), True),
    ("agency admin same org", Principal(uuid.uuid4(), UserRole.broker, {ORG_A: OrgRole.agency_admin}), True),
    ("agent same org", Principal(uuid.uuid4(), UserRole.broker, {ORG_A: OrgRole.agent}), False),
    (
        "agency admin other org",
        Principal(uuid.uuid4(), UserRole.broker, {ORG_B: OrgRole.agency_admin}),
        False,
    ),
    ("seeker", Principal(uuid.uuid4(), UserRole.seeker), False),
    ("other owner", Principal(uuid.uuid4(), UserRole.owner), False),
    ("platform admin", Principal(uuid.uuid4(), UserRole.platform_admin), True),
    ("anonymous", None, False),
]


@pytest.mark.parametrize(("name", "principal", "expected"), CASES, ids=[c[0] for c in CASES])
def test_manage_matrix(name: str, principal: Principal | None, expected: bool) -> None:
    assert can_manage_listing(principal, listing()) is expected


def test_owner_listing_without_org_only_creator() -> None:
    ref = listing(organization_id=None)
    assert can_manage_listing(Principal(CREATOR, UserRole.owner), ref)
    assert not can_manage_listing(
        Principal(uuid.uuid4(), UserRole.broker, {ORG_A: OrgRole.agency_admin}), ref
    )


@pytest.mark.parametrize(
    ("role", "allowed"),
    [
        (UserRole.seeker, False),
        (UserRole.owner, True),
        (UserRole.broker, True),
        (UserRole.platform_admin, True),
    ],
)
def test_create_listing_roles(role: UserRole, allowed: bool) -> None:
    assert can_create_listing(Principal(uuid.uuid4(), role)) is allowed


@pytest.mark.parametrize(
    ("kw", "demo_mode", "visible"),
    [
        ({}, False, True),
        ({"status": ListingStatus.draft}, False, False),
        ({"status": ListingStatus.paused}, False, False),
        ({"status": ListingStatus.pending_review}, False, False),
        ({"expires_at": NOW - timedelta(seconds=1)}, False, False),
        ({"is_demo": True}, False, False),
        ({"is_demo": True}, True, True),
    ],
)
def test_public_visibility(kw: dict[str, object], demo_mode: bool, visible: bool) -> None:
    assert is_publicly_visible(listing(**kw), NOW, demo_mode) is visible


def test_manager_can_view_draft_but_public_cannot() -> None:
    draft = listing(status=ListingStatus.draft)
    assert can_view_listing(Principal(CREATOR, UserRole.broker), draft, NOW, False)
    assert not can_view_listing(None, draft, NOW, False)
    assert not can_view_listing(Principal(uuid.uuid4(), UserRole.seeker), draft, NOW, False)
