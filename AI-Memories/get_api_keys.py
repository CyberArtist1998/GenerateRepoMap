from playwright.sync_api import sync_playwright
import time

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    page = browser.new_page()
    
    # Open a new tab for API registration
    api_tab = browser.new_page()
    
    print("Opening WorldMonitor dashboard...")
    page.goto("http://localhost:3000", wait_until="networkidle", timeout=60000)
    time.sleep(2)
    page.screenshot(path="/tmp/dashboard.png")
    
    # Open API registration pages for essential services
    api_urls = {
        "AISStream (News)": "https://aisstream.com/",
        "Finnhub (Financial Markets)": "https://finnhub.io/",
        "NASA FIRMS (Satellite Fires)": "https://firms.modaps.eosdis.nasa.gov/api/",
        "AviationStack (Flight Data)": "https://aviationstack.com/"
    }
    
    print("\nOpening API registration pages...")
    for name, url in api_urls.items():
        print(f"  → {name}: {url}")
        try:
            api_tab.goto(url, wait_until="networkidle", timeout=30000)
            time.sleep(2)
            api_tab.screenshot(path=f"/tmp/api_{name.replace(' ', '_')}.png")
        except Exception as e:
            print(f"    Error opening {name}: {e}")
    
    # Take screenshot of all open pages
    page.screenshot(path="/tmp/all_pages.png")
    
    print("\n✅ All API registration pages opened!")
    print("📸 Screenshots saved to /tmp/")
