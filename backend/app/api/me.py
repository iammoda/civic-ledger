from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import AuthUser, require_user
from app.db.session import get_db
from app.models import Person, Topic, UserFollow, UserProfile
from app.services.represent import lookup_postal


router = APIRouter(tags=["me"])

VALID_TARGET_TYPES = {"topic", "person", "bill", "question"}
VALID_READING_LEVELS = {"simple", "standard", "expert"}


class MpCandidateModel(BaseModel):
    riding_name: str
    province: str | None = None
    mp_name: str
    party_name: str | None = None
    person_slug: str | None = None


class PostalLookupResponse(BaseModel):
    candidates: list[MpCandidateModel]
    ambiguous: bool


@router.get("/lookup/postal/{code}", response_model=PostalLookupResponse)
async def postal_lookup(code: str, db: Session = Depends(get_db)) -> PostalLookupResponse:
    """Anonymous-first: works without an account; nothing is stored."""
    candidates = await lookup_postal(db, code)
    if candidates is None:
        raise HTTPException(status_code=502, detail="Postal lookup unavailable or invalid postal code")
    return PostalLookupResponse(
        candidates=[
            MpCandidateModel(
                riding_name=c.riding_name,
                province=c.province,
                mp_name=c.mp_name,
                party_name=c.party_name,
                person_slug=c.person_slug,
            )
            for c in candidates
        ],
        ambiguous=len(candidates) > 1,
    )


class ProfileModel(BaseModel):
    riding_name: str | None = None
    province_code: str | None = None
    mp_slug: str | None = None
    mp_name: str | None = None
    reading_level: str = "standard"


class FollowModel(BaseModel):
    target_type: str
    target_ref: str
    label: str | None = None


class MeResponse(BaseModel):
    user_id: str
    email: str
    name: str
    profile: ProfileModel
    follows: list[FollowModel]


def _profile_of(db: Session, user_id: str) -> UserProfile | None:
    return db.get(UserProfile, user_id)


def _follow_label(db: Session, follow: UserFollow) -> str | None:
    if follow.target_type == "topic":
        topic = db.scalar(select(Topic).where(Topic.slug == follow.target_ref))
        return topic.name_en if topic else None
    if follow.target_type == "person":
        person = db.scalar(select(Person).where(Person.slug == follow.target_ref))
        return person.full_name if person else None
    return None


def _me_response(db: Session, user: AuthUser) -> MeResponse:
    profile = _profile_of(db, user.id)
    mp = None
    if profile is not None and profile.mp_person_id is not None:
        mp = db.get(Person, profile.mp_person_id)
    follows = db.scalars(
        select(UserFollow).where(UserFollow.user_id == user.id).order_by(UserFollow.created_at)
    ).all()
    return MeResponse(
        user_id=user.id,
        email=user.email,
        name=user.name,
        profile=ProfileModel(
            riding_name=profile.riding_name if profile else None,
            province_code=profile.province_code if profile else None,
            mp_slug=mp.slug if mp else None,
            mp_name=mp.full_name if mp else None,
            reading_level=profile.reading_level if profile else "standard",
        ),
        follows=[
            FollowModel(target_type=f.target_type, target_ref=f.target_ref, label=_follow_label(db, f))
            for f in follows
        ],
    )


@router.get("/me", response_model=MeResponse)
def get_me(user: AuthUser = Depends(require_user), db: Session = Depends(get_db)) -> MeResponse:
    return _me_response(db, user)


class ProfileUpdate(BaseModel):
    riding_name: str | None = Field(default=None, max_length=255)
    province_code: str | None = Field(default=None, max_length=8)
    mp_slug: str | None = Field(default=None, max_length=255)
    reading_level: str | None = None


@router.put("/me/profile", response_model=MeResponse)
def update_profile(
    payload: ProfileUpdate,
    user: AuthUser = Depends(require_user),
    db: Session = Depends(get_db),
) -> MeResponse:
    profile = _profile_of(db, user.id)
    if profile is None:
        profile = UserProfile(user_id=user.id)
        db.add(profile)

    if payload.reading_level is not None:
        if payload.reading_level not in VALID_READING_LEVELS:
            raise HTTPException(status_code=422, detail="Invalid reading level")
        profile.reading_level = payload.reading_level
    if payload.riding_name is not None:
        profile.riding_name = payload.riding_name or None
    if payload.province_code is not None:
        profile.province_code = payload.province_code or None
    if payload.mp_slug is not None:
        if payload.mp_slug == "":
            profile.mp_person_id = None
        else:
            person = db.scalar(select(Person).where(Person.slug == payload.mp_slug))
            if person is None:
                raise HTTPException(status_code=404, detail="MP not found")
            profile.mp_person_id = person.id

    db.commit()
    return _me_response(db, user)


class FollowRequest(BaseModel):
    target_type: str
    target_ref: str = Field(min_length=1, max_length=500)


@router.post("/me/follows", response_model=MeResponse, status_code=201)
def add_follow(
    payload: FollowRequest,
    user: AuthUser = Depends(require_user),
    db: Session = Depends(get_db),
) -> MeResponse:
    if payload.target_type not in VALID_TARGET_TYPES:
        raise HTTPException(status_code=422, detail=f"target_type must be one of {sorted(VALID_TARGET_TYPES)}")
    if payload.target_type == "topic":
        if db.scalar(select(Topic).where(Topic.slug == payload.target_ref)) is None:
            raise HTTPException(status_code=404, detail="Unknown topic")
    if payload.target_type == "person":
        if db.scalar(select(Person).where(Person.slug == payload.target_ref)) is None:
            raise HTTPException(status_code=404, detail="Unknown person")

    existing = db.scalar(
        select(UserFollow).where(
            UserFollow.user_id == user.id,
            UserFollow.target_type == payload.target_type,
            UserFollow.target_ref == payload.target_ref,
        )
    )
    if existing is None:
        db.add(UserFollow(user_id=user.id, target_type=payload.target_type, target_ref=payload.target_ref))
        db.commit()
    return _me_response(db, user)


@router.delete("/me/follows", response_model=MeResponse)
def remove_follow(
    target_type: str = Query(),
    target_ref: str = Query(),
    user: AuthUser = Depends(require_user),
    db: Session = Depends(get_db),
) -> MeResponse:
    follow = db.scalar(
        select(UserFollow).where(
            UserFollow.user_id == user.id,
            UserFollow.target_type == target_type,
            UserFollow.target_ref == target_ref,
        )
    )
    if follow is not None:
        db.delete(follow)
        db.commit()
    return _me_response(db, user)


class TopicItem(BaseModel):
    slug: str
    name_en: str
    description_en: str | None = None


@router.get("/topics", response_model=list[TopicItem])
def list_topics(db: Session = Depends(get_db)) -> list[TopicItem]:
    topics = db.scalars(select(Topic).order_by(Topic.name_en)).all()
    return [TopicItem(slug=t.slug, name_en=t.name_en, description_en=t.description_en) for t in topics]
