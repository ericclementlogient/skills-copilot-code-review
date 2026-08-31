"""
Endpoints for managing school announcements
"""

import uuid
from datetime import date

from fastapi import APIRouter, HTTPException, Query
from typing import Any, Dict, List, Optional

from ..database import announcements_collection, teachers_collection

router = APIRouter(
    prefix="/announcements",
    tags=["announcements"]
)


def _require_teacher(teacher_username: Optional[str]):
    """Raise 401 unless teacher_username maps to a known teacher account"""
    if not teacher_username:
        raise HTTPException(
            status_code=401, detail="Authentication required for this action")

    teacher = teachers_collection.find_one({"_id": teacher_username})
    if not teacher:
        raise HTTPException(
            status_code=401, detail="Invalid teacher credentials")


def _serialize(announcement: Dict[str, Any]) -> Dict[str, Any]:
    announcement = dict(announcement)
    announcement["id"] = announcement.pop("_id")
    return announcement


@router.get("/active", response_model=List[Dict[str, Any]])
def get_active_announcements() -> List[Dict[str, Any]]:
    """Get announcements currently visible to all users (public, no auth required)"""
    today = date.today().isoformat()
    query = {
        "expiration_date": {"$gte": today},
        "$or": [
            {"start_date": None},
            {"start_date": {"$lte": today}}
        ]
    }

    return [_serialize(a) for a in announcements_collection.find(query)]


@router.get("", response_model=List[Dict[str, Any]])
@router.get("/", response_model=List[Dict[str, Any]])
def get_all_announcements(teacher_username: Optional[str] = Query(None)) -> List[Dict[str, Any]]:
    """Get all announcements for management - requires teacher authentication"""
    _require_teacher(teacher_username)

    announcements = announcements_collection.find().sort("expiration_date", 1)
    return [_serialize(a) for a in announcements]


@router.post("", response_model=Dict[str, Any])
@router.post("/", response_model=Dict[str, Any])
def create_announcement(
    message: str,
    expiration_date: str,
    start_date: Optional[str] = None,
    teacher_username: Optional[str] = Query(None)
) -> Dict[str, Any]:
    """Create a new announcement - requires teacher authentication"""
    _require_teacher(teacher_username)

    try:
        expiration = date.fromisoformat(expiration_date)
        start = date.fromisoformat(start_date) if start_date else None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Dates must be in YYYY-MM-DD format") from exc

    if start and start > expiration:
        raise HTTPException(
            status_code=400, detail="Start date must be before the expiration date")

    expiration_date = expiration.isoformat()
    start_date = start.isoformat() if start else None
    announcement = {
        "_id": str(uuid.uuid4()),
        "message": message,
        "start_date": start_date,
        "expiration_date": expiration_date,
        "created_by": teacher_username
    }
    announcements_collection.insert_one(announcement)

    return _serialize(announcement)


@router.put("/{announcement_id}", response_model=Dict[str, Any])
def update_announcement(
    announcement_id: str,
    message: str,
    expiration_date: str,
    start_date: Optional[str] = None,
    teacher_username: Optional[str] = Query(None)
) -> Dict[str, Any]:
    """Update an existing announcement - requires teacher authentication"""
    _require_teacher(teacher_username)

    if start_date and start_date > expiration_date:
        raise HTTPException(
            status_code=400, detail="Start date must be before the expiration date")

    announcement = announcements_collection.find_one({"_id": announcement_id})
    if not announcement:
        raise HTTPException(status_code=404, detail="Announcement not found")

    updated_fields = {
        "message": message,
        "start_date": start_date,
        "expiration_date": expiration_date
    }
    announcements_collection.update_one(
        {"_id": announcement_id}, {"$set": updated_fields})

    return _serialize({**announcement, **updated_fields})


@router.delete("/{announcement_id}")
def delete_announcement(announcement_id: str, teacher_username: Optional[str] = Query(None)):
    """Delete an announcement - requires teacher authentication"""
    _require_teacher(teacher_username)

    result = announcements_collection.delete_one({"_id": announcement_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Announcement not found")

    return {"message": "Announcement deleted"}
