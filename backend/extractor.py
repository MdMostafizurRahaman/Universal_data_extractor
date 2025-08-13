# --- Imports ---
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import re
import json
import pandas as pd
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import asyncio
from playwright.async_api import async_playwright

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
async def extract_data(url, data_types=["emails", "images", "tables"]):
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto(url)
            await page.wait_for_load_state("load", timeout=60000)
            # Dynamic interaction: scroll, click buttons, handle popups
            for _ in range(3):
                await page.evaluate("window.scrollBy(0, document.body.scrollHeight)")
                await page.wait_for_timeout(1000)

            # Click all visible 'Load more', 'Show more', or similar buttons
            try:
                buttons = await page.query_selector_all("button, a")
            except Exception:
                buttons = []
            for btn in buttons:
                try:
                    text = await btn.inner_text()
                    if any(x in text.lower() for x in ["load more", "show more", "more", "next"]):
                        await btn.click()
                        await page.wait_for_timeout(1000)
                except Exception:
                    pass

            # Handle popups/modals (try to close common ones)
            for sel in ["button[aria-label='close']", "button.close", ".modal-close", ".popup-close"]:
                try:
                    close_btns = await page.query_selector_all(sel)
                except Exception:
                    close_btns = []
                for btn in close_btns:
                    try:
                        await btn.click()
                        await page.wait_for_timeout(500)
                    except Exception:
                        pass

            html = await page.content()
            from bs4 import BeautifulSoup
            import re
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
            await browser.close()
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
    result = await extract_data(url, data_types)
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
