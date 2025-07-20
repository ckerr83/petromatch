from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, func, Table
from sqlalchemy.orm import relationship
from ..core.database import Base

scrape_task_boards = Table(
    'scrape_task_boards',
    Base.metadata,
    Column('scrape_task_id', Integer, ForeignKey('scrape_tasks.id'), primary_key=True),
    Column('board_id', Integer, ForeignKey('boards.id'), primary_key=True)
)

class ScrapeTask(Base):
    __tablename__ = "scrape_tasks"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    status = Column(String, default="pending")  # pending, running, completed, failed
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    user = relationship("User", back_populates="scrape_tasks")
    boards = relationship("JobBoard", secondary=scrape_task_boards, back_populates="scrape_tasks")
    job_listings = relationship("JobListing", back_populates="task")
    matches = relationship("Match", back_populates="task")