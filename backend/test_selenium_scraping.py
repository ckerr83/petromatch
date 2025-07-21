#!/usr/bin/env python3

import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import json
import time

def scrape_orion_jobs_selenium(max_jobs: int = 5) -> list:
    """
    Scrape Orion Jobs using Selenium for JavaScript rendering
    """
    jobs = []
    
    try:
        print("Setting up Chrome driver...")
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        
        print("Navigating to Orion Jobs...")
        driver.get("https://www.orionjobs.com/job-search/?+Gas=")
        
        print("Waiting for page to load...")
        WebDriverWait(driver, 20).until(lambda driver: driver.execute_script("return document.readyState") == "complete")
        
        print("Waiting for dynamic content...")
        time.sleep(5)
        
        print("Current page title:", driver.title)
        print("Current URL:", driver.current_url)
        
        # Get page source for debugging
        page_source = driver.page_source
        print(f"Page source length: {len(page_source)} characters")
        
        # Look for job listings with multiple strategies
        job_selectors = [
            ".job-listing",
            ".job-item", 
            ".job-card",
            "[data-job-id]",
            ".posting",
            ".vacancy",
            ".opportunity",
            "article",
            ".search-result"
        ]
        
        job_elements = []
        for selector in job_selectors:
            try:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                print(f"Found {len(elements)} elements with selector '{selector}'")
                if elements:
                    job_elements = elements
                    break
            except Exception as e:
                print(f"Error with selector '{selector}': {e}")
                continue
        
        # Try XPath patterns
        if not job_elements:
            xpath_patterns = [
                "//div[contains(@class, 'job')]",
                "//div[contains(text(), 'Engineer')]",
                "//div[contains(text(), 'Technician')]",
                "//div[contains(text(), 'Manager')]",
                "//a[contains(@href, 'job')]"
            ]
            
            for xpath in xpath_patterns:
                try:
                    elements = driver.find_elements(By.XPATH, xpath)
                    print(f"Found {len(elements)} elements with XPath '{xpath}'")
                    if elements:
                        job_elements = elements[:max_jobs]
                        break
                except Exception as e:
                    print(f"Error with XPath '{xpath}': {e}")
                    continue
        
        # Extract job information
        for i, element in enumerate(job_elements[:max_jobs]):
            try:
                # Get the full text content
                job_text = element.text.strip()
                if not job_text:
                    continue
                
                # Parse the Orion Jobs format: Yesterday\nTR/078474\nWell Site HSE Supervisor Offshore\nCompetitive\nOman\nContract\nWe have a current op...
                lines = [line.strip() for line in job_text.split('\n') if line.strip()]
                
                if len(lines) < 3:
                    continue
                
                # Extract fields from the structured format
                date_posted = lines[0] if lines[0] and not lines[0].startswith('TR/') else "Recently"
                job_ref = ""
                title_line_idx = 1
                
                # Find job reference and title
                if len(lines) > 1 and lines[1].startswith('TR/'):
                    job_ref = lines[1]
                    title_line_idx = 2
                
                title = lines[title_line_idx] if len(lines) > title_line_idx else "Position Available"
                
                # Extract additional fields
                salary = ""
                location = "Location Not Specified"
                job_type = ""
                
                remaining_lines = lines[title_line_idx + 1:]
                
                # Look for location patterns (countries, cities)
                location_keywords = ['uk', 'usa', 'london', 'houston', 'aberdeen', 'norway', 'oman', 'qatar', 'uae', 'saudi', 'kuwait', 'iraq', 'algeria', 'nigeria', 'angola', 'brazil', 'mexico', 'canada', 'australia', 'scotland', 'england', 'texas', 'louisiana', 'california', 'north sea', 'gulf', 'offshore', 'onshore']
                salary_keywords = ['competitive', '$', '£', 'k', 'per', 'annum', 'day rate', 'negotiable']
                contract_keywords = ['contract', 'permanent', 'temp', 'full-time', 'part-time', 'freelance']
                
                for line in remaining_lines:
                    line_lower = line.lower()
                    if any(keyword in line_lower for keyword in location_keywords):
                        location = line
                    elif any(keyword in line_lower for keyword in salary_keywords):
                        salary = line
                    elif any(keyword in line_lower for keyword in contract_keywords):
                        job_type = line
                
                # Build description from remaining content
                description_parts = []
                if date_posted and date_posted != "Recently":
                    description_parts.append(f"Posted: {date_posted}")
                if salary:
                    description_parts.append(f"Salary: {salary}")
                if job_type:
                    description_parts.append(f"Type: {job_type}")
                if job_ref:
                    description_parts.append(f"Reference: {job_ref}")
                
                # Add any remaining lines as description
                desc_lines = remaining_lines[3:] if len(remaining_lines) > 3 else []
                if desc_lines:
                    description_parts.append(" ".join(desc_lines[:2]))
                
                if not description_parts:
                    description_parts.append(f"Oil and gas position: {title} based in {location}")
                
                description = " | ".join(description_parts)
                
                # Clean up the title to remove any reference numbers
                if job_ref and job_ref in title:
                    title = title.replace(job_ref, "").strip()
                
                # Ensure we have meaningful content
                if len(title) < 5 or title == "Position Available":
                    title = f"Oil & Gas Position {job_ref}" if job_ref else "Oil & Gas Opportunity"
                
                job = {
                    "title": title,
                    "company": "Orion Jobs Client",
                    "location": location,
                    "description": description,
                    "url": f"https://www.orionjobs.com/job-search/?+Gas=#{job_ref}" if job_ref else "https://www.orionjobs.com/job-search/?+Gas=",
                    "date_posted": "2024-01-01",
                    "board": "Orion Jobs"
                }
                
                jobs.append(job)
                print(f"Extracted job {i+1}: {title}")
                
            except Exception as e:
                print(f"Error extracting job {i+1}: {e}")
                continue
        
        print(f"Total jobs extracted: {len(jobs)}")
        
        # If no jobs found, print page source for debugging
        if len(jobs) == 0:
            print("\n=== PAGE SOURCE SAMPLE (first 2000 chars) ===")
            print(page_source[:2000])
            print("\n=== END PAGE SOURCE SAMPLE ===")
        
        driver.quit()
        return jobs
        
    except Exception as e:
        print(f"Error in scrape_orion_jobs_selenium: {e}")
        import traceback
        traceback.print_exc()
        try:
            driver.quit()
        except:
            pass
        return []

if __name__ == "__main__":
    print("Testing Selenium scraping for Orion Jobs...")
    jobs = scrape_orion_jobs_selenium(max_jobs=5)
    print(f"\nFound {len(jobs)} jobs")
    if len(jobs) > 0:
        print("\nSample job:")
        print(json.dumps(jobs[0], indent=2))
    else:
        print("No jobs found")