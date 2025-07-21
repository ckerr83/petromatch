#!/usr/bin/env python3

import requests
import json

def test_orion_api():
    """Test if Orion Jobs has any API endpoints we can use"""
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'en-US,en;q=0.5',
        'Content-Type': 'application/json',
        'Referer': 'https://www.orionjobs.com/job-search/?+Gas='
    }
    
    # Common API endpoint patterns for job sites
    api_endpoints = [
        "https://www.orionjobs.com/api/jobs",
        "https://www.orionjobs.com/api/search",
        "https://www.orionjobs.com/api/job-search",
        "https://www.orionjobs.com/jobs/api",
        "https://www.orionjobs.com/api/v1/jobs",
        "https://api.orionjobs.com/jobs",
        "https://www.orionjobs.com/search/jobs",
        "https://www.orionjobs.com/wp-json/wp/v2/jobs",
        "https://www.orionjobs.com/ajax/jobs",
        "https://www.orionjobs.com/jobs/search"
    ]
    
    # Try with different search parameters
    search_params = [
        {"q": "gas", "category": "oil-gas"},
        {"search": "engineer"},
        {"keywords": "gas"},
        {"term": "petroleum"},
        {"sector": "oil-gas"}
    ]
    
    print("Testing potential API endpoints...")
    
    for endpoint in api_endpoints:
        print(f"\nTesting: {endpoint}")
        
        # Try GET request first
        try:
            response = requests.get(endpoint, headers=headers, timeout=10)
            print(f"  GET Status: {response.status_code}")
            
            if response.status_code == 200:
                content_type = response.headers.get('content-type', '')
                print(f"  Content-Type: {content_type}")
                
                if 'json' in content_type:
                    try:
                        data = response.json()
                        print(f"  JSON Response: {str(data)[:200]}...")
                        if isinstance(data, list) and len(data) > 0:
                            print(f"  Found {len(data)} items in response")
                        elif isinstance(data, dict) and 'jobs' in data:
                            print(f"  Found 'jobs' key in response")
                    except:
                        print(f"  Invalid JSON response")
                else:
                    print(f"  HTML/Text response length: {len(response.text)}")
                    
        except Exception as e:
            print(f"  GET Error: {e}")
        
        # Try POST with search parameters
        for params in search_params:
            try:
                response = requests.post(endpoint, json=params, headers=headers, timeout=10)
                if response.status_code == 200:
                    print(f"  POST with {params}: Status {response.status_code}")
                    content_type = response.headers.get('content-type', '')
                    if 'json' in content_type:
                        try:
                            data = response.json()
                            if data and len(str(data)) > 50:
                                print(f"    JSON Response: {str(data)[:150]}...")
                        except:
                            pass
                break  # Only try first successful param set
            except:
                continue

    print("\n" + "="*50)
    print("Testing for AJAX/GraphQL endpoints...")
    
    # Check for GraphQL
    graphql_endpoints = [
        "https://www.orionjobs.com/graphql",
        "https://www.orionjobs.com/api/graphql"
    ]
    
    for endpoint in graphql_endpoints:
        try:
            query = {"query": "{ jobs { title company location } }"}
            response = requests.post(endpoint, json=query, headers=headers, timeout=10)
            print(f"GraphQL {endpoint}: Status {response.status_code}")
            if response.status_code == 200:
                print(f"  Response: {response.text[:200]}...")
        except Exception as e:
            print(f"GraphQL {endpoint}: Error {e}")

if __name__ == "__main__":
    test_orion_api()