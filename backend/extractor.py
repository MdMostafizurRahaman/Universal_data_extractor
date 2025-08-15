# --- Imports ---
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import re
import json
import pandas as pd
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import asyncio
import time
from fpdf import FPDF
import os

 # --- FastAPI Setup ---
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# Ensure static directory exists before mounting
static_dir_path = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(static_dir_path, exist_ok=True)
from fastapi.staticfiles import StaticFiles
app.mount("/static", StaticFiles(directory=static_dir_path), name="static")
# --- Profile Extractor and PDF Maker ---
def extract_profiles(url):
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
    driver.get(url)
    time.sleep(3)
    # Scroll to bottom
    for _ in range(3):
        driver.execute_script("window.scrollBy(0, document.body.scrollHeight)")
        time.sleep(1)
    html = driver.page_source
    soup = BeautifulSoup(html, "lxml")
    profiles = []
    # Universal profile extraction: look for repeated containers (links, cards, rows, divs)
    profiles = []
    # Try to find profile blocks by common patterns
    # 1. Links to details pages (faculty, employee, etc.)
    # Try links first (for sites that use them)
    found_profiles = 0
    profile_links = soup.find_all('a', href=True)
    profile_keywords = [
        'professor', 'lecturer', 'doctor', 'department', 'faculty', 'designation', 'specialty', 'hospital', 'chamber',
        'contact', 'email', 'phone', 'research', 'publication', 'employee', 'staff', 'teacher', 'medical', 'clinic', 'practice', 'biography', 'cv', 'resume', 'name', 'qualification', 'experience', 'address', 'mobile', 'office', 'division', 'unit', 'section', 'group', 'role', 'title', 'position', 'subject', 'field', 'area', 'expertise', 'interest', 'profile', 'bio', 'about'
    ]
    navigation_keywords = [
        'academics', 'academic', 'programs', 'admission', 'libraries', 'bodies', 'institutes', 'constituent', 'affiliated', 'calendar', 'undergraduate', 'graduate', 'mphil', 'phd', 'international students', 'service', 'footer', 'home', 'about', 'news', 'events', 'contact', 'login', 'register', 'search', 'menu', 'sidebar', 'navigation', 'copyright', 'disclaimer', 'privacy', 'terms', 'departments', 'faculty', 'staff', 'employee', 'directory', 'list', 'members', 'committee', 'board', 'administration', 'management', 'office', 'unit', 'division', 'section', 'group', 'organization', 'org', 'orgs', 'people', 'personnel', 'team', 'teams', 'overview', 'info', 'information', 'details', 'resources', 'links', 'site', 'web', 'webpage', 'page', 'pages', 'main', 'general', 'profile', 'profiles', 'bio', 'bios', 'about'
    ]
    for a_tag in profile_links:
        text = a_tag.get_text(strip=True)
        href = a_tag['href']
        block = a_tag.parent
        if block and block.name == 'a':
            block = block.parent
        block_text = block.get_text(separator=' ', strip=True) if block else text
        main_text = block_text.split('\n')[0] if block_text else ''
        # Stricter filtering: skip navigation, social, empty links, blocks without profile keywords, blocks with navigation keywords, and invalid links/main_text
        def is_navigation(text):
            return any(re.search(r'\b' + re.escape(nav_kw) + r'\b', text.lower()) for nav_kw in navigation_keywords)
        if (
            not text or len(text) < 5 or
            any(x in href for x in ['login', 'facebook', 'youtube', 'service', 'dashboard', 'charter', 'online', 'home', 'contact', 'news', 'report', 'noc', 'tender', 'library', 'repository', 'forms', 'barta', 'archive', 'performance', 'visitor', 'graduate', 'result', 'alumni', 'annual', 'footer']) or
            not any(re.search(r'\b' + re.escape(kw) + r'\b', block_text.lower()) for kw in profile_keywords) or
            is_navigation(block_text) or
            href == '#' or not href.strip() or not main_text.strip() or is_navigation(main_text)
        ):
            continue
        # Auto-detect key-value pairs, require at least 2 fields (besides main_text, profile_link, block_text)
        profile = {'main_text': main_text, 'profile_link': href, 'block_text': block_text}
        field_count = 0
        for part in re.split(r'[;\n]', block_text):
            kv_match = re.match(r'\s*([\w\s\-]+)\s*[:：]\s*(.+)', part)
            if kv_match:
                key = kv_match.group(1).strip().lower().replace(' ', '_')
                value = kv_match.group(2).strip()
                if key and value:
                    profile[key] = value
                    field_count += 1
        if field_count >= 2:
            profiles.append(profile)
            found_profiles += 1
    # If not enough profiles found, scan for repeated blocks and table rows/cards
    if found_profiles < 5:
        # Table row extraction (for faculty lists, doctor lists, etc.)
        for table in soup.find_all('table'):
            headers = []
            # Try to get headers from thead or first row
            thead = table.find('thead')
            if thead:
                headers = [th.get_text(strip=True).lower().replace(' ', '_') for th in thead.find_all('th')]
            else:
                first_row = table.find('tr')
                if first_row:
                    headers = [td.get_text(strip=True).lower().replace(' ', '_') for td in first_row.find_all(['th', 'td'])]
            for tr in table.find_all('tr')[1:]:
                cells = tr.find_all(['td', 'th'])
                if len(cells) >= 2:
                    profile = {}
                    for idx, cell in enumerate(cells):
                        value = cell.get_text(separator=' ', strip=True)
                        key = headers[idx] if idx < len(headers) else f'field_{idx+1}'
                        # Try to map common headers to standard categories
                        if key in ['name', 'doctor_name', 'faculty_name', 'professor_name']:
                            key = 'name'
                        elif key in ['designation', 'title', 'position', 'role']:
                            key = 'designation'
                        elif key in ['hospital', 'institute', 'department', 'division', 'unit', 'section']:
                            key = 'organization'
                        elif key in ['email', 'e-mail', 'mail']:
                            key = 'email'
                        elif key in ['phone', 'mobile', 'contact']:
                            key = 'phone'
                        profile[key] = value
                    if any(re.search(r'\b' + re.escape(kw) + r'\b', ' '.join(profile.values()).lower()) for kw in profile_keywords):
                        profiles.append(profile)
        # Card/div block extraction (for doctor cards, etc.)
        block_tags = soup.find_all(['div', 'li', 'tr'])
        for block in block_tags:
            block_text = block.get_text(separator=' ', strip=True)
            main_text = block_text.split('\n')[0] if block_text else ''
            def is_navigation(text):
                return any(re.search(r'\b' + re.escape(nav_kw) + r'\b', text.lower()) for nav_kw in navigation_keywords)
            # Flexible: treat as profile if block has enough words, contains profile keywords, and is not navigation
            if (
                block_text and len(block_text.split()) > 8 and
                any(re.search(r'\b' + re.escape(kw) + r'\b', block_text.lower()) for kw in profile_keywords) and
                not is_navigation(block_text) and
                main_text.strip() and not is_navigation(main_text)
            ):
                profile = {'main_text': main_text, 'block_text': block_text}
                # Try to split by common delimiters to infer fields
                parts = re.split(r'[;\n,|\-]', block_text)
                # Pattern matching for common profile fields
                for idx, part in enumerate(parts):
                    kv_match = re.match(r'\s*([\w\s\-]+)\s*[:：]\s*(.+)', part)
                    if kv_match:
                        key = kv_match.group(1).strip().lower().replace(' ', '_')
                        value = kv_match.group(2).strip()
                        # Map to standard categories
                        if key in ['name', 'doctor_name', 'faculty_name', 'professor_name']:
                            key = 'name'
                        elif key in ['designation', 'title', 'position', 'role']:
                            key = 'designation'
                        elif key in ['hospital', 'institute', 'department', 'division', 'unit', 'section']:
                            key = 'organization'
                        elif key in ['email', 'e-mail', 'mail']:
                            key = 'email'
                        elif key in ['phone', 'mobile', 'contact']:
                            key = 'phone'
                        profile[key] = value
                    else:
                        value = part.strip()
                        # Heuristic: assign by position if not key-value
                        if idx == 0 and value:
                            profile['name'] = value
                        elif idx == 1 and value:
                            profile['designation'] = value
                        elif idx == 2 and value:
                            profile['organization'] = value
                        elif value and len(value.split()) > 1:
                            field_name = f'field_{idx+1}'
                            profile[field_name] = value
                profiles.append(profile)
    # If no profiles found, try to find repeated divs or rows
    if not profiles:
        for div in soup.find_all(['div', 'tr', 'li']):
            div_text = div.get_text(separator=' ', strip=True)
            if div_text and len(div_text.split()) > 5:
                profile = {'block_text': div_text}
                for part in re.split(r'[;\n]', div_text):
                    kv_match = re.match(r'\s*([\w\s\-]+)\s*[:：]\s*(.+)', part)
                    if kv_match:
                        key = kv_match.group(1).strip().lower().replace(' ', '_')
                        value = kv_match.group(2).strip()
                        if key and value:
                            profile[key] = value
                profiles.append(profile)
    print(f"[Profile Extractor] Found {len(profiles)} profiles.")
    if profiles:
        print(f"[Profile Extractor] Sample profile: {profiles[0]}")
    driver.quit()
    return profiles


@app.post("/profile_excel")
async def profile_excel(request: Request):
    body = await request.json()
    url = body.get("url")
    if not url:
        return {"error": "No URL provided."}
    import concurrent.futures
    loop = asyncio.get_event_loop()
    with concurrent.futures.ThreadPoolExecutor() as pool:
        profiles = await loop.run_in_executor(pool, extract_profiles, url)
    if not profiles:
        return {"error": "No profiles found."}

    from datetime import datetime
    filename = f"profiles_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    filepath = filename
    save_excel(profiles, filepath)
    static_dir = os.path.join(os.path.dirname(__file__), 'static')
    os.makedirs(static_dir, exist_ok=True)
    os.replace(filepath, os.path.join(static_dir, filename))
    excel_url = f"/static/{filename}"
    return {"excel_url": excel_url}
# --- Dynamic Extraction Function ---
def extract_data(url, data_types=["emails", "images", "tables"]):
    try:
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--no-sandbox")
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
        driver.get(url)
        time.sleep(3)
        # Scroll to bottom
        for _ in range(3):
            driver.execute_script("window.scrollBy(0, document.body.scrollHeight)")
            time.sleep(1)
        # Click 'Load more', 'Show more', etc.
        for btn in driver.find_elements(By.XPATH, "//button|//a"):
            try:
                text = btn.text.lower()
                if any(x in text for x in ["load more", "show more", "more", "next"]):
                    btn.click()
                    time.sleep(1)
            except Exception:
                pass
        # Try to close popups/modals
        for sel in ["button[aria-label='close']", "button.close", ".modal-close", ".popup-close"]:
            try:
                for btn in driver.find_elements(By.CSS_SELECTOR, sel):
                    btn.click()
                    time.sleep(0.5)
            except Exception:
                pass
        html = driver.page_source
        soup = BeautifulSoup(html, "lxml")
        result = {}
        if "emails" in data_types:
            result["emails"] = list(set(re.findall(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", html)))
        if "images" in data_types:
            result["images"] = [img['src'] for img in soup.find_all("img") if img.get("src")]
        if "tables" in data_types:
            tables = []
            for table in soup.find_all("table"):
                rows = []
                for tr in table.find_all("tr"):
                    cells = [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
                    rows.append(cells)
                tables.append(rows)
            result["tables"] = tables
        driver.quit()
        return result
    except Exception as e:
        import traceback
        print("Extraction error:", traceback.format_exc())
        return {"error": str(e)}

@app.post("/extract")
async def extract(request: Request):
    body = await request.json()
    url = body.get("url")
    data_types = body.get("data_types", ["emails", "images", "tables"])
    # Run Selenium in a thread to avoid blocking event loop
    import concurrent.futures
    loop = asyncio.get_event_loop()
    with concurrent.futures.ThreadPoolExecutor() as pool:
        result = await loop.run_in_executor(pool, extract_data, url, data_types)
    if isinstance(result, dict) and "error" in result:
        return {"error": result["error"]}
    # Save to Excel file
    try:
        import pandas as pd
        from datetime import datetime
        filename = f"extracted_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        with pd.ExcelWriter(filename) as writer:
            for key, value in result.items():
                if isinstance(value, list) and value and isinstance(value[0], list):
                    pd.DataFrame(value).to_excel(writer, sheet_name=key, index=False)
                else:
                    pd.DataFrame(value).to_excel(writer, sheet_name=key, index=False)
    except Exception as e:
        print(f"Excel save error: {e}")
    return {"result": result, "excel_file": filename}

# --- Utility Functions ---
def save_json(data, filename):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def save_csv(data, filename):
    if isinstance(data, dict):
        for key, value in data.items():
            pd.DataFrame(value).to_csv(f"{filename}_{key}.csv", index=False)
    else:
        pd.DataFrame(data).to_csv(filename, index=False)

def save_excel(data, filename):
    # If data is a list of dicts, ensure all possible keys are columns
    if isinstance(data, list) and data and isinstance(data[0], dict):
        # Standardize columns
        standard_cols = ['name', 'designation', 'organization', 'email', 'phone']
        def map_key(key):
            k = key.lower()
            if k in ['name', 'doctor_name', 'faculty_name', 'professor_name', 'main_text']:
                return 'name'
            elif k in ['designation', 'title', 'position', 'role']:
                return 'designation'
            elif k in ['hospital', 'institute', 'department', 'division', 'unit', 'section', 'organization', 'org']:
                return 'organization'
            elif k in ['email', 'e-mail', 'mail']:
                return 'email'
            elif k in ['phone', 'mobile', 'contact']:
                return 'phone'
            return None
        clean_profiles = []
        seen = set()
        for row in data:
            new_row = {col: '' for col in standard_cols}
            # Fill standard columns from mapped keys
            for k, v in row.items():
                col = map_key(k)
                if col and not new_row[col]:
                    new_row[col] = v
            # If any standard column is still empty, try to fill from generic columns
            for k, v in row.items():
                if not map_key(k):
                    # Heuristic: try to fill missing name/designation/organization from generic columns if possible
                    if not new_row['name'] and re.search(r'(professor|lecturer|teacher|dr\.|md\.|mrs\.|mr\.|ashraf|sumit|aziz|kabir|islam|rana|banoo|chowdhury|sultana|sharmin|shahriar|mannan|hussain|saha|chakroborty|farhana|karmaker|sikder|moonmoon|rubina)', str(v), re.I):
                        new_row['name'] = v
                    elif not new_row['designation'] and re.search(r'(professor|lecturer|assistant|chairperson|retired|emeritus|supernumerary|study leave|teacher)', str(v), re.I):
                        new_row['designation'] = v
                    elif not new_row['organization'] and re.search(r'(department|institute|faculty|school|center|bureau|unit|section|division)', str(v), re.I):
                        new_row['organization'] = v
            uniq = (new_row.get('name', '').strip().lower(), new_row.get('organization', '').strip().lower())
            if uniq in seen or not new_row.get('name'):
                continue
            seen.add(uniq)
            clean_profiles.append(new_row)
        df = pd.DataFrame(clean_profiles, columns=standard_cols)
        df.to_excel(filename, index=False)
    elif isinstance(data, dict):
        with pd.ExcelWriter(filename) as writer:
            for key, value in data.items():
                pd.DataFrame(value).to_excel(writer, sheet_name=key, index=False)
    else:
        pd.DataFrame(data).to_excel(filename, index=False)
