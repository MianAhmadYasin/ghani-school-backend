from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime, date, time


class EventBase(BaseModel):
    title: str
    description: Optional[str] = None
    date: date
    time: Optional[str] = None  # Format: "HH:MM:SS"
    location: Optional[str] = None
    type: str  # academic, sports, cultural, meeting, other
    status: str = "upcoming"  # upcoming, ongoing, completed, cancelled


class EventCreate(EventBase):
    """Schema for creating a new event"""
    pass


class EventUpdate(BaseModel):
    """Schema for updating an event - all fields optional"""
    title: Optional[str] = None
    description: Optional[str] = None
    date: Optional[date] = None
    time: Optional[str] = None
    location: Optional[str] = None
    type: Optional[str] = None
    status: Optional[str] = None


class EventResponse(EventBase):
    """Schema for event response"""
    id: str
    created_by: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class EventStats(BaseModel):
    """Statistics for events"""
    total_events: int
    upcoming_events: int
    ongoing_events: int
    completed_events: int
    events_by_type: dict
    events_this_month: int
