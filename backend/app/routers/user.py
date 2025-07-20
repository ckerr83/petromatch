from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List
from ..core.database import get_db
from ..core.security import get_current_user
from ..models.user import User
from ..models.cv import CV
import io

router = APIRouter(prefix="/user", tags=["user"])

from datetime import datetime

class CVResponse(BaseModel):
    id: int
    filename: str
    created_at: str
    
    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

@router.post("/cv", response_model=CVResponse)
async def upload_cv(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not file.filename.endswith(('.txt', '.pdf', '.doc', '.docx')):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only .txt, .pdf, .doc, .docx files are allowed"
        )
    
    content = await file.read()
    
    # Handle different file types
    if file.filename.endswith('.txt'):
        try:
            text_content = content.decode('utf-8')
        except UnicodeDecodeError:
            text_content = content.decode('latin-1', errors='ignore')
    else:
        # For binary files (PDF, DOC, etc.), store a placeholder for now
        # In production, you'd use proper parsers like PyPDF2, python-docx
        text_content = f"Binary file: {file.filename}\nFile size: {len(content)} bytes\nPlease upload a .txt file for now, or we'll implement proper parsing later."
    
    # Delete existing CV if any
    db.query(CV).filter(CV.user_id == current_user.id).delete()
    
    db_cv = CV(
        user_id=current_user.id,
        filename=file.filename,
        text_content=text_content
    )
    db.add(db_cv)
    db.commit()
    db.refresh(db_cv)
    
    return CVResponse(
        id=db_cv.id,
        filename=db_cv.filename,
        created_at=db_cv.created_at.isoformat()
    )

@router.get("/cv", response_model=CVResponse)
def get_cv(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    cv = db.query(CV).filter(CV.user_id == current_user.id).first()
    if not cv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="CV not found"
        )
    return CVResponse(
        id=cv.id,
        filename=cv.filename,
        created_at=cv.created_at.isoformat()
    )

@router.get("/cv/content")
def get_cv_content(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    cv = db.query(CV).filter(CV.user_id == current_user.id).first()
    if not cv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="CV not found"
        )
    return {"content": cv.text_content}