from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.auth import AuthUser, require_user
from app.db.session import get_db
from app.models import Bill, EntityTopic, Notification, Topic, UserFollow
from app.services.notifications import parliament_is_sitting


router = APIRouter(tags=["feed"])


class NotificationItem(BaseModel):
    id: int
    kind: str
    title_en: str
    body_en: str | None = None
    url_path: str | None = None
    matched_follow: str | None = None
    is_read: bool
    created_at_date: str | None = None


@router.get("/me/notifications", response_model=list[NotificationItem])
def list_notifications(
    unread_only: bool = Query(default=False),
    limit: int = Query(default=50, le=200),
    user: AuthUser = Depends(require_user),
    db: Session = Depends(get_db),
) -> list[NotificationItem]:
    query = select(Notification).where(Notification.user_id == user.id)
    if unread_only:
        query = query.where(Notification.is_read.is_(False))
    rows = db.scalars(query.order_by(Notification.created_at.desc()).limit(limit)).all()
    return [
        NotificationItem(
            id=n.id,
            kind=n.kind,
            title_en=n.title_en,
            body_en=n.body_en,
            url_path=n.url_path,
            matched_follow=n.matched_follow,
            is_read=n.is_read,
            created_at_date=n.created_at.date().isoformat() if n.created_at else None,
        )
        for n in rows
    ]


class MarkReadRequest(BaseModel):
    ids: list[int] | None = None  # None = mark all read


@router.post("/me/notifications/read")
def mark_read(
    payload: MarkReadRequest,
    user: AuthUser = Depends(require_user),
    db: Session = Depends(get_db),
) -> dict:
    query = select(Notification).where(Notification.user_id == user.id, Notification.is_read.is_(False))
    if payload.ids:
        query = query.where(Notification.id.in_(payload.ids))
    count = 0
    for notification in db.scalars(query).all():
        notification.is_read = True
        count += 1
    db.commit()
    return {"marked_read": count}


class FeedSuggestion(BaseModel):
    title: str
    detail: str | None = None
    url_path: str


class FeedResponse(BaseModel):
    parliament_sitting: bool
    unread_count: int
    notifications: list[NotificationItem]
    # When the feed is quiet: recent activity in followed topics.
    suggestions: list[FeedSuggestion]
    followed_topics: list[str]


@router.get("/me/feed", response_model=FeedResponse)
def get_feed(
    user: AuthUser = Depends(require_user),
    db: Session = Depends(get_db),
) -> FeedResponse:
    unread_count = db.scalar(
        select(func.count())
        .select_from(Notification)
        .where(Notification.user_id == user.id, Notification.is_read.is_(False))
    ) or 0

    notifications = db.scalars(
        select(Notification)
        .where(Notification.user_id == user.id)
        .order_by(Notification.is_read.asc(), Notification.created_at.desc())
        .limit(30)
    ).all()

    followed_topic_slugs = [
        f.target_ref
        for f in db.scalars(
            select(UserFollow).where(UserFollow.user_id == user.id, UserFollow.target_type == "topic")
        ).all()
    ]

    # Never-empty feed: when quiet, seed with the latest bills in followed
    # topics (recess-aware wording handled by parliament_sitting).
    suggestions: list[FeedSuggestion] = []
    if len(notifications) < 5 and followed_topic_slugs:
        topic_ids = [
            t.id
            for t in db.scalars(select(Topic).where(Topic.slug.in_(followed_topic_slugs))).all()
        ]
        if topic_ids:
            bill_ids = {
                row[0]
                for row in db.execute(
                    select(EntityTopic.entity_id).where(
                        EntityTopic.entity_type == "bill", EntityTopic.topic_id.in_(topic_ids)
                    )
                ).all()
            }
            if bill_ids:
                bills = db.scalars(
                    select(Bill)
                    .options(selectinload(Bill.session))
                    .where(Bill.id.in_(bill_ids))
                    .order_by(Bill.introduced_on.desc().nullslast())
                    .limit(8)
                ).all()
                suggestions = [
                    FeedSuggestion(
                        title=f"{bill.number} — {bill.short_title_en or bill.title_en}",
                        detail=bill.status_en,
                        url_path=f"/bills/{bill.session.label}/{bill.number}",
                    )
                    for bill in bills
                ]

    return FeedResponse(
        parliament_sitting=parliament_is_sitting(db),
        unread_count=unread_count,
        notifications=[
            NotificationItem(
                id=n.id,
                kind=n.kind,
                title_en=n.title_en,
                body_en=n.body_en,
                url_path=n.url_path,
                matched_follow=n.matched_follow,
                is_read=n.is_read,
                created_at_date=n.created_at.date().isoformat() if n.created_at else None,
            )
            for n in notifications
        ],
        suggestions=suggestions,
        followed_topics=followed_topic_slugs,
    )
