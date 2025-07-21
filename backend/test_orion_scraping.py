#!/usr/bin/env python3

import requests
from bs4 import BeautifulSoup
import json

def test_orion_scraping():
    """Test traditional Orion Jobs scraping"""
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
    }
    
    # Try the main URL
    url = "https://www.orionjobs.com/job-search/?+Gas="
    print(f"Testing URL: {url}")
    
    try:
        response = requests.get(url, headers=headers, timeout=15)
        print(f"Status Code: {response.status_code}")
        print(f"Content Length: {len(response.content)} bytes")
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Print page title
        title = soup.find('title')
        print(f"Page Title: {title.get_text() if title else 'No title'}")
        
        # Look for any job-related content
        job_keywords = ['engineer', 'technician', 'manager', 'supervisor', 'analyst', 'specialist', 'drilling', 'offshore']
        page_text = soup.get_text().lower()
        
        print("\nJob keyword analysis:")
        for keyword in job_keywords:
            count = page_text.count(keyword)
            if count > 0:
                print(f"  {keyword}: {count} occurrences")
        
        # Try to find job elements
        job_selectors = [
            'div.job-listing',
            'div.job-item', 
            'article.job',
            'div[class*="job"]',
            'li[class*="job"]',
            '.job-card',
            '.position',
            '.vacancy',
            'tr[class*="job"]',
            '.search-result'
        ]
        
        print("\nTrying job selectors:")
        found_elements = False
        for selector in job_selectors:
            try:
                elements = soup.select(selector)
                print(f"  {selector}: {len(elements)} elements")
                if elements:
                    found_elements = True
                    print(f"    First element text: {elements[0].get_text()[:100]}...")
            except Exception as e:
                print(f"    Error with {selector}: {e}")
        
        # Look for forms or search functionality
        forms = soup.find_all('form')
        print(f"\nFound {len(forms)} forms on page")
        
        # Look for script tags (might indicate dynamic loading)
        scripts = soup.find_all('script')
        print(f"Found {len(scripts)} script tags")
        
        # Check for specific Orion Jobs content
        orion_specific = soup.find_all(text=lambda text: text and 'orion' in text.lower())
        print(f"Found {len(orion_specific)} Orion-specific text elements")
        
        # Save sample of page content for analysis
        print(f"\nPage content sample (first 1000 chars):")
        print(response.text[:1000])
        
        return found_elements
        
    except Exception as e:
        print(f"Error: {e}")
        return False

if __name__ == "__main__":
    print("Testing Orion Jobs traditional scraping...")
    success = test_orion_scraping()
    print(f"\nResult: {'Found job elements' if success else 'No job elements found'}")