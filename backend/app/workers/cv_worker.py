from celery import Celery
from sqlalchemy.orm import Session
from openai import OpenAI
from ..core.database import SessionLocal
from ..core.config import settings
from ..models.job_listing import JobListing
from ..models.cv import CV
from ..models.user import User
from .celery_app import celery_app

client = OpenAI(api_key=settings.OPENAI_API_KEY)

@celery_app.task
def tailor_cv(user_id: int, job_id: int):
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        job = db.query(JobListing).filter(JobListing.id == job_id).first()
        cv = db.query(CV).filter(CV.user_id == user_id).first()
        
        if not user or not job or not cv:
            return {"error": "User, job, or CV not found"}
        
        prompt = f"""
        You are an expert CV writer specializing in the oil & gas industry. 
        
        Please rewrite the candidate's CV to target this specific job opportunity:
        
        Job Title: {job.title}
        Company: {job.company}
        Location: {job.location}
        Job Description: {job.description}
        
        Original CV:
        {cv.text_content}
        
        Instructions:
        1. Tailor the CV to highlight relevant experience and skills for this specific position
        2. Use keywords from the job description naturally throughout the CV
        3. Emphasize achievements and experiences that align with the job requirements
        4. Maintain the original structure and format as much as possible
        5. Keep the same personal information and contact details
        6. Focus on oil & gas industry experience and technical skills
        7. Ensure the CV remains professional and ATS-friendly
        
        Please provide the tailored CV:
        """
        
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are an expert CV writer specializing in the oil & gas industry."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=2000,
            temperature=0.7
        )
        
        tailored_cv = response.choices[0].message.content
        
        return {
            "tailored_cv": tailored_cv,
            "job_title": job.title,
            "company": job.company
        }
        
    except Exception as e:
        return {"error": str(e)}
    finally:
        db.close()