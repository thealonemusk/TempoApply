import asyncio
import requests
from bs4 import BeautifulSoup
import urllib.parse
from loguru import logger
from sqlalchemy.orm import Session

from backend.db.models import SessionLocal
from backend.pipeline import upsert_jobs
from backend.scrapers.base import normalize_job
from backend.scrapers.linkedin import _scrape_job_detail_bs4

TARGET_COMPANIES = [
    "Google", "Apple", "Tower Research", "Uber", "Directi", "Media.net", "Zeta", "Flock", 
    "LinkedIn", "Microsoft", "Amazon", "Adobe", "Cloudera", "Twitter", "Flipkart", "Yahoo", 
    "Rubrik", "Salesforce", "Slack", "Oracle", "MindTickle", "Paypal", "Rippling", "Goldman Sachs", 
    "Intuit", "De Shaw", "Arcesium", "Walmart", "ServiceNow", "Xilinx", "GitHub", "Nutanix", 
    "InMobi", "NortonLifeLock", "Codenation", "Cure.Fit", "Intel", "Atlassian", "Qualcomm", 
    "Visa", "eBay", "SumoLogic", "Expedia", "Paytm", "Swiggy", "Grab", "Morgan Stanley", 
    "VMware", "NVIDIA", "DropBox", "HackerRank", "Urban Company", "Citicorp", "OYO", "Cisco", 
    "Hotstar", "Hike messenger", "Ola", "MakeMyTrip", "Samsung", "Times Internet", "Zomato", "Dream11", 
    "Mentor Graphics", "Junglee Games", "Cadence", "Dunzo", "Rivigo", "Arista Networks", "Airtel", "NetApp", 
    "SAP", "Synopsys", "GreyOrange", "Unacademy", "Myntra", "ThoughtWorks", "American Express", 
    "Juniper Networks", "BrowserStack", "Citrix", "RedHat", "Ixigo", "Grofers", "Snapdeal", "ClearTax", 
    "BankBazar", "Livspace", "1mg", "Master Card", "BigBasket", "PayU", "Sirion Labs", "AJio", "Practo", 
    "Info Edge", "Delhivery", "Mobikwik", "Proptiger", "Akamai", "ClearTrip"
]

roles = ["Software Engineer", "Backend Engineer", "Full Stack Developer", "AI Engineer", "Software Developer"]
locations = ["Bengaluru", "Delhi", "Noida", "Pune", "Hyderabad", "Mumbai", "Gurugram", "India"]

async def main():
    logger.info(f"Starting targeted search for {len(TARGET_COMPANIES)} companies on LinkedIn...")
    
    # Chunk companies to build queries of 8 companies each (to stay within URL length and search complexity limits)
    chunks = [TARGET_COMPANIES[i:i + 8] for i in range(0, len(TARGET_COMPANIES), 8)]
    
    all_matching_jobs = []
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    }
    
    # We will search for each role and chunk combination
    for role in roles:
        for chunk in chunks:
            comp_query = " OR ".join(f'"{c}"' for c in chunk)
            keywords = f'"{role}" AND ({comp_query})'
            query = urllib.parse.quote(keywords)
            
            # Search in India, last 7 days
            search_url = f"https://www.linkedin.com/jobs/search/?keywords={query}&location=India&f_TPR=r604800&f_E=1%2C2"
            
            try:
                logger.info(f"Querying LinkedIn for: {role} in {chunk[0]}...")
                resp = await asyncio.to_thread(requests.get, search_url, headers=headers, timeout=15)
                if resp.status_code != 200:
                    logger.warning(f"Failed to fetch: {resp.status_code}")
                    continue
                    
                soup = BeautifulSoup(resp.content, 'html.parser')
                job_cards = soup.find_all(class_='base-card') or soup.find_all(class_='base-search-card')
                
                logger.info(f"Found {len(job_cards)} raw results for query.")
                
                for card in job_cards:
                    title_el = card.find(class_='base-search-card__title')
                    comp_el = card.find(class_='base-search-card__subtitle')
                    link_el = card.find('a', class_='base-card__full-link') or card.find('a')
                    loc_el = card.find(class_='job-search-card__location')
                    
                    title = title_el.text.strip() if title_el else ""
                    company = comp_el.text.strip() if comp_el else ""
                    url = link_el['href'] if link_el else ""
                    location = loc_el.text.strip() if loc_el else "India"
                    
                    if not title or not company or not url:
                        continue
                        
                    # Strict validation: ensure the company matches one of the target companies
                    company_lower = company.lower()
                    matched_company = None
                    for tc in TARGET_COMPANIES:
                        if tc.lower() in company_lower or company_lower in tc.lower():
                            matched_company = tc
                            break
                            
                    if not matched_company:
                        # Skip if it doesn't match any of the target companies
                        continue
                        
                    # Normalize URL
                    url = url.split('?')[0]
                    
                    # Fetch JD detail
                    detail = await asyncio.to_thread(_scrape_job_detail_bs4, url)
                    
                    job_data = {
                        "title": title,
                        "company": matched_company, # Use the clean name
                        "url": url,
                        "location": location,
                        "experience_required": "",
                        "salary_range": "",
                        "jd_text": detail.get("jd_text", ""),
                        "score": 100.0,
                        "fit_reason": f"Discovered via targeted search for {matched_company} on LinkedIn",
                        "missing_skills": [],
                        "seniority_level": "Entry Level",
                        "is_engineering_role": True,
                        "easy_apply": detail.get("easy_apply", False),
                        "recruiter_name": "",
                        "recruiter_profile": "",
                        "platform": "linkedin"
                    }
                    
                    all_matching_jobs.append(job_data)
                    logger.info(f"Match found: {title} at {matched_company}")
                    
                # Small courtesy delay between queries
                await asyncio.sleep(1.5)
                
            except Exception as e:
                logger.error(f"Error querying {role} in {chunk[0]}: {e}")
                
    if all_matching_jobs:
        logger.info(f"Upserting {len(all_matching_jobs)} matched jobs into database...")
        db = SessionLocal()
        try:
            added = upsert_jobs(all_matching_jobs, db)
            logger.info(f"Successfully added {added} new jobs to the database!")
        finally:
            db.close()
    else:
        logger.info("No matching jobs found during this run.")

if __name__ == '__main__':
    asyncio.run(main())
