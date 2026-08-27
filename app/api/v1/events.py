"""
Event Management Endpoints
Handles event creation, updating, listing, and configuration for organizers.
"""

import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.database import get_db
from app.models import Event, User, Participant, Certificate
from app.schemas.event import EventCreate, EventUpdate, EventResponse, EventDetailResponse
from app.api.deps import get_current_user

router = APIRouter(prefix="/events", tags=["Events"])


@router.get("/", response_model=List[EventResponse])
def list_events(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Lists all events organized by the authenticated user with aggregate stats"""
    events = db.query(Event).filter(Event.user_id == current_user.id).order_by(Event.created_at.desc()).all()
    
    result = []
    for ev in events:
        p_count = db.query(func.count(Participant.id)).filter(Participant.event_id == ev.id).scalar() or 0
        c_count = db.query(func.count(Certificate.id)).filter(
            Certificate.event_id == ev.id,
            Certificate.status == "GENERATED"
        ).scalar() or 0
        
        ev_dict = {
            "id": ev.id,
            "user_id": ev.user_id,
            "name": ev.name,
            "location": ev.location,
            "event_date": ev.event_date,
            "description": ev.description,
            "status": ev.status,
            "created_at": ev.created_at,
            "updated_at": ev.updated_at,
            "participant_count": p_count,
            "certificate_count": c_count,
        }
        result.append(ev_dict)
    
    return result


@router.post("/", response_model=EventResponse, status_code=status.HTTP_201_CREATED)
def create_event(
    event_in: EventCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Creates a new event (Conference, Webinar, Workshop)"""
    event = Event(
        user_id=current_user.id,
        name=event_in.name,
        location=event_in.location,
        event_date=event_in.event_date,
        description=event_in.description,
        status="draft"
    )
    db.add(event)
    db.commit()
    db.refresh(event)

    return {
        "id": event.id,
        "user_id": event.user_id,
        "name": event.name,
        "location": event.location,
        "event_date": event.event_date,
        "description": event.description,
        "status": event.status,
        "created_at": event.created_at,
        "updated_at": event.updated_at,
        "participant_count": 0,
        "certificate_count": 0,
    }


@router.get("/{event_id}", response_model=EventDetailResponse)
def get_event_detail(
    event_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Gets single event details including attached certificate template and fields"""
    event = db.query(Event).filter(Event.id == event_id, Event.user_id == current_user.id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Acara tidak ditemukan.")

    p_count = db.query(func.count(Participant.id)).filter(Participant.event_id == event.id).scalar() or 0
    c_count = db.query(func.count(Certificate.id)).filter(
        Certificate.event_id == event.id,
        Certificate.status == "GENERATED"
    ).scalar() or 0

    return {
        "id": event.id,
        "user_id": event.user_id,
        "name": event.name,
        "location": event.location,
        "event_date": event.event_date,
        "description": event.description,
        "status": event.status,
        "created_at": event.created_at,
        "updated_at": event.updated_at,
        "participant_count": p_count,
        "certificate_count": c_count,
        "template": event.template
    }


@router.put("/{event_id}", response_model=EventResponse)
def update_event(
    event_id: uuid.UUID,
    event_update: EventUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Updates event parameters"""
    event = db.query(Event).filter(Event.id == event_id, Event.user_id == current_user.id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Acara tidak ditemukan.")

    update_data = event_update.model_dump(exclude_unset=True)
    for field, val in update_data.items():
        setattr(event, field, val)

    db.commit()
    db.refresh(event)

    p_count = db.query(func.count(Participant.id)).filter(Participant.event_id == event.id).scalar() or 0
    c_count = db.query(func.count(Certificate.id)).filter(Certificate.event_id == event.id).scalar() or 0

    return {
        "id": event.id,
        "user_id": event.user_id,
        "name": event.name,
        "location": event.location,
        "event_date": event.event_date,
        "description": event.description,
        "status": event.status,
        "created_at": event.created_at,
        "updated_at": event.updated_at,
        "participant_count": p_count,
        "certificate_count": c_count,
    }


@router.delete("/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_event(
    event_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Deletes an event and all associated templates, participants, and certificates"""
    event = db.query(Event).filter(Event.id == event_id, Event.user_id == current_user.id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Acara tidak ditemukan.")

    db.delete(event)
    db.commit()
    return None
