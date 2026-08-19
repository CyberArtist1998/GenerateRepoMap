from playwright.sync_api import sync_playwright
import time
import json

# Temporary email for verification (using mail.tm or similar)
TEMP_EMAIL = "worldmonitor@tuta.io"
TEMP_PASSWORD = "SecurePass123!"

def register_aisstream(page):
    """Register on AISStream and get API key"""
    print("📰 Registering on AISStream...")
    
    # Go to registration page
    page.goto("https://aisstream.com/", wait_until="networkidle", timeout=60000)
    time.sleep(3)
    
    # Look for sign up button
    try:
        signup_btn = page.locator('text=Sign Up, text=Register, text=Get Started').first
        if signup_btn.is_visible():
            signup_btn.click()
            print("  ✓ Clicked Sign Up")
            time.sleep(2)
    except Exception as e:
        print(f"  ⚠️ Could not find sign up button: {e}")
    
    # Fill registration form
    try:
        # Name field
        name_field = page.locator('input[name="name"], input[placeholder*="Name"]').first
        if name_field.is_visible():
            name_field.fill("World Monitor")
            print("  ✓ Entered name")
        
        # Email field
        email_field = page.locator('input[type="email"]').first
        if email_field.is_visible():
            email_field.fill(TEMP_EMAIL)
            print(f"  ✓ Entered email: {TEMP_EMAIL}")
        
        # Password field
        password_field = page.locator('input[type="password"]').first
        if password_field.is_visible():
            password_field.fill(TEMP_PASSWORD)
            print("  ✓ Entered password")
        
        # Submit form
        submit_btn = page.locator('button[type="submit"], text=Submit, text=Create Account').first
        if submit_btn.is_visible():
            submit_btn.click()
            print("  ✓ Submitted registration")
            time.sleep(5)
            
    except Exception as e:
        print(f"  ⚠️ Registration form issue: {e}")
    
    # Take screenshot of current state
    page.screenshot(path="/tmp/aisstream_registration.png")

def register_finnhub(page):
    """Register on Finnhub and get API key"""
    print("\n💰 Registering on Finnhub...")
    
    # Go to registration page
    page.goto("https://finnhub.io/register", wait_until="networkidle", timeout=60000)
    time.sleep(3)
    
    try:
        # Fill form
        name_field = page.locator('input[name="name"], input[placeholder*="Name"]').first
        if name_field.is_visible():
            name_field.fill("World Monitor")
        
        email_field = page.locator('input[type="email"]').first
        if email_field.is_visible():
            email_field.fill(TEMP_EMAIL)
        
        password_field = page.locator('input[type="password"]').first
        if password_field.is_visible():
            password_field.fill(TEMP_PASSWORD)
        
        # Submit
        submit_btn = page.locator('button[type="submit"], text=Register').first
        if submit_btn.is_visible():
            submit_btn.click()
            print("  ✓ Submitted Finnhub registration")
            time.sleep(5)
            
    except Exception as e:
        print(f"  ⚠️ Finnhub issue: {e}")
    
    page.screenshot(path="/tmp/finnhub_registration.png")

def register_nasa_firms(page):
    """Register on NASA FIRMS"""
    print("\n🔥 Registering on NASA FIRMS...")
    
    # NASA FIRMS doesn't require registration for basic API access
    # But let's check if there's an account system
    page.goto("https://firms.modaps.eosdis.nasa.gov/api/", wait_until="networkidle", timeout=60000)
    time.sleep(3)
    
    print("  ℹ️ NASA FIRMS - checking for API key requirements...")
    page.screenshot(path="/tmp/nasa_firms.png")

def register_aviationstack(page):
    """Register on AviationStack"""
    print("\n✈️ Registering on AviationStack...")
    
    # Go to registration page
    page.goto("https://aviationstack.com/register", wait_until="networkidle", timeout=60000)
    time.sleep(3)
    
    try:
        # Fill form
        name_field = page.locator('input[name="name"], input[placeholder*="Name"]').first
        if name_field.is_visible():
            name_field.fill("World Monitor")
        
        email_field = page.locator('input[type="email"]').first
        if email_field.is_visible():
            email_field.fill(TEMP_EMAIL)
        
        password_field = page.locator('input[type="password"]').first
        if password_field.is_visible():
            password_field.fill(TEMP_PASSWORD)
        
        # Submit
        submit_btn = page.locator('button[type="submit"], text=Register').first
        if submit_btn.is_visible():
            submit_btn.click()
            print("  ✓ Submitted AviationStack registration")
            time.sleep(5)
            
    except Exception as e:
        print(f"  ⚠️ AviationStack issue: {e}")
    
    page.screenshot(path="/tmp/aviationstack_registration.png")

# Main execution
with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    context = browser.new_context(viewport={"width": 1280, "height": 720})
    page = context.new_page()
    
    print("="*60)
    print("🤖 AUTOMATED API REGISTRATION FOR WORLD MONITOR")
    print("="*60)
    
    # Register on all services
    register_aisstream(page)
    register_finnhub(page)
    register_nasa_firms(page)
    register_aviationstack(page)
    
    # Take final screenshot
    page.screenshot(path="/tmp/all_registrations.png")
    
    print("\n✅ Registration attempts complete!")
    print("📸 Screenshots saved to /tmp/")
    print("\n⚠️ NOTE: You'll need to verify emails and get API keys manually.")
    print("   Check your email (worldmonitor@tuta.io) for verification links.")
