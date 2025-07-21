#!/usr/bin/env python3

import requests
from bs4 import BeautifulSoup
import json

def test_rigzone_scraping():
    """Test RigZone scraping to make sure it's still working"""
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    jobs = []
    
    # Test first 2 pages of RigZone
    for page in range(1, 3):
        try:
            url = f"https://www.rigzone.com/oil/jobs/search/?page={page}"
            print(f"Testing RigZone page {page}: {url}")
            
            response = requests.get(url, headers=headers, timeout=15)
            print(f"Status: {response.status_code}")
            
            if response.status_code != 200:
                print(f"Failed to fetch page {page}")
                continue
                
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Look for job articles
            job_articles = soup.find_all('article', class_='update-block')
            print(f"Found {len(job_articles)} job articles on page {page}")
            
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
                        locations = ['texas', 'houston', 'oklahoma', 'louisiana', 'california', 'north dakota', 'pennsylvania', 'canada', 'norway', 'uk', 'scotland', 'abu dhabi', 'saudi', 'qatar']
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
                    link_elem = article.find('a', href=True)
                    job_url = f"https://www.rigzone.com{link_elem['href']}" if link_elem else "URL not found"
                    
                    job = {
                        'title': title,
                        'company': company,
                        'location': location,
                        'description': description,
                        'url': job_url,
                        'board': 'RigZone'
                    }
                    
                    jobs.append(job)
                    print(f"  Job: {title} - {company} - {location}")
                    
                except Exception as e:
                    print(f"  Error parsing job: {e}")
                    continue
                    
        except Exception as e:
            print(f"Error scraping RigZone page {page}: {e}")
            continue
    
    print(f"\nTotal RigZone jobs found: {len(jobs)}")
    
    if jobs:
        print("\nSample job:")
        print(json.dumps(jobs[0], indent=2))
    
    return jobs

if __name__ == "__main__":
    print("Testing RigZone scraping...")
    rigzone_jobs = test_rigzone_scraping()
    print(f"Result: {'Working' if len(rigzone_jobs) > 0 else 'Not working'}")