from playwright.sync_api import sync_playwright
import json
import urllib.request

with sync_playwright() as p:
    # Launch browser in headed mode so we can see it
    browser = p.chromium.launch(headless=False)
    context = browser.new_context(viewport={"width": 1920, "height": 1080})
    page = context.new_page()
    
    # Navigate to WorldMonitor dashboard - use 'load' instead of 'networkidle'
    print("Opening WorldMonitor at http://localhost:3000...")
    try:
        page.goto("http://localhost:3000", wait_until="domcontentloaded", timeout=30000)
    except Exception as e:
        print(f"⚠ Initial load issue (continuing anyway): {e}")
    
    # Wait for content to render
    page.wait_for_timeout(8000)
    
    # Take initial screenshot
    try:
        page.screenshot(path="/tmp/worldmonitor-initial.png", full_page=True)
        print("✓ Initial screenshot saved")
    except Exception as e:
        print(f"⚠ Screenshot issue: {e}")
    
    # Find and click the SUMMARIZE button
    summarize_btn = page.query_selector("*:has-text('SUMMARIZE')") or \
                    page.query_selector("[class*='summarize']")
    
    if summarize_btn:
        print("\n✓ Found SUMMARIZE button, clicking it...")
        try:
            summarize_btn.click()
            print("✓ Clicked SUMMARIZE button!")
            
            # Wait for brief to generate
            page.wait_for_timeout(10000)
            
            # Take screenshot after click
            page.screenshot(path="/tmp/after-summarize-click.png", full_page=True)
            print("✓ Screenshot saved after clicking SUMMARIZE")
        except Exception as e:
            print(f"⚠ Click issue: {e}")
    else:
        print("\n✗ Could not find SUMMARIZE button")
    
    # Find and enable auto-timer (try 5m option)
    try:
        # Look for the dropdown or options
        auto_options = page.query_selector_all("*:has-text('Auto:')")
        if auto_options:
            print(f"\n✓ Found {len(auto_options)} Auto-timer elements")
            
            # Try clicking "Auto: 5m" option
            five_min_option = page.query_selector("*:has-text('Auto: 5m')")
            if five_min_option:
                print("✓ Found 'Auto: 5m' option, enabling it...")
                try:
                    five_min_option.click()
                    print("✓ Enabled Auto-timer (5 minutes)")
                    
                    # Wait and take screenshot
                    page.wait_for_timeout(3000)
                    page.screenshot(path="/tmp/auto-timer-enabled.png", full_page=True)
                    print("✓ Screenshot saved with auto-timer enabled")
                except Exception as e:
                    print(f"⚠ Auto-timer click issue: {e}")
            else:
                print("✗ Could not find 'Auto: 5m' option specifically")
        else:
            print("\n✗ No Auto-timer elements found")
    except Exception as e:
        print(f"\n⚠ Auto-timer search issue: {e}")
    
    # Extract health status from API if available
    try:
        with urllib.request.urlopen("http://localhost:3000/api/health?compact=1", timeout=5) as response:
            data = json.loads(response.read().decode())
            print(f"\n📊 Health Status:")
            if 'sources' in data:
                for source in data['sources'][:10]:  # First 10 sources
                    status = source.get('status', 'unknown')
                    name = source.get('name', 'N/A')
                    print(f"  {name}: {status}")
    except Exception as e:
        print(f"\n⚠ Could not fetch health API: {e}")
    
    # Final screenshot
    page.wait_for_timeout(3000)
    try:
        page.screenshot(path="/tmp/worldmonitor-final.png", full_page=True)
        print("\n✓ Final screenshot saved")
    except Exception as e:
        print(f"\n⚠ Final screenshot issue: {e}")
    
    print("\n📁 All screenshots saved in /tmp/ directory")
    browser.close()
