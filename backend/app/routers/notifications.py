from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List
from ..core.database import get_db
from ..core.security import get_current_user
from ..models.user import User
from ..models.email_notification import EmailNotification

router = APIRouter(prefix="/notifications", tags=["notifications"])

class EmailNotificationRequest(BaseModel):
    cron_schedule: str

class EmailNotificationResponse(BaseModel):
    id: int
    cron_schedule: str
    last_sent: str = None
    
    class Config:
        from_attributes = True

@router.post("/email", response_model=EmailNotificationResponse)
def create_email_notification(
    request: EmailNotificationRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Delete existing notification if any
    db.query(EmailNotification).filter(EmailNotification.user_id == current_user.id).delete()
    
    notification = EmailNotification(
        user_id=current_user.id,
        cron_schedule=request.cron_schedule
    )
    db.add(notification)
    db.commit()
    db.refresh(notification)
    
    return notification

@router.get("/email", response_model=EmailNotificationResponse)
def get_email_notification(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    notification = db.query(EmailNotification).filter(
        EmailNotification.user_id == current_user.id
    ).first()
    
    if not notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Email notification not found"
        )
    
    return notification

@router.delete("/email")
def delete_email_notification(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    notification = db.query(EmailNotification).filter(
        EmailNotification.user_id == current_user.id
    ).first()
    
    if not notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Email notification not found"
        )
    
    db.delete(notification)
    db.commit()
    
    return {"message": "Email notification deleted"}