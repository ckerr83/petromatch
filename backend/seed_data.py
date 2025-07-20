import json
from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.models.job_board import JobBoard

def seed_job_boards():
    """Seed the database with sample job boards"""
    db = SessionLocal()
    
    try:
        # Check if job boards already exist
        existing_boards = db.query(JobBoard).count()
        if existing_boards > 0:
            print("Job boards already exist. Skipping seed.")
            return
        
        # Load sample job boards
        with open('sample_job_boards.json', 'r') as f:
            boards_data = json.load(f)
        
        # Create job boards
        for board_data in boards_data:
            board = JobBoard(
                name=board_data['name'],
                login_required=board_data['login_required'],
                base_url=board_data['base_url'],
                selectors_json=board_data['selectors_json']
            )
            db.add(board)
        
        db.commit()
        print(f"Successfully seeded {len(boards_data)} job boards.")
        
    except Exception as e:
        print(f"Error seeding job boards: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    seed_job_boards()