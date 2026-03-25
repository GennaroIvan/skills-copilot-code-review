"""
Announcement endpoints for the High School Management System API
"""

from datetime import date
from typing import Any, Dict, List, Optional
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from ..database import announcements_collection, teachers_collection

router = APIRouter(
    prefix="/announcements",
    tags=["announcements"]
)


class AnnouncementPayload(BaseModel):
    """Announcement payload for create/update operations."""

    message: str = Field(min_length=1, max_length=280)
    expires_at: date
    starts_at: Optional[date] = None


class AnnouncementResponse(BaseModel):
    """Announcement response model returned to clients."""

    id: str
    message: str
    expires_at: str
    starts_at: Optional[str] = None


def _is_authenticated_teacher(teacher_username: Optional[str]) -> bool:
    """Validate teacher access for management operations."""
    if not teacher_username:
        return False
    return teachers_collection.find_one({"_id": teacher_username}) is not None


def _to_response(document: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize DB announcement document for API responses."""
    return {
        "id": document["_id"],
        "message": document["message"],
        "starts_at": document.get("starts_at"),
        "expires_at": document["expires_at"]
    }


def _validate_date_window(payload: AnnouncementPayload) -> None:
    """Reject announcements with an invalid start/end date window."""
    if payload.starts_at and payload.starts_at > payload.expires_at:
        raise HTTPException(
            status_code=400,
            detail="Start date must be earlier than or equal to expiration date"
        )


@router.get("", response_model=List[AnnouncementResponse])
def get_active_announcements() -> List[Dict[str, Any]]:
    """Return currently active, non-expired announcements for all users."""
    today = date.today().isoformat()
    query = {
        "expires_at": {"$gte": today},
        "$or": [
            {"starts_at": None},
            {"starts_at": {"$exists": False}},
            {"starts_at": {"$lte": today}}
        ]
    }

    cursor = announcements_collection.find(query).sort("expires_at", 1)
    return [_to_response(doc) for doc in cursor]


@router.get("/all", response_model=List[AnnouncementResponse])
def get_all_announcements(teacher_username: Optional[str] = Query(None)) -> List[Dict[str, Any]]:
    """Return all announcements for authenticated teachers/admins."""
    if not _is_authenticated_teacher(teacher_username):
        raise HTTPException(status_code=401, detail="Authentication required for this action")

    cursor = announcements_collection.find({}).sort("expires_at", 1)
    return [_to_response(doc) for doc in cursor]


@router.post("", response_model=AnnouncementResponse)
def create_announcement(payload: AnnouncementPayload, teacher_username: Optional[str] = Query(None)) -> Dict[str, Any]:
    """Create a new announcement for authenticated teachers/admins."""
    if not _is_authenticated_teacher(teacher_username):
        raise HTTPException(status_code=401, detail="Authentication required for this action")

    _validate_date_window(payload)

    announcement_id = f"announcement-{uuid4().hex[:12]}"
    document = {
        "_id": announcement_id,
        "message": payload.message.strip(),
        "starts_at": payload.starts_at.isoformat() if payload.starts_at else None,
        "expires_at": payload.expires_at.isoformat()
    }

    announcements_collection.insert_one(document)
    return _to_response(document)


@router.put("/{announcement_id}", response_model=AnnouncementResponse)
def update_announcement(
    announcement_id: str,
    payload: AnnouncementPayload,
    teacher_username: Optional[str] = Query(None)
) -> Dict[str, Any]:
    """Update an existing announcement for authenticated teachers/admins."""
    if not _is_authenticated_teacher(teacher_username):
        raise HTTPException(status_code=401, detail="Authentication required for this action")

    _validate_date_window(payload)

    updated_fields = {
        "message": payload.message.strip(),
        "starts_at": payload.starts_at.isoformat() if payload.starts_at else None,
        "expires_at": payload.expires_at.isoformat()
    }

    result = announcements_collection.update_one(
        {"_id": announcement_id},
        {"$set": updated_fields}
    )

    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Announcement not found")

    updated_document = announcements_collection.find_one({"_id": announcement_id})
    if not updated_document:
        raise HTTPException(status_code=404, detail="Announcement not found")

    return _to_response(updated_document)


@router.delete("/{announcement_id}")
def delete_announcement(announcement_id: str, teacher_username: Optional[str] = Query(None)) -> Dict[str, str]:
    """Delete an announcement for authenticated teachers/admins."""
    if not _is_authenticated_teacher(teacher_username):
        raise HTTPException(status_code=401, detail="Authentication required for this action")

    result = announcements_collection.delete_one({"_id": announcement_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Announcement not found")

    return {"message": "Announcement deleted"}
