#!/usr/bin/env python3

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Mock the database parts to test just the scraping function
import requests
from bs4 import BeautifulSoup
import re
import time
from typing import List

def scrape_rigzone_jobs(max_pages: int = 2) -> List[dict]:
    """Test the updated RigZone scraping function"""
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
                    # Extract title
                    title_elem = article.find('h3')
                    title = title_elem.get_text(strip=True) if title_elem else "Title not found"
                    
                    # Extract company - try multiple selectors
                    company = "Company not specified"
                    company_selectors = ['p.company', '.company', 'div.company', 'span.company']
                    for sel in company_selectors:
                        company_elem = article.select_one(sel)
                        if company_elem and company_elem.get_text(strip=True):
                            company = company_elem.get_text(strip=True)
                            break
                    
                    # If no company element, look in all text for company patterns
                    if company == "Company not specified":
                        all_text = article.get_text()
                        # Look for company patterns (often after job title)
                        lines = [line.strip() for line in all_text.split('\n') if line.strip()]
                        if len(lines) > 1:
                            # Second line often contains company info
                            company = lines[1] if len(lines[1]) < 100 else "Oil & Gas Company"
                    
                    # Extract location - try multiple selectors
                    location = "Location not specified"
                    location_selectors = ['p.location', '.location', 'div.location', 'span.location']
                    for sel in location_selectors:
                        location_elem = article.select_one(sel)
                        if location_elem and location_elem.get_text(strip=True):
                            location = location_elem.get_text(strip=True)
                            break
                    
                    # If no location element, look for common location keywords
                    if location == "Location not specified":
                        all_text = article.get_text().lower()
                        locations = ['texas', 'houston', 'oklahoma', 'louisiana', 'california', 'north dakota', 'pennsylvania', 'canada', 'norway', 'uk', 'scotland', 'abu dhabi', 'saudi', 'qatar', 'uae', 'oman', 'kuwait', 'nigeria', 'angola', 'brazil', 'mexico', 'australia']
                        for loc in locations:
                            if loc in all_text:
                                location = loc.title()
                                break
                    
                    # Extract description - try multiple selectors
                    description = "Oil and gas industry position. Full details available on RigZone."
                    desc_selectors = ['p.description', '.description', 'div.description', '.summary', '.details']
                    for sel in desc_selectors:
                        desc_elem = article.select_one(sel)
                        if desc_elem and desc_elem.get_text(strip=True):
                            description = desc_elem.get_text(strip=True)
                            break
                    
                    # If no description, use article text (limited)
                    if description == "Oil and gas industry position. Full details available on RigZone.":
                        all_text = article.get_text()
                        lines = [line.strip() for line in all_text.split('\n') if line.strip() and len(line.strip()) > 20]
                        if len(lines) > 2:
                            description = " ".join(lines[2:4])  # Use 3rd and 4th lines
                        else:
                            description = f"Oil and gas position: {title}. Apply via RigZone for full details."
                    
                    # Extract URL
                    job_url = "https://www.rigzone.com/oil/jobs/search/"
                    link_elem = article.find('a', href=True)
                    if link_elem:
                        href = link_elem.get('href')
                        if href:
                            if href.startswith('http'):
                                job_url = href
                            else:
                                job_url = f"https://www.rigzone.com{href}"
                    
                    # Ensure description is not empty
                    if not description or len(description.strip()) < 10:
                        description = f"Oil and gas position: {title}. Apply via RigZone for full details."
                    
                    # Only add jobs with valid titles and URLs
                    if title and job_url:
                        jobs.append({
                            'title': title,
                            'company': company,
                            'location': location,
                            'url': job_url,
                            'description': description
                        })
                        
                        print(f"  Added: {title} - {company} - {location}")
                        
                except Exception as e:
                    print(f"Error parsing job article: {e}")
                    continue
            
            # Only add delay if we're getting good results
            if len(job_articles) > 0:
                time.sleep(1)  # Short delay for testing
            
    except Exception as e:
        print(f"Error scraping RigZone: {e}")
    
    print(f"Total RigZone jobs scraped: {len(jobs)}")
    return jobs

if __name__ == "__main__":
    print("Testing updated RigZone scraping function...")
    jobs = scrape_rigzone_jobs(max_pages=2)
    print(f"\nResult: Found {len(jobs)} jobs")
    
    if jobs:
        print("\nFirst job:")
        import json
        print(json.dumps(jobs[0], indent=2))