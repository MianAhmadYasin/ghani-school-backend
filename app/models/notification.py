from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class NotificationBase(BaseModel):
    """Base notification schema"""
    title: str
    body: str
    link: Optional[str] = None
    announcement_id: Optional[str] = None


class NotificationCreate(NotificationBase):
    """Schema for creating a notification"""
    user_id: str


class NotificationUpdate(BaseModel):
    """Schema for updating notification - all fields optional"""
    title: Optional[str] = None
    body: Optional[str] = None
    link: Optional[str] = None
    read_at: Optional[datetime] = None


class NotificationResponse(NotificationBase):
    """Schema for notification response"""
    id: str
    user_id: str
    read_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


class NotificationStats(BaseModel):
    """Statistics for notifications"""
    total_notifications: int
    unread_count: int
    read_count: int
    notifications_by_type: dict









