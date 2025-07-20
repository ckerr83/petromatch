from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship
from ..core.database import Base

class JobListing(Base):
    __tablename__ = "job_listings"
    
    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("scrape_tasks.id"), nullable=False)
    title = Column(String, nullable=False)
    company = Column(String, nullable=False)
    location = Column(String, nullable=False)
    url = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    created_at = Column(DateTime, default=func.now())
    
    task = relationship("ScrapeTask", back_populates="job_listings")
    matches = relationship("Match", back_populates="listing")