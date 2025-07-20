from sqlalchemy import Column, Integer, Float, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship
from ..core.database import Base

class Match(Base):
    __tablename__ = "matches"
    
    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("scrape_tasks.id"), nullable=False)
    listing_id = Column(Integer, ForeignKey("job_listings.id"), nullable=False)
    score = Column(Float, nullable=False)
    matched_at = Column(DateTime, default=func.now())
    
    task = relationship("ScrapeTask", back_populates="matches")
    listing = relationship("JobListing", back_populates="matches")