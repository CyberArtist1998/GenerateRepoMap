
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)  # Show the browser window~!
    page = browser.new_page()
    
    # Navigate to Google search for "Cats"
    page.goto("https://www.google.com/search?q=Cats", wait_until="domcontentloaded")
    
    # Wait a bit for everything to load nicely
    page.wait_for_timeout(5000)
    
    # Take the screenshot and save to Desktop!
    desktop_path = "C:/Users/RedRain2077/Desktop/google_cats_screenshot.png"
    page.screenshot(path=desktop_path, full_page=True)
    print(f"Screenshot saved to: {desktop_path}")
    
    browser.close()

print("Done~! Meow! (=^･ω･^=)")
