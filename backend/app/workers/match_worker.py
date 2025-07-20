from celery import Celery
from sqlalchemy.orm import Session
import numpy as np
import faiss
from openai import OpenAI
from ..core.database import SessionLocal
from ..core.config import settings
from ..models.scrape_task import ScrapeTask
from ..models.job_listing import JobListing
from ..models.match import Match
from ..models.cv import CV
from ..models.user import User
from .celery_app import celery_app

client = OpenAI(api_key=settings.OPENAI_API_KEY)

@celery_app.task
def match_jobs(task_id: int, user_id: int):
    db = SessionLocal()
    try:
        task = db.query(ScrapeTask).filter(ScrapeTask.id == task_id).first()
        user = db.query(User).filter(User.id == user_id).first()
        
        if not task or not user:
            return {"error": "Task or user not found"}
        
        # Get user's CV
        cv = db.query(CV).filter(CV.user_id == user_id).first()
        if not cv:
            return {"error": "CV not found"}
        
        # Get job listings
        job_listings = db.query(JobListing).filter(JobListing.task_id == task_id).all()
        if not job_listings:
            return {"error": "No job listings found"}
        
        # Create embeddings for CV
        cv_embedding = create_embedding(cv.text_content)
        
        # Create embeddings for job listings
        job_embeddings = []
        job_texts = []
        
        for job in job_listings:
            job_text = f"{job.title} {job.company} {job.location} {job.description}"
            job_texts.append(job_text)
            job_embedding = create_embedding(job_text)
            job_embeddings.append(job_embedding)
        
        # Convert to numpy arrays
        cv_embedding = np.array(cv_embedding).astype('float32')
        job_embeddings = np.array(job_embeddings).astype('float32')
        
        # Normalize embeddings
        cv_embedding = cv_embedding / np.linalg.norm(cv_embedding)
        job_embeddings = job_embeddings / np.linalg.norm(job_embeddings, axis=1, keepdims=True)
        
        # Create FAISS index
        dimension = job_embeddings.shape[1]
        index = faiss.IndexFlatIP(dimension)  # Inner product for cosine similarity
        index.add(job_embeddings)
        
        # Search for similar jobs
        k = min(10, len(job_listings))  # Top 10 or all jobs if less than 10
        cv_embedding = cv_embedding.reshape(1, -1)
        scores, indices = index.search(cv_embedding, k)
        
        # Store matches
        for i, (score, idx) in enumerate(zip(scores[0], indices[0])):
            if score > 0.7:  # Threshold for good matches
                match = Match(
                    task_id=task_id,
                    listing_id=job_listings[idx].id,
                    score=float(score)
                )
                db.add(match)
        
        db.commit()
        
        return {"matches_found": len(scores[0])}
        
    except Exception as e:
        return {"error": str(e)}
    finally:
        db.close()

def create_embedding(text: str) -> list:
    try:
        response = client.embeddings.create(
            model="text-embedding-ada-002",
            input=text
        )
        return response.data[0].embedding
    except Exception as e:
        print(f"Error creating embedding: {str(e)}")
        return [0.0] * 1536  # Default embedding size for ada-002