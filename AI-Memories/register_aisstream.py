from playwright.sync_api import sync_playwright
import time

with sync_playwright() as p:
    # Launch browser in headed mode so we can see what's happening
    browser = p.chromium.launch(headless=False)
    page = browser.new_page(viewport={"width": 1280, "height": 720})
    
    print("="*70)
    print("📰 REGISTERING ON AISTREAM - Step by Step")
    print("="*70)
    
    # Step 1: Open AISStream homepage
    print("\n[Step 1] Opening AISStream website...")
    page.goto("https://aisstream.com/", wait_until="networkidle", timeout=60000)
    time.sleep(2)
    page.screenshot(path="/tmp/step1_aisstream_home.png", full_page=True)
    print("  ✓ Homepage loaded - screenshot saved")
    
    # Step 2: Find and click Sign Up / Get Started button
    print("\n[Step 2] Looking for registration button...")
    
    # Try different selectors for sign up button
    signup_selectors = [
        'text=Sign Up',
        'text=Register', 
        'text=Get Started',
        'a[href*="signup"]',
        'a[href*="register"]',
        'button:has-text("Start")'
    ]
    
    signup_found = False
    for selector in signup_selectors:
        try:
            btn = page.locator(selector).first
            if btn.is_visible():
                print(f"  ✓ Found button with selector: {selector}")
                btn.click()
                time.sleep(3)
                page.screenshot(path="/tmp/step2_registration_page.png", full_page=True)
                print("  ✓ Clicked! Registration page loaded")
                signup_found = True
                break
        except Exception as e:
            continue
    
    if not signup_found:
        print("  ⚠️ Could not find sign up button automatically")
        print("  ℹ️ Taking screenshot of current page...")
        page.screenshot(path="/tmp/step2_manual_check.png", full_page=True)
    
    # Step 3: Fill registration form if we're on a registration page
    print("\n[Step 3] Filling registration form...")
    
    try:
        # Look for email field
        email_field = page.locator('input[type="email"]').first
        if email_field.is_visible():
            print("  ✓ Found email field")
            email_field.fill("user@gmail.com")  # Use your real email
            time.sleep(1)
        
        # Look for name field
        name_field = page.locator('input[name*="name"], input[placeholder*="Name"]').first
        if name_field.is_visible():
            print("  ✓ Found name field")
            name_field.fill("World Monitor User")
            time.sleep(1)
        
        # Look for password field
        password_field = page.locator('input[type="password"]').first
        if password_field.is_visible():
            print("  ✓ Found password field")
            password_field.fill("SecurePass123!")
            time.sleep(1)
        
        # Submit form
        submit_btn = page.locator('button[type="submit"], text=Submit, text=Create Account').first
        if submit_btn.is_visible():
            print("  ✓ Found submit button")
            submit_btn.click()
            time.sleep(3)
            print("  ✓ Form submitted!")
        
    except Exception as e:
        print(f"  ⚠️ Could not fill form automatically: {e}")
    
    # Step 4: Take final screenshot
    page.screenshot(path="/tmp/step4_after_registration.png", full_page=True)
    print("\n[Step 4] Final state captured")
    
    print("\n" + "="*70)
    print("✅ AISStream registration attempt complete!")
    print("="*70)
    print("\n📸 Screenshots saved to /tmp/:")
    print("   - step1_aisstream_home.png (homepage)")
    print("   - step2_registration_page.png (after clicking sign up)")
    print("   - step4_after_registration.png (final state)")
    print("\n⚠️ Next steps:")
    print("   1. Check the screenshots to see what happened")
    print("   2. If registration worked, check your email for verification")
    print("   3. Once verified, find API key in account settings")
    print("   4. Send me the API key and I'll add it to WorldMonitor!")
