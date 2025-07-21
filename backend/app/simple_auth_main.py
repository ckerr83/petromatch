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
import requests
from bs4 import BeautifulSoup
import re

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

class LocationPreference(Base):
    __tablename__ = "location_preferences"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer)
    location = Column(String)  # Asia, Africa, Worldwide, Global, North Sea, UK, etc.
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

class LocationPreferenceRequest(BaseModel):
    locations: List[str]

class LocationPreferenceResponse(BaseModel):
    id: int
    location: str
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

@app.get("/debug/scrape-test")
def debug_scrape_test():
    """Debug endpoint to test RigZone scraping directly"""
    try:
        print("Starting debug scrape test...")
        jobs = scrape_rigzone_jobs(max_pages=10)  # Test with 10 pages (40 jobs)
        return {
            "status": "success", 
            "jobs_found": len(jobs),
            "sample_jobs": jobs[:3] if jobs else [],
            "message": f"Successfully scraped {len(jobs)} jobs from RigZone"
        }
    except Exception as e:
        print(f"Debug scrape test error: {e}")
        return {
            "status": "error",
            "error": str(e),
            "message": "Failed to scrape RigZone"
        }

@app.get("/debug/scrape-orion")
def debug_scrape_orion():
    """Debug endpoint to test Orion Jobs scraping directly"""
    try:
        print("Starting Orion Jobs debug scrape test...")
        jobs = scrape_orion_jobs(max_pages=5)  # Test with 5 pages
        return {
            "status": "success", 
            "jobs_found": len(jobs),
            "sample_jobs": jobs[:3] if jobs else [],
            "message": f"Successfully scraped {len(jobs)} jobs from Orion Jobs"
        }
    except Exception as e:
        print(f"Orion debug scrape test error: {e}")
        return {
            "status": "error",
            "error": str(e),
            "message": "Failed to scrape Orion Jobs"
        }

@app.get("/debug/orion-connectivity")
def debug_orion_connectivity():
    """Test basic connectivity to Orion Jobs"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        test_urls = [
            "https://www.orionjobs.com/job-search/?+Gas=",
            "https://www.orionjobs.com/job-search/?+Oil=", 
            "https://www.orionjobs.com/job-search/?+Oil=&+Gas=",
        ]
        
        results = []
        for url in test_urls:
            try:
                response = requests.get(url, headers=headers, timeout=10)
                results.append({
                    "url": url,
                    "status_code": response.status_code,
                    "content_length": len(response.content),
                    "has_job_content": "job" in response.text.lower(),
                    "title": response.text[:100] if response.text else "No content"
                })
            except Exception as e:
                results.append({
                    "url": url,
                    "error": str(e),
                    "status": "failed"
                })
        
        return {
            "status": "completed",
            "test_results": results
        }
        
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }

@app.get("/debug/orion-html-structure")
def debug_orion_html_structure():
    """Analyze HTML structure of Orion Jobs page"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        response = requests.get("https://www.orionjobs.com/job-search/?+Gas=", headers=headers, timeout=15)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Find all unique tag/class combinations
        elements_found = {}
        for element in soup.find_all():
            tag = element.name
            classes = element.get('class', [])
            class_str = ' '.join(classes) if classes else 'no-class'
            key = f"{tag}.{class_str}"
            
            if key not in elements_found:
                elements_found[key] = {
                    "count": 0,
                    "sample_text": ""
                }
            
            elements_found[key]["count"] += 1
            if not elements_found[key]["sample_text"] and element.get_text(strip=True):
                elements_found[key]["sample_text"] = element.get_text(strip=True)[:100]
        
        # Focus on potentially job-related elements
        job_related = {}
        for key, info in elements_found.items():
            if any(keyword in key.lower() for keyword in ['job', 'position', 'vacancy', 'listing', 'result', 'card', 'item']):
                job_related[key] = info
        
        return {
            "status": "completed",
            "page_info": {
                "total_elements": len(elements_found),
                "has_jobs_text": "job" in response.text.lower(),
                "content_length": len(response.content)
            },
            "job_related_elements": job_related,
            "common_elements": dict(sorted(elements_found.items(), key=lambda x: x[1]["count"], reverse=True)[:20])
        }
        
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }

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
            JobBoard(name="Energy Jobline", login_required=False, base_url="https://www.energyjobline.com"),
            JobBoard(name="Orion Jobs", login_required=False, base_url="https://www.orionjobs.com")
        ]
        for board in boards:
            db.add(board)
        db.commit()

# Initialize database with sample data
with SessionLocal() as db:
    seed_job_boards(db)

def scrape_rigzone_jobs(max_pages: int = 100) -> List[dict]:
    """Scrape jobs from RigZone with pagination support"""
    jobs = []
    base_url = "https://www.rigzone.com/oil/jobs/search/"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    try:
        for page in range(1, max_pages + 1):
            print(f"Scraping RigZone page {page}...")
            
            # Construct URL with page parameter  
            url = f"{base_url}?page={page}"
            print(f"Fetching URL: {url}")
            
            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Find job listings using the structure we identified
            job_articles = soup.find_all('article', class_='update-block')
            
            print(f"Found {len(job_articles)} job articles on page {page}")
            
            if not job_articles:
                print(f"No job articles found on page {page}, stopping pagination")
                break
                
            for article in job_articles:
                try:
                    # Extract job title and URL
                    heading = article.find('div', class_='heading')
                    if not heading:
                        continue
                        
                    title_link = heading.find('h3').find('a') if heading.find('h3') else None
                    if not title_link:
                        continue
                        
                    title = title_link.get_text(strip=True)
                    job_url = title_link.get('href', '')
                    
                    # Make URL absolute if relative
                    if job_url.startswith('/'):
                        job_url = f"https://www.rigzone.com{job_url}"
                    
                    # Extract company and location from address
                    address = heading.find('address')
                    if not address:
                        continue
                        
                    address_text = address.get_text(strip=True)
                    # Try to split company and location
                    address_parts = [part.strip() for part in address_text.split('\n') if part.strip()]
                    
                    if address_parts:
                        # Often RigZone combines company and location in one line
                        full_text = address_parts[0]
                        
                        # Try to extract location from the end of the company text
                        # Look for patterns like "CompanyNameCity, State, Country"
                        location_match = re.search(r'([A-Za-z\s]+),\s*([A-Z]{2}),\s*([A-Za-z\s]+)$', full_text)
                        if location_match:
                            city, state, country = location_match.groups()
                            location = f"{city.strip()}, {state.strip()}, {country.strip()}"
                            company = full_text.replace(location_match.group(0), '').strip()
                        else:
                            # Try simpler pattern "CompanyCity, Country"
                            location_match = re.search(r'([A-Za-z\s]+),\s*([A-Za-z\s]+)$', full_text)
                            if location_match and len(location_match.group(2).strip()) > 2:
                                city, country = location_match.groups()
                                location = f"{city.strip()}, {country.strip()}"
                                company = full_text.replace(location_match.group(0), '').strip()
                            else:
                                company = full_text
                                location = "Location not specified"
                    else:
                        company = "Unknown Company"
                        location = "Location not specified"
                    
                    # Extract job details from footer
                    footer = article.find('footer', class_='details')
                    experience = ""
                    skills = ""
                    
                    if footer:
                        exp_span = footer.find('span', class_='experience')
                        if exp_span:
                            experience = exp_span.get_text(strip=True)
                            
                        resp_span = footer.find('span', class_='responsibility')
                        if resp_span:
                            skills = resp_span.get_text(strip=True)
                    
                    # Build description
                    description_parts = []
                    if experience:
                        description_parts.append(f"Experience: {experience}")
                    if skills:
                        description_parts.append(f"Skills: {skills}")
                    
                    description = " | ".join(description_parts) if description_parts else "Job details available on RigZone."
                    
                    # Only add jobs with valid titles and URLs
                    if title and job_url:
                        jobs.append({
                            'title': title,
                            'company': company,
                            'location': location,
                            'url': job_url,
                            'description': description
                        })
                        
                except Exception as e:
                    print(f"Error parsing job article: {e}")
                    continue
            
            print(f"Found {len(job_articles)} job articles on page {page}")
            
            # Only add delay if we're getting good results
            if len(job_articles) > 0:
                time.sleep(2)  # Be more respectful with longer delay
            
    except Exception as e:
        print(f"Error scraping RigZone: {e}")
    
    print(f"Total jobs scraped from RigZone: {len(jobs)}")
    return jobs

def scrape_orion_jobs(max_pages: int = 20) -> List[dict]:
    """Scrape jobs from Orion Jobs with pagination support"""
    jobs = []
    # Use the correct search URL for Oil & Gas jobs
    base_url = "https://www.orionjobs.com/job-search/?+Gas="
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    try:
        for page in range(1, max_pages + 1):
            print(f"Scraping Orion Jobs page {page}...")
            
            # Try different URL patterns for Orion Jobs Oil & Gas search
            urls_to_try = [
                "https://www.orionjobs.com/job-search/?+Gas=",  # Main gas search
                "https://www.orionjobs.com/job-search/?+Oil=",  # Oil search  
                "https://www.orionjobs.com/job-search/?+Oil=&+Gas=",  # Both oil and gas
                f"https://www.orionjobs.com/job-search/?+Gas=&page={page}",  # With pagination
                f"https://www.orionjobs.com/job-search/?+Oil=&page={page}"   # Oil with pagination
            ]
            
            page_jobs_found = False
            
            for url in urls_to_try:
                try:
                    print(f"Trying URL: {url}")
                    response = requests.get(url, headers=headers, timeout=15)
                    response.raise_for_status()
                    
                    soup = BeautifulSoup(response.content, 'html.parser')
                    
                    # Try extensive job listing selectors
                    job_selectors = [
                        'div.job-item',
                        'div.job-listing', 
                        'article.job',
                        'div.job-card',
                        'li.job',
                        '.job-result',
                        '.job-post',
                        'div[class*="job"]',
                        'li[class*="job"]',
                        'article[class*="job"]',
                        '.search-result',
                        '.result-item',
                        'tr.job',
                        'div.vacancy',
                        'div.position'
                    ]
                    
                    job_articles = []
                    for selector in job_selectors:
                        found_jobs = soup.select(selector)
                        if found_jobs:
                            job_articles = found_jobs
                            print(f"Found {len(job_articles)} jobs using selector: {selector}")
                            break
                    
                    # If no specific job selectors work, try finding links that might be job links
                    if not job_articles:
                        print("Trying to find job links...")
                        potential_job_links = soup.find_all('a', href=True)
                        job_links = [link for link in potential_job_links 
                                   if any(keyword in link.get('href', '').lower() 
                                         for keyword in ['job', 'vacancy', 'position', 'career'])]
                        
                        if job_links:
                            print(f"Found {len(job_links)} potential job links")
                            # Create mock job articles from links
                            job_articles = job_links[:20]  # Limit to 20 per page
                    
                    if job_articles:
                        page_jobs_found = True
                        
                        for article in job_articles:
                            try:
                                # Check if this is a direct link or a job container
                                if article.name == 'a':
                                    # This is a direct job link
                                    title = article.get_text(strip=True)
                                    job_url = article.get('href', '')
                                    company = "Company via Orion Jobs"
                                    location = "Location not specified"
                                    description = "Job details available on Orion Jobs"
                                else:
                                    # This is a job container, extract details
                                    # Extract job title
                                    title_selectors = ['h2 a', 'h3 a', '.job-title a', '.title a', 'a.job-link', 'h2', 'h3', '.job-title', '.title']
                                    title = ""
                                    job_url = ""
                                    
                                    for title_sel in title_selectors:
                                        title_elem = article.select_one(title_sel)
                                        if title_elem:
                                            title = title_elem.get_text(strip=True)
                                            if title_elem.name == 'a':
                                                job_url = title_elem.get('href', '')
                                            break
                                    
                                    # Extract company
                                    company_selectors = ['.company', '.employer', '.company-name', '.job-company']
                                    company = ""
                                    for comp_sel in company_selectors:
                                        comp_elem = article.select_one(comp_sel)
                                        if comp_elem:
                                            company = comp_elem.get_text(strip=True)
                                            break
                                    
                                    # Extract location
                                    location_selectors = ['.location', '.job-location', '.place', '.job-place']
                                    location = ""
                                    for loc_sel in location_selectors:
                                        loc_elem = article.select_one(loc_sel)
                                        if loc_elem:
                                            location = loc_elem.get_text(strip=True)
                                            break
                                    
                                    # Extract date posted
                                    date_selectors = ['.date', '.posted-date', '.job-date', '.posted', 'time']
                                    date_posted = ""
                                    for date_sel in date_selectors:
                                        date_elem = article.select_one(date_sel)
                                        if date_elem:
                                            date_posted = date_elem.get_text(strip=True)
                                            break
                                    
                                    # Extract description
                                    desc_selectors = ['.description', '.job-description', '.summary', '.excerpt']
                                    description = ""
                                    for desc_sel in desc_selectors:
                                        desc_elem = article.select_one(desc_sel)
                                        if desc_elem:
                                            description = desc_elem.get_text(strip=True)
                                            break
                                    
                                    # Build description with available info
                                    desc_parts = []
                                    if date_posted:
                                        desc_parts.append(f"Posted: {date_posted}")
                                    if description:
                                        desc_parts.append(description)
                                    
                                    description = " | ".join(desc_parts) if desc_parts else "Job details available on Orion Jobs."
                                    
                                    # Set defaults if not found
                                    if not company:
                                        company = "Company via Orion Jobs"
                                    if not location:
                                        location = "Location not specified"
                                
                                # Make URL absolute
                                if job_url and job_url.startswith('/'):
                                    job_url = f"https://www.orionjobs.com{job_url}"
                                elif not job_url:
                                    job_url = f"https://www.orionjobs.com/job-search/"
                                
                                # Only add jobs with valid titles
                                if title and len(title) > 3:  # Basic validation
                                    jobs.append({
                                        'title': title,
                                        'company': company,
                                        'location': location, 
                                        'url': job_url,
                                        'description': description
                                    })
                                    
                            except Exception as e:
                                print(f"Error parsing Orion job article: {e}")
                                continue
                        
                        break  # Found jobs with this URL, no need to try others
                        
                except Exception as e:
                    print(f"Error with URL {url}: {e}")
                    continue
            
            if not page_jobs_found:
                print(f"No jobs found on page {page}, stopping pagination")
                break
                
            print(f"Found {len([j for j in jobs if 'page_{page}' not in str(j)])} jobs on page {page}")
            
            # Add respectful delay
            time.sleep(2)
            
    except Exception as e:
        print(f"Error scraping Orion Jobs: {e}")
    
    # If no jobs found via traditional scraping, try alternative approaches
    if len(jobs) == 0:
        print("No jobs found via CSS selectors. Trying alternative approaches...")
        
        # Try to find any text that looks like job titles in the page content
        try:
            response = requests.get("https://www.orionjobs.com/job-search/?+Gas=", headers=headers, timeout=15)
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Look for any text containing job-related keywords
            all_text = soup.get_text()
            
            # Search for patterns that might be job titles
            job_keywords = ['engineer', 'manager', 'analyst', 'technician', 'specialist', 'supervisor', 'director']
            oil_gas_keywords = ['oil', 'gas', 'petroleum', 'drilling', 'offshore', 'pipeline', 'refinery']
            
            # Find sentences that contain both job and industry keywords
            sentences = all_text.split('.')
            potential_jobs = []
            
            for sentence in sentences[:100]:  # Check first 100 sentences
                sentence = sentence.strip()
                if (any(keyword in sentence.lower() for keyword in job_keywords) and 
                    any(keyword in sentence.lower() for keyword in oil_gas_keywords) and
                    len(sentence) < 200 and len(sentence) > 10):
                    potential_jobs.append(sentence)
            
            print(f"Found {len(potential_jobs)} potential job-related text snippets")
            
            # If we found potential job content but couldn't parse it properly,
            # it suggests the site structure is different than expected
            if len(potential_jobs) > 0:
                print("Found job-related content but couldn't parse job listings structure")
                print("Orion Jobs may use dynamic loading or a different page structure")
            
        except Exception as e:
            print(f"Alternative scraping approach failed: {e}")
        
        print("Orion Jobs scraping unsuccessful - site may use JavaScript loading or anti-bot protection")
    
    print(f"Total jobs scraped from Orion Jobs: {len(jobs)}")
    return jobs

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
    task = ScrapeTask(status="running", user_id=current_user.id)
    db.add(task)
    db.commit()
    db.refresh(task)
    
    try:
        jobs_created = 0
        
        # Check which boards to scrape
        for board_id in request.board_ids:
            board = db.query(JobBoard).filter(JobBoard.id == board_id).first()
            if not board:
                continue
                
            print(f"Scraping jobs from {board.name}...")
            
            if board.name == "RigZone":
                # Scrape real RigZone jobs
                print(f"Starting RigZone scraping for task {task.task_id}...")
                rigzone_jobs = scrape_rigzone_jobs(max_pages=25)  # Scrape 25 pages (~100 jobs) from RigZone
                print(f"RigZone scraping completed. Found {len(rigzone_jobs)} jobs")
                
                for job_data in rigzone_jobs:
                    try:
                        job = JobListing(
                            task_id=task.task_id,
                            title=job_data['title'],
                            company=job_data['company'],
                            location=job_data['location'],
                            url=job_data['url'],
                            description=job_data['description']
                        )
                        db.add(job)
                        jobs_created += 1
                    except Exception as e:
                        print(f"Error creating job listing: {e}")
                        continue
                        
            elif board.name == "Orion Jobs":
                # Scrape real Orion Jobs
                print(f"Starting Orion Jobs scraping for task {task.task_id}...")
                orion_jobs = scrape_orion_jobs(max_pages=5)  # Try fewer pages first
                print(f"Orion Jobs scraping completed. Found {len(orion_jobs)} jobs")
                
                if len(orion_jobs) == 0:
                    print("WARNING: Orion Jobs scraping found 0 jobs - may need manual investigation")
                    print("Possible causes: dynamic loading, anti-bot protection, or changed site structure")
                else:
                    for job_data in orion_jobs:
                        try:
                            job = JobListing(
                                task_id=task.task_id,
                                title=job_data['title'],
                                company=job_data['company'],
                                location=job_data['location'],
                                url=job_data['url'],
                                description=job_data['description']
                            )
                            db.add(job)
                            jobs_created += 1
                        except Exception as e:
                            print(f"Error creating Orion job listing: {e}")
                            continue
            else:
                # For other boards, create some sample jobs for now
                sample_jobs_data = [
                    {
                        'title': f"Senior Petroleum Engineer - {board.name}",
                        'company': "Major Oil Company",
                        'location': "Houston, TX",
                        'url': f"{board.base_url}/job123",
                        'description': f"Engineering position from {board.name}. Experience with petroleum engineering and project management required."
                    },
                    {
                        'title': f"Drilling Engineer - {board.name}",
                        'company': "International Energy Corp",
                        'location': "Calgary, AB",
                        'url': f"{board.base_url}/job456",
                        'description': f"Drilling engineering role from {board.name}. Offshore drilling experience preferred."
                    }
                ]
                
                for job_data in sample_jobs_data:
                    job = JobListing(
                        task_id=task.task_id,
                        title=job_data['title'],
                        company=job_data['company'],
                        location=job_data['location'],
                        url=job_data['url'],
                        description=job_data['description']
                    )
                    db.add(job)
                    jobs_created += 1
        
        # Mark task as completed
        task.status = "completed"
        db.commit()
        
        print(f"Scraping completed. Created {jobs_created} jobs for task {task.task_id}")
        
    except Exception as e:
        print(f"Error during scraping: {e}")
        task.status = "failed"
        db.commit()
    
    return ScrapeTaskResponse(task_id=task.task_id, status=task.status)

@app.get("/jobs/status/{task_id}")
def get_scrape_status(task_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    task = db.query(ScrapeTask).filter(ScrapeTask.task_id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Since we create jobs immediately now, task should already be completed
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
    
    # Get user's location preferences
    location_preferences = db.query(LocationPreference).filter(LocationPreference.user_id == current_user.id).all()
    preferred_locations = [pref.location.lower() for pref in location_preferences]
    
    # Get jobs for this task
    jobs = db.query(JobListing).filter(JobListing.task_id == request.task_id).all()
    if not jobs:
        raise HTTPException(status_code=404, detail="No jobs found for this task")
    
    # Clear existing matches
    db.query(Match).filter(Match.task_id == request.task_id).delete()
    
    # Analyze CV content and match with jobs
    cv_content = user_cv.content.lower()
    
    # Create intelligent matches based on CV analysis and location preferences
    matches_to_create = []
    for job in jobs:
        score = calculate_match_score(cv_content, job, preferred_locations)
        matches_to_create.append((job, score))
    
    # Sort by score (highest first) and take top 10
    matches_to_create.sort(key=lambda x: x[1], reverse=True)
    top_matches = matches_to_create[:10]
    
    # Create matches for top 10 (with minimum 30% threshold)
    for job, score in top_matches:
        if score >= 0.3:  # Lower threshold to ensure we get more matches
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

def calculate_match_score(cv_content: str, job: JobListing, preferred_locations: List[str] = None) -> float:
    """Calculate job match score based on CV content, job requirements, and location preferences"""
    job_text = f"{job.title} {job.description} {job.company}".lower()
    job_location = job.location.lower()
    
    # Define skill keywords and their weights
    technical_skills = {
        "petroleum": 0.12, "drilling": 0.12, "reservoir": 0.12, "geophysics": 0.12,
        "pipeline": 0.12, "offshore": 0.10, "refinery": 0.10, "oil": 0.08, "gas": 0.08,
        "engineering": 0.06, "process": 0.08, "safety": 0.04, "hse": 0.04,
        "python": 0.06, "matlab": 0.06, "autocad": 0.04, "solidworks": 0.04,
        "project management": 0.06, "leadership": 0.04, "analysis": 0.04,
        "production": 0.08, "completion": 0.08, "subsea": 0.10, "petrophysics": 0.10,
        "facilities": 0.06, "simulation": 0.06, "optimization": 0.04, "operations": 0.06
    }
    
    experience_levels = {
        "senior": 0.10, "lead": 0.10, "principal": 0.12, "manager": 0.15,
        "director": 0.18, "engineer": 0.05, "analyst": 0.03, "graduate": 0.02
    }
    
    locations = {
        "houston": 0.05, "calgary": 0.05, "london": 0.03, "dubai": 0.03,
        "norway": 0.04, "uk": 0.03, "texas": 0.05, "alberta": 0.05
    }
    
    # Calculate base score (lower base to create more variety)
    score = 0.3  # Base compatibility
    
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
    
    # Apply location preference matching bonus
    if preferred_locations:
        location_match_bonus = 0.0
        for preferred_location in preferred_locations:
            # Check for exact matches and partial matches
            if preferred_location in job_location:
                location_match_bonus += 0.15
            elif preferred_location == "worldwide" or preferred_location == "global":
                # Global/worldwide preference matches any location
                location_match_bonus += 0.05
            elif preferred_location == "asia" and any(country in job_location for country in ["malaysia", "singapore", "china", "japan", "korea", "thailand", "indonesia", "dubai", "uae"]):
                location_match_bonus += 0.15
            elif preferred_location == "africa" and any(country in job_location for country in ["nigeria", "angola", "egypt", "ghana", "libya", "south africa"]):
                location_match_bonus += 0.15
            elif preferred_location == "europe" and any(country in job_location for country in ["uk", "norway", "netherlands", "london", "aberdeen", "north sea", "stavanger"]):
                location_match_bonus += 0.15
            elif preferred_location == "north america" and any(country in job_location for country in ["usa", "canada", "houston", "calgary", "texas", "alberta", "denver"]):
                location_match_bonus += 0.15
            elif preferred_location == "south america" and any(country in job_location for country in ["brazil", "venezuela", "colombia", "argentina", "chile"]):
                location_match_bonus += 0.15
            elif preferred_location == "australia" and any(country in job_location for country in ["australia", "perth", "melbourne", "sydney"]):
                location_match_bonus += 0.15
        
        # Cap location bonus at 0.20
        score += min(0.20, location_match_bonus)
    
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
    
    # Cap the score at 0.95 and ensure minimum of 0.3
    return min(0.95, max(0.3, round(score, 2)))

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

# Location Preferences API Endpoints
@app.post("/user/location-preferences", response_model=List[LocationPreferenceResponse])
def set_location_preferences(request: LocationPreferenceRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # Delete existing location preferences for this user
    db.query(LocationPreference).filter(LocationPreference.user_id == current_user.id).delete()
    
    # Create new location preferences
    preferences = []
    for location in request.locations:
        preference = LocationPreference(
            user_id=current_user.id,
            location=location
        )
        db.add(preference)
        preferences.append(preference)
    
    db.commit()
    
    # Refresh to get IDs and timestamps
    for pref in preferences:
        db.refresh(pref)
    
    return [LocationPreferenceResponse(
        id=pref.id,
        location=pref.location,
        created_at=pref.created_at.isoformat()
    ) for pref in preferences]

@app.get("/user/location-preferences", response_model=List[LocationPreferenceResponse])
def get_location_preferences(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    preferences = db.query(LocationPreference).filter(LocationPreference.user_id == current_user.id).all()
    
    return [LocationPreferenceResponse(
        id=pref.id,
        location=pref.location,
        created_at=pref.created_at.isoformat()
    ) for pref in preferences]