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

# --- FastAPI Setup ---
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
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
    with pd.ExcelWriter(filename) as writer:
        if isinstance(data, dict):
            for key, value in data.items():
                pd.DataFrame(value).to_excel(writer, sheet_name=key, index=False)
        else:
            pd.DataFrame(data).to_excel(writer, index=False)
