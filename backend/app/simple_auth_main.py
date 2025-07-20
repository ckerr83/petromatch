from fastapi import FastAPI, Depends, HTTPException, status, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm, HTTPBearer
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from pydantic import BaseModel
from passlib.context import CryptContext
from jose import JWTError, jwt
from datetime import datetime, timedelta
from typing import List, Optional
import os
import time
import random

# Database setup
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./petromatch.db")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Database models
class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    password_hash = Column(String)

class JobBoard(Base):
    __tablename__ = "job_boards"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    login_required = Column(Integer, default=0)  # SQLite compatibility
    base_url = Column(String)

class ScrapeTask(Base):
    __tablename__ = "scrape_tasks"
    
    task_id = Column(Integer, primary_key=True, index=True)
    status = Column(String, default="pending")
    created_at = Column(DateTime, default=datetime.utcnow)
    user_id = Column(Integer)

class JobListing(Base):
    __tablename__ = "job_listings"
    
    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer)
    title = Column(String)
    company = Column(String)
    location = Column(String)
    url = Column(String)
    description = Column(Text)

class Match(Base):
    __tablename__ = "matches"
    
    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer)
    listing_id = Column(Integer)
    score = Column(Float)
    matched_at = Column(DateTime, default=datetime.utcnow)

class CV(Base):
    __tablename__ = "cvs"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer)
    filename = Column(String)
    content = Column(Text)  # Store file content as text
    created_at = Column(DateTime, default=datetime.utcnow)

# Create tables
Base.metadata.create_all(bind=engine)

# Security
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-here-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Pydantic models
class Token(BaseModel):
    access_token: str
    token_type: str

class JobBoardResponse(BaseModel):
    id: int
    name: str
    login_required: bool
    base_url: str

class ScrapeTaskResponse(BaseModel):
    task_id: int
    status: str

class JobListingResponse(BaseModel):
    id: int
    title: str
    company: str
    location: str
    url: str
    description: str

class MatchResponse(BaseModel):
    id: int
    listing: JobListingResponse
    score: float
    matched_at: str

class ScrapeRequest(BaseModel):
    board_ids: List[int]

class MatchRequest(BaseModel):
    task_id: int

class CVResponse(BaseModel):
    id: int
    filename: str
    created_at: str

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

# Authentication helper
bearer_scheme = HTTPBearer()

def get_current_user(token: str = Depends(bearer_scheme), db: Session = Depends(get_db)):
    try:
        payload = jwt.decode(token.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid token")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    user = db.query(User).filter(User.id == int(user_id)).first()
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")
    return user

# FastAPI app
app = FastAPI(title="PetroMatch API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000", 
        "https://petromatch-app.vercel.app",
        "https://*.vercel.app"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"message": "PetroMatch API with Authentication", "status": "ok"}

@app.get("/health")
def health_check():
    return {"status": "healthy"}

@app.post("/auth/login", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    # Check if user exists
    user = db.query(User).filter(User.email == form_data.username).first()
    if not user:
        # Auto-create demo user for testing
        hashed_password = get_password_hash(form_data.password)
        user = User(
            email=form_data.username,
            password_hash=hashed_password
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    else:
        # Verify password for existing user
        if not verify_password(form_data.password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": str(user.id)},
        expires_delta=access_token_expires
    )
    
    return {"access_token": access_token, "token_type": "bearer"}

# Seed job boards on startup
def seed_job_boards(db: Session):
    if db.query(JobBoard).count() == 0:
        boards = [
            JobBoard(name="RigZone", login_required=False, base_url="https://www.rigzone.com"),
            JobBoard(name="Oil & Gas Job Search", login_required=False, base_url="https://www.oilandgasjobsearch.com"),
            JobBoard(name="Energy Jobline", login_required=False, base_url="https://www.energyjobline.com")
        ]
        for board in boards:
            db.add(board)
        db.commit()

# Initialize database with sample data
with SessionLocal() as db:
    seed_job_boards(db)

# Job Board API Endpoints
@app.get("/jobs/boards", response_model=List[JobBoardResponse])
def get_job_boards(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    boards = db.query(JobBoard).all()
    return [JobBoardResponse(
        id=board.id,
        name=board.name,
        login_required=bool(board.login_required),
        base_url=board.base_url
    ) for board in boards]

@app.post("/jobs/scrape", response_model=ScrapeTaskResponse)
def start_job_scrape(request: ScrapeRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # Create a new scrape task
    task = ScrapeTask(status="pending", user_id=current_user.id)
    db.add(task)
    db.commit()
    db.refresh(task)
    
    # Simulate starting the scrape - in a real app this would trigger background processing
    # For demo, we'll create some sample job listings after a delay
    return ScrapeTaskResponse(task_id=task.task_id, status=task.status)

@app.get("/jobs/status/{task_id}")
def get_scrape_status(task_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    task = db.query(ScrapeTask).filter(ScrapeTask.task_id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Simulate task processing
    if task.status == "pending":
        # After 5 seconds, mark as running
        if (datetime.utcnow() - task.created_at).seconds > 5:
            task.status = "running"
            db.commit()
    elif task.status == "running":
        # After 15 seconds total, mark as completed and create sample jobs
        if (datetime.utcnow() - task.created_at).seconds > 15:
            task.status = "completed"
            
            # Create sample job listings if they don't exist
            if db.query(JobListing).filter(JobListing.task_id == task_id).count() == 0:
                sample_jobs = [
                    JobListing(
                        task_id=task_id,
                        title="Senior Petroleum Engineer",
                        company="ExxonMobil",
                        location="Houston, TX",
                        url="https://careers.exxonmobil.com/job123",
                        description="Lead reservoir engineering projects and optimize production strategies."
                    ),
                    JobListing(
                        task_id=task_id,
                        title="Drilling Engineer",
                        company="Shell",
                        location="Calgary, AB",
                        url="https://shell.com/careers/job456",
                        description="Design and supervise drilling operations for offshore projects."
                    ),
                    JobListing(
                        task_id=task_id,
                        title="Process Engineer",
                        company="Chevron",
                        location="Midland, TX",
                        url="https://chevron.com/jobs/789",
                        description="Optimize refinery processes and ensure safety compliance."
                    ),
                    JobListing(
                        task_id=task_id,
                        title="Geophysicist",
                        company="BP",
                        location="London, UK",
                        url="https://bp.com/careers/geo001",
                        description="Analyze seismic data to identify new oil and gas reserves."
                    ),
                    JobListing(
                        task_id=task_id,
                        title="Pipeline Engineer",
                        company="Kinder Morgan",
                        location="Denver, CO",
                        url="https://kindermorgan.com/job999",
                        description="Design and maintain pipeline infrastructure systems."
                    )
                ]
                for job in sample_jobs:
                    db.add(job)
            db.commit()
    
    return {"task_id": task.task_id, "status": task.status, "created_at": task.created_at.isoformat()}

@app.get("/jobs/results/{task_id}", response_model=List[JobListingResponse])
def get_job_results(task_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    task = db.query(ScrapeTask).filter(ScrapeTask.task_id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    jobs = db.query(JobListing).filter(JobListing.task_id == task_id).all()
    return [JobListingResponse(
        id=job.id,
        title=job.title,
        company=job.company,
        location=job.location,
        url=job.url,
        description=job.description
    ) for job in jobs]

@app.post("/jobs/match")
def start_job_matching(request: MatchRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    task = db.query(ScrapeTask).filter(ScrapeTask.task_id == request.task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Get user's CV for analysis
    user_cv = db.query(CV).filter(CV.user_id == current_user.id).first()
    if not user_cv:
        raise HTTPException(status_code=400, detail="Please upload your CV first to enable job matching")
    
    # Get jobs for this task
    jobs = db.query(JobListing).filter(JobListing.task_id == request.task_id).all()
    if not jobs:
        raise HTTPException(status_code=404, detail="No jobs found for this task")
    
    # Clear existing matches
    db.query(Match).filter(Match.task_id == request.task_id).delete()
    
    # Analyze CV content and match with jobs
    cv_content = user_cv.content.lower()
    
    # Create intelligent matches based on CV analysis
    for job in jobs:
        score = calculate_match_score(cv_content, job)
        
        # Only create matches with score > 0.5 (50%)
        if score > 0.5:
            match = Match(
                task_id=request.task_id,
                listing_id=job.id,
                score=score
            )
            db.add(match)
    
    db.commit()
    
    # Count created matches
    match_count = db.query(Match).filter(Match.task_id == request.task_id).count()
    return {"message": "Matching completed", "matches_created": match_count}

def calculate_match_score(cv_content: str, job: JobListing) -> float:
    """Calculate job match score based on CV content and job requirements"""
    job_text = f"{job.title} {job.description} {job.company}".lower()
    
    # Define skill keywords and their weights
    technical_skills = {
        "petroleum": 0.15, "drilling": 0.15, "reservoir": 0.15, "geophysics": 0.15,
        "pipeline": 0.15, "offshore": 0.12, "refinery": 0.12, "oil": 0.10, "gas": 0.10,
        "engineering": 0.08, "process": 0.08, "safety": 0.05, "hse": 0.05,
        "python": 0.08, "matlab": 0.08, "autocad": 0.06, "solidworks": 0.06,
        "project management": 0.08, "leadership": 0.05, "analysis": 0.05
    }
    
    experience_levels = {
        "senior": 0.10, "lead": 0.10, "principal": 0.12, "manager": 0.15,
        "director": 0.18, "engineer": 0.05, "analyst": 0.03, "graduate": 0.02
    }
    
    locations = {
        "houston": 0.05, "calgary": 0.05, "london": 0.03, "dubai": 0.03,
        "norway": 0.04, "uk": 0.03, "texas": 0.05, "alberta": 0.05
    }
    
    # Calculate base score
    score = 0.5  # Base compatibility
    
    # Check technical skills match
    for skill, weight in technical_skills.items():
        if skill in cv_content and skill in job_text:
            score += weight
    
    # Check experience level match
    for level, weight in experience_levels.items():
        if level in cv_content and level in job_text:
            score += weight
    
    # Check location preference (if mentioned in CV)
    for location, weight in locations.items():
        if location in cv_content and location in job_text:
            score += weight
    
    # Job title specific bonuses
    job_title = job.title.lower()
    if "petroleum" in cv_content and "petroleum" in job_title:
        score += 0.1
    if "drilling" in cv_content and "drilling" in job_title:
        score += 0.1
    if "process" in cv_content and "process" in job_title:
        score += 0.1
    if "pipeline" in cv_content and "pipeline" in job_title:
        score += 0.1
    if "geophysics" in cv_content and ("geophysics" in job_title or "geophysicist" in job_title):
        score += 0.1
    
    # Company match bonus
    company_names = ["exxonmobil", "shell", "chevron", "bp", "total", "conocophillips"]
    for company in company_names:
        if company in cv_content and company in job.company.lower():
            score += 0.05
    
    # Cap the score at 0.95 and ensure minimum
    return min(0.95, max(0.5, round(score, 2)))

@app.get("/jobs/matches/{task_id}", response_model=List[MatchResponse])
def get_job_matches(task_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # Join matches with job listings
    matches_query = db.query(Match, JobListing).join(
        JobListing, Match.listing_id == JobListing.id
    ).filter(Match.task_id == task_id).order_by(Match.score.desc()).all()
    
    results = []
    for match, job in matches_query:
        results.append(MatchResponse(
            id=match.id,
            listing=JobListingResponse(
                id=job.id,
                title=job.title,
                company=job.company,
                location=job.location,
                url=job.url,
                description=job.description
            ),
            score=match.score,
            matched_at=match.matched_at.isoformat()
        ))
    
    return results

# CV Upload API Endpoints
@app.post("/user/cv", response_model=CVResponse)
async def upload_cv(file: UploadFile = File(...), current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # Validate file type
    allowed_types = ['text/plain', 'application/pdf', 'application/msword', 
                    'application/vnd.openxmlformats-officedocument.wordprocessingml.document']
    
    if file.content_type not in allowed_types:
        raise HTTPException(status_code=400, detail="File type not supported. Please upload .txt, .pdf, .doc, or .docx files.")
    
    # Read file content
    content = await file.read()
    
    # For demo purposes, store as text (in production, you'd handle different file types properly)
    if file.content_type == 'text/plain':
        file_content = content.decode('utf-8')
    else:
        # For demo, just store filename for non-text files
        file_content = f"File content: {file.filename} ({file.content_type})"
    
    # Delete existing CV for this user
    db.query(CV).filter(CV.user_id == current_user.id).delete()
    
    # Create new CV record
    cv = CV(
        user_id=current_user.id,
        filename=file.filename,
        content=file_content
    )
    db.add(cv)
    db.commit()
    db.refresh(cv)
    
    return CVResponse(
        id=cv.id,
        filename=cv.filename,
        created_at=cv.created_at.isoformat()
    )

@app.get("/user/cv", response_model=CVResponse)
def get_user_cv(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    cv = db.query(CV).filter(CV.user_id == current_user.id).first()
    if not cv:
        raise HTTPException(status_code=404, detail="No CV found")
    
    return CVResponse(
        id=cv.id,
        filename=cv.filename,
        created_at=cv.created_at.isoformat()
    )