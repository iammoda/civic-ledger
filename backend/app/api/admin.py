"""Admin: integrity-flag review queue + corrections triage.

Access: signed-in users whose email is in ADMIN_EMAILS.
The review queue is the legal-safety keystone — flags only become
public through an explicit human 'publish' decision here.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import AuthUser, require_admin
from app.db.session import get_db
from app.models import Bill, Correction, IntegrityFlag, Person


router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])


class AdminFlagItem(BaseModel):
    id: int
    detector: str
    status: str
    headline_en: str
    detail_en: str | None = None
    confidence: float | None = None
    evidence: dict | None = None
    person_slug: str | None = None
    bill_number: str | None = None
    reviewed_by: str | None = None
    review_note: str | None = None


@router.get("/flags", response_model=list[AdminFlagItem])
def list_flags(
    status: str = Query(default="pending_review", pattern="^(pending_review|published|dismissed|all)$"),
    limit: int = Query(default=50, le=200),
    db: Session = Depends(get_db),
) -> list[AdminFlagItem]:
    query = select(IntegrityFlag).order_by(IntegrityFlag.created_at.desc()).limit(limit)
    if status != "all":
        query = query.where(IntegrityFlag.status == status)
    flags = db.scalars(query).all()

    items = []
    for flag in flags:
        person = db.get(Person, flag.person_id) if flag.person_id else None
        bill = db.get(Bill, flag.bill_id) if flag.bill_id else None
        items.append(
            AdminFlagItem(
                id=flag.id,
                detector=flag.detector,
                status=flag.status,
                headline_en=flag.headline_en,
                detail_en=flag.detail_en,
                confidence=flag.confidence,
                evidence=flag.evidence,
                person_slug=person.slug if person else None,
                bill_number=bill.number if bill else None,
                reviewed_by=flag.reviewed_by,
                review_note=flag.review_note,
            )
        )
    return items


class ReviewRequest(BaseModel):
    action: str  # publish | dismiss
    note: str | None = None


@router.post("/flags/{flag_id}", response_model=AdminFlagItem)
def review_flag(
    flag_id: int,
    payload: ReviewRequest,
    admin: AuthUser = Depends(require_admin),
    db: Session = Depends(get_db),
) -> AdminFlagItem:
    if payload.action not in {"publish", "dismiss"}:
        raise HTTPException(status_code=422, detail="action must be publish or dismiss")
    flag = db.get(IntegrityFlag, flag_id)
    if flag is None:
        raise HTTPException(status_code=404, detail="Flag not found")

    flag.status = "published" if payload.action == "publish" else "dismissed"
    flag.reviewed_by = admin.email
    flag.review_note = payload.note
    db.commit()

    person = db.get(Person, flag.person_id) if flag.person_id else None
    bill = db.get(Bill, flag.bill_id) if flag.bill_id else None
    return AdminFlagItem(
        id=flag.id,
        detector=flag.detector,
        status=flag.status,
        headline_en=flag.headline_en,
        detail_en=flag.detail_en,
        confidence=flag.confidence,
        evidence=flag.evidence,
        person_slug=person.slug if person else None,
        bill_number=bill.number if bill else None,
        reviewed_by=flag.reviewed_by,
        review_note=flag.review_note,
    )


class AdminCorrectionItem(BaseModel):
    id: int
    page_url: str
    message: str
    contact: str | None = None
    status: str
    resolution_note: str | None = None


@router.get("/corrections", response_model=list[AdminCorrectionItem])
def list_corrections(
    status: str = Query(default="open", pattern="^(open|resolved|all)$"),
    db: Session = Depends(get_db),
) -> list[AdminCorrectionItem]:
    query = select(Correction).order_by(Correction.created_at.desc()).limit(200)
    if status != "all":
        query = query.where(Correction.status == status)
    return [
        AdminCorrectionItem(
            id=c.id,
            page_url=c.page_url,
            message=c.message,
            contact=c.contact,
            status=c.status,
            resolution_note=c.resolution_note,
        )
        for c in db.scalars(query).all()
    ]


class ResolveCorrectionRequest(BaseModel):
    note: str | None = None


@router.post("/corrections/{correction_id}", response_model=AdminCorrectionItem)
def resolve_correction(
    correction_id: int,
    payload: ResolveCorrectionRequest,
    db: Session = Depends(get_db),
) -> AdminCorrectionItem:
    correction = db.get(Correction, correction_id)
    if correction is None:
        raise HTTPException(status_code=404, detail="Correction not found")
    correction.status = "resolved"
    correction.resolution_note = payload.note
    db.commit()
    return AdminCorrectionItem(
        id=correction.id,
        page_url=correction.page_url,
        message=correction.message,
        contact=correction.contact,
        status=correction.status,
        resolution_note=correction.resolution_note,
    )
