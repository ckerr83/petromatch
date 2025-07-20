from fastapi import FastAPI, Depends, HTTPException, status
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
    
    # Create AI matches with random scores for demo
    jobs = db.query(JobListing).filter(JobListing.task_id == request.task_id).all()
    
    # Clear existing matches
    db.query(Match).filter(Match.task_id == request.task_id).delete()
    
    # Create new matches with scores
    for job in jobs:
        score = round(random.uniform(0.6, 0.95), 2)  # Demo scores between 60-95%
        match = Match(
            task_id=request.task_id,
            listing_id=job.id,
            score=score
        )
        db.add(match)
    
    db.commit()
    return {"message": "Matching completed", "matches_created": len(jobs)}

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