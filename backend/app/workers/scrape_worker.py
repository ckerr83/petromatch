from celery import Celery
from sqlalchemy.orm import Session
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import requests
import json
import time
from ..core.database import SessionLocal
from ..models.scrape_task import ScrapeTask
from ..models.job_listing import JobListing
from ..models.job_board import JobBoard
from .celery_app import celery_app

@celery_app.task
def scrape_jobs(task_id: int):
    db = SessionLocal()
    try:
        task = db.query(ScrapeTask).filter(ScrapeTask.id == task_id).first()
        if not task:
            return {"error": "Task not found"}
        
        task.status = "running"
        db.commit()
        
        total_listings = 0
        
        for board in task.boards:
            try:
                selectors = json.loads(board.selectors_json)
                
                if selectors.get("use_playwright", False):
                    listings = scrape_with_playwright(board, selectors)
                else:
                    listings = scrape_with_requests(board, selectors)
                
                for listing_data in listings:
                    listing = JobListing(
                        task_id=task_id,
                        title=listing_data.get("title", ""),
                        company=listing_data.get("company", ""),
                        location=listing_data.get("location", ""),
                        url=listing_data.get("url", ""),
                        description=listing_data.get("description", "")
                    )
                    db.add(listing)
                    total_listings += 1
                
                db.commit()
                
            except Exception as e:
                print(f"Error scraping board {board.name}: {str(e)}")
                continue
        
        task.status = "completed"
        db.commit()
        
        return {"total_listings": total_listings}
        
    except Exception as e:
        task.status = "failed"
        db.commit()
        return {"error": str(e)}
    finally:
        db.close()

def scrape_with_playwright(board: JobBoard, selectors: dict):
    listings = []
    
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        
        try:
            page.goto(board.base_url)
            
            if board.login_required and selectors.get("login"):
                login_data = selectors["login"]
                page.fill(login_data["username_selector"], login_data["username"])
                page.fill(login_data["password_selector"], login_data["password"])
                page.click(login_data["submit_selector"])
                page.wait_for_timeout(3000)
            
            # Navigate to jobs page if different
            if selectors.get("jobs_page_url"):
                page.goto(selectors["jobs_page_url"])
            
            # Wait for job listings to load
            page.wait_for_selector(selectors["job_container"], timeout=10000)
            
            # Scrape job listings
            job_elements = page.query_selector_all(selectors["job_container"])
            
            for job_element in job_elements:
                try:
                    title = job_element.query_selector(selectors["title_selector"])
                    company = job_element.query_selector(selectors["company_selector"])
                    location = job_element.query_selector(selectors["location_selector"])
                    url_element = job_element.query_selector(selectors["url_selector"])
                    description = job_element.query_selector(selectors.get("description_selector", ""))
                    
                    listing = {
                        "title": title.inner_text() if title else "",
                        "company": company.inner_text() if company else "",
                        "location": location.inner_text() if location else "",
                        "url": url_element.get_attribute("href") if url_element else "",
                        "description": description.inner_text() if description else ""
                    }
                    
                    # Make URL absolute
                    if listing["url"] and not listing["url"].startswith("http"):
                        listing["url"] = f"{board.base_url.rstrip('/')}/{listing['url'].lstrip('/')}"
                    
                    listings.append(listing)
                    
                except Exception as e:
                    print(f"Error parsing job element: {str(e)}")
                    continue
            
        finally:
            browser.close()
    
    return listings

def scrape_with_requests(board: JobBoard, selectors: dict):
    listings = []
    
    session = requests.Session()
    
    try:
        # Login if required
        if board.login_required and selectors.get("login"):
            login_data = selectors["login"]
            login_payload = {
                login_data["username_field"]: login_data["username"],
                login_data["password_field"]: login_data["password"]
            }
            session.post(login_data["login_url"], data=login_payload)
        
        # Get jobs page
        jobs_url = selectors.get("jobs_page_url", board.base_url)
        response = session.get(jobs_url)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Find job containers
        job_containers = soup.select(selectors["job_container"])
        
        for container in job_containers:
            try:
                title_elem = container.select_one(selectors["title_selector"])
                company_elem = container.select_one(selectors["company_selector"])
                location_elem = container.select_one(selectors["location_selector"])
                url_elem = container.select_one(selectors["url_selector"])
                description_elem = container.select_one(selectors.get("description_selector", ""))
                
                listing = {
                    "title": title_elem.get_text(strip=True) if title_elem else "",
                    "company": company_elem.get_text(strip=True) if company_elem else "",
                    "location": location_elem.get_text(strip=True) if location_elem else "",
                    "url": url_elem.get("href") if url_elem else "",
                    "description": description_elem.get_text(strip=True) if description_elem else ""
                }
                
                # Make URL absolute
                if listing["url"] and not listing["url"].startswith("http"):
                    listing["url"] = f"{board.base_url.rstrip('/')}/{listing['url'].lstrip('/')}"
                
                listings.append(listing)
                
            except Exception as e:
                print(f"Error parsing job container: {str(e)}")
                continue
    
    except Exception as e:
        print(f"Error scraping with requests: {str(e)}")
    
    return listings