from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List
from ..core.database import get_db
from ..core.security import get_current_user
from ..models.user import User
from ..models.job_board import JobBoard
from ..models.scrape_task import ScrapeTask
from ..models.job_listing import JobListing
from ..models.match import Match
from ..workers.simple_scraper import simple_scrape_jobs
import threading

router = APIRouter(prefix="/jobs", tags=["jobs"])

class BoardResponse(BaseModel):
    id: int
    name: str
    login_required: bool
    base_url: str
    
    class Config:
        from_attributes = True

class ScrapeRequest(BaseModel):
    board_ids: List[int]

class ScrapeResponse(BaseModel):
    task_id: int
    status: str

class TaskStatusResponse(BaseModel):
    task_id: int
    status: str
    created_at: str

class JobListingResponse(BaseModel):
    id: int
    title: str
    company: str
    location: str
    url: str
    description: str
    
    class Config:
        from_attributes = True

class MatchResponse(BaseModel):
    id: int
    listing: JobListingResponse
    score: float
    matched_at: str
    
    class Config:
        from_attributes = True

class MatchRequest(BaseModel):
    task_id: int

class TailorCVRequest(BaseModel):
    job_id: int

@router.get("/boards", response_model=List[BoardResponse])
def get_boards(db: Session = Depends(get_db)):
    boards = db.query(JobBoard).all()
    return boards

@router.post("/scrape", response_model=ScrapeResponse)
def start_scrape(
    request: ScrapeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Create scrape task
    task = ScrapeTask(user_id=current_user.id, status="pending")
    db.add(task)
    db.commit()
    db.refresh(task)
    
    # Associate boards with task
    boards = db.query(JobBoard).filter(JobBoard.id.in_(request.board_ids)).all()
    task.boards = boards
    db.commit()
    
    # Start scraping job in background thread
    threading.Thread(target=simple_scrape_jobs, args=(task.id,), daemon=True).start()
    
    return {"task_id": task.id, "status": task.status}

@router.get("/status/{task_id}", response_model=TaskStatusResponse)
def get_task_status(
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    task = db.query(ScrapeTask).filter(
        ScrapeTask.id == task_id,
        ScrapeTask.user_id == current_user.id
    ).first()
    
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found"
        )
    
    return TaskStatusResponse(
        task_id=task.id,
        status=task.status,
        created_at=task.created_at.isoformat()
    )

@router.get("/results/{task_id}", response_model=List[JobListingResponse])
def get_task_results(
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    task = db.query(ScrapeTask).filter(
        ScrapeTask.id == task_id,
        ScrapeTask.user_id == current_user.id
    ).first()
    
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found"
        )
    
    return task.job_listings

@router.post("/match")
def start_matching(
    request: MatchRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    task = db.query(ScrapeTask).filter(
        ScrapeTask.id == request.task_id,
        ScrapeTask.user_id == current_user.id
    ).first()
    
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found"
        )
    
    # Get user's CV for matching
    from ..models.cv import CV
    from ..models.match import Match
    import re
    
    cv = db.query(CV).filter(CV.user_id == current_user.id).first()
    if not cv:
        raise HTTPException(status_code=404, detail="CV not found")
    
    cv_text = cv.text_content.lower()
    
    # Check if CV content is properly extracted
    is_binary_cv = 'binary file:' in cv_text or 'file size:' in cv_text
    if is_binary_cv:
        print("Warning: CV is binary PDF, using simplified matching")
    
    def calculate_job_match_score(job_title: str, job_description: str, cv_content: str) -> float:
        """Calculate matching score between job and CV based on keywords and skills"""
        
        job_text = (job_title + " " + job_description).lower()
        
        # If CV is binary/unextracted, use job-type based scoring
        if is_binary_cv:
            # Score based on job type for oil & gas professionals
            engineering_job_words = ['engineer', 'technical', 'drilling', 'production', 'petroleum', 'mechanical', 'electrical', 'chemical']
            management_job_words = ['manager', 'supervisor', 'coordinator', 'director', 'lead']
            office_job_words = ['assistant', 'secretary', 'clerk', 'administrative', 'reception']
            
            engineering_score = sum(1 for word in engineering_job_words if word in job_text)
            management_score = sum(1 for word in management_job_words if word in job_text)
            office_score = sum(1 for word in office_job_words if word in job_text)
            
            if engineering_score > 0:
                return min(0.85, 0.6 + (engineering_score * 0.05))  # 60-85% for engineering
            elif management_score > 0:
                return min(0.75, 0.5 + (management_score * 0.05))   # 50-75% for management
            elif office_score > 0:
                return 0.2  # 20% for office jobs (low but not filtered)
            else:
                return 0.4  # 40% for other jobs
        
        # Original algorithm for properly extracted CVs
        engineering_keywords = [
            'engineer', 'engineering', 'technical', 'design', 'analysis', 'project',
            'mechanical', 'electrical', 'chemical', 'petroleum', 'drilling', 'production',
            'reservoir', 'pipeline', 'refinery', 'offshore', 'onshore', 'process',
            'matlab', 'autocad', 'solidworks', 'python', 'simulation', 'modeling',
            'troubleshooting', 'optimization', 'safety', 'hse', 'commissioning'
        ]
        
        management_keywords = [
            'manager', 'management', 'lead', 'supervisor', 'director', 'coordinator',
            'team', 'leadership', 'planning', 'budget', 'strategy', 'operations'
        ]
        
        office_keywords = [
            'administrative', 'office', 'clerical', 'secretary', 'assistant', 'clerk',
            'data entry', 'filing', 'reception', 'customer service', 'sales'
        ]
        
        # Count keyword matches
        engineering_matches = sum(1 for keyword in engineering_keywords if keyword in cv_content and keyword in job_text)
        management_matches = sum(1 for keyword in management_keywords if keyword in cv_content and keyword in job_text)
        office_matches = sum(1 for keyword in office_keywords if keyword in job_text)
        
        # Penalize office jobs for engineering CVs
        if any(keyword in cv_content for keyword in engineering_keywords):
            if office_matches > 2 and engineering_matches < 2:
                return max(0.1, 0.3 - (office_matches * 0.1))  # Low score for office jobs
        
        # Calculate base score
        total_keywords = len(engineering_keywords) + len(management_keywords)
        match_score = (engineering_matches + management_matches) / total_keywords
        
        # Boost for engineering jobs when CV has engineering background
        if engineering_matches > 2 and any(eng_word in job_text for eng_word in engineering_keywords[:10]):
            match_score += 0.2
        
        # Boost for management roles if CV shows leadership experience  
        if management_matches > 1 and any(mgmt_word in cv_content for mgmt_word in management_keywords):
            match_score += 0.1
            
        return min(0.95, max(0.1, match_score))
    
    job_listings = task.job_listings
    matches_created = []
    
    for listing in job_listings[:5]:  # Match first 5 jobs
        score = calculate_job_match_score(listing.title, listing.description, cv_text)
        
        # Debug logging
        print(f"Job: {listing.title} | Score: {score:.3f}")
        print(f"  Company: {listing.company} | Location: {listing.location}")
        
        match = Match(
            task_id=task.id,
            listing_id=listing.id,
            score=score
        )
        db.add(match)
        matches_created.append((listing.title, score))
    
    print(f"CV keywords preview: {cv_text[:100]}...")
    
    db.commit()
    
    return {"message": "Matching completed"}

@router.get("/matches/{task_id}", response_model=List[MatchResponse])
def get_matches(
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    task = db.query(ScrapeTask).filter(
        ScrapeTask.id == task_id,
        ScrapeTask.user_id == current_user.id
    ).first()
    
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found"
        )
    
    # Return matches with score >= 0.3 (30%) to filter out low-quality matches
    matches = db.query(Match).filter(
        Match.task_id == task_id,
        Match.score >= 0.3
    ).order_by(Match.score.desc()).all()
    
    # Convert to response format with proper datetime serialization
    result = []
    for match in matches:
        result.append(MatchResponse(
            id=match.id,
            listing=JobListingResponse(
                id=match.listing.id,
                title=match.listing.title,
                company=match.listing.company,
                location=match.listing.location,
                url=match.listing.url,
                description=match.listing.description
            ),
            score=match.score,
            matched_at=match.matched_at.isoformat()
        ))
    
    return result

@router.post("/cv/tailor")
def tailor_cv_for_job(
    request: TailorCVRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    job = db.query(JobListing).filter(JobListing.id == request.job_id).first()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found"
        )
    
    # For demo, return a simple message
    return {"message": "CV tailoring feature coming soon! For now, please manually adjust your CV to highlight relevant experience for this position."}