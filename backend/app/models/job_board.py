from sqlalchemy import Column, Integer, String, Boolean, Text, DateTime, func
from sqlalchemy.orm import relationship
from ..core.database import Base

class JobBoard(Base):
    __tablename__ = "boards"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    login_required = Column(Boolean, default=False)
    base_url = Column(String, nullable=False)
    selectors_json = Column(Text, nullable=False)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    scrape_tasks = relationship("ScrapeTask", secondary="scrape_task_boards", back_populates="boards")