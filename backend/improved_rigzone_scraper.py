#!/usr/bin/env python3
"""
Improved RigZone Scraper
Based on HTML structure analysis, this scraper correctly extracts real job data
"""

import requests
from bs4 import BeautifulSoup
import json
import re
from urllib.parse import urljoin

def fetch_rigzone_jobs():
    """Fetch and parse RigZone jobs with correct structure understanding"""
    url = "https://www.rigzone.com/oil/jobs/search/?sk=nes"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate',
        'Connection': 'keep-alive',
        'Referer': 'https://www.rigzone.com/',
    }
    
    print(f"Fetching: {url}")
    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()
    
    soup = BeautifulSoup(response.content, 'html.parser')
    
    # Find job articles - this is the correct selector based on analysis
    job_articles = soup.find_all('article', class_='update-block')
    print(f"Found {len(job_articles)} job articles")
    
    jobs_data = []
    
    for i, article in enumerate(job_articles):
        try:
            # Extract job title from h3 > a
            title_element = article.find('h3')
            if not title_element:
                continue
                
            title_link = title_element.find('a')
            if not title_link:
                continue
            
            title = title_link.get_text(strip=True)
            job_url = urljoin('https://www.rigzone.com', title_link.get('href', ''))
            
            # Extract company and location from address element
            address_element = article.find('address')
            if not address_element:
                continue
            
            # Get all text content from address, split by <br> tags
            address_parts = []
            for content in address_element.contents:
                if hasattr(content, 'get_text'):
                    # It's an element, get its text
                    text = content.get_text(strip=True)
                    if text and text not in ['Featured Employer']:
                        address_parts.append(text)
                elif hasattr(content, 'strip'):
                    # It's a text node
                    text = content.strip()
                    if text and text not in ['Featured Employer']:
                        address_parts.append(text)
            
            # Clean up address parts and separate company from location
            clean_parts = [part for part in address_parts if part and part.strip()]
            
            if len(clean_parts) >= 2:
                company = clean_parts[0].strip()
                location = clean_parts[-1].strip()  # Last part is usually location
            elif len(clean_parts) == 1:
                # Only one part, could be company or location
                single_part = clean_parts[0].strip()
                if any(loc_indicator in single_part.lower() for loc_indicator in [',', 'offshore', 'remote', 'canada', 'usa', 'uae', 'saudi']):
                    company = "RigZone Partner"
                    location = single_part
                else:
                    company = single_part
                    location = "Various Locations"
            else:
                company = "RigZone Partner"
                location = "Various Locations"
            
            # Check for Featured Employer indicator
            featured_img = article.find('img', alt='Featured Employer')
            is_featured = featured_img is not None
            
            # Extract job description from the description div if available
            desc_div = article.find('div', class_='description')
            if desc_div:
                description_text = desc_div.get_text(strip=True)
            else:
                description_text = ""
            
            # Create comprehensive description
            description_parts = [
                f"Position: {title}",
                f"Company: {company}",
                f"Location: {location}"
            ]
            
            if is_featured:
                description_parts.append("Featured Employer: Yes")
            
            if description_text:
                description_parts.append(f"\nJob Details: {description_text}")
            
            description_parts.append("\nApply through RigZone for full job details and requirements.")
            
            description = "\n".join(description_parts)
            
            job_data = {
                "title": title,
                "company": company,
                "location": location,
                "url": job_url,
                "description": description,
                "is_featured": is_featured
            }
            
            jobs_data.append(job_data)
            
            print(f"Job {i+1}:")
            print(f"  Title: {title}")
            print(f"  Company: {company}")
            print(f"  Location: {location}")
            print(f"  Featured: {is_featured}")
            print(f"  URL: {job_url}")
            print("-" * 60)
            
        except Exception as e:
            print(f"Error parsing job article {i}: {e}")
            continue
    
    return jobs_data

def test_extraction():
    """Test the improved extraction"""
    print("Testing Improved RigZone Job Extraction")
    print("="*60)
    
    jobs = fetch_rigzone_jobs()
    
    print(f"\nSUMMARY:")
    print(f"Total jobs extracted: {len(jobs)}")
    
    if jobs:
        print("\nFirst job details:")
        first_job = jobs[0]
        for key, value in first_job.items():
            print(f"  {key}: {value}")
    
    # Save results to file for inspection
    with open('/Users/chriskerr/Projects/claude-test/backend/extracted_jobs.json', 'w', encoding='utf-8') as f:
        json.dump(jobs, f, indent=2, ensure_ascii=False)
    
    print(f"\nExtracted job data saved to: /Users/chriskerr/Projects/claude-test/backend/extracted_jobs.json")
    
    return jobs

if __name__ == "__main__":
    test_extraction()