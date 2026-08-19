from playwright.sync_api import sync_playwright
import json
import urllib.request

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    page = browser.new_page()
    
    # Navigate to WorldMonitor dashboard
    print("Opening WorldMonitor at http://localhost:3000...")
    page.goto("http://localhost:3000", wait_until="domcontentloaded", timeout=60000)
    
    # Take a screenshot of the full dashboard
    page.screenshot(path="/tmp/dashboard-full.png", full_page=True)
    print("✓ Full dashboard screenshot saved")
    
    # Get health status from API
    try:
        response = urllib.request.urlopen("http://localhost:3000/api/health?compact=1", timeout=10)
        health_data = json.loads(response.read().decode())
        
        print("\n" + "="*70)
        print("📊 WORLD MONITOR HEALTH STATUS")
        print("="*70)
        
        sources = health_data.get('sources', {})
        total = sources.get('total', 0)
        ok = sources.get('ok', 0)
        crit = sources.get('critical', 0)
        warn = sources.get('warning', 0)
        
        print(f"Total Sources: {total}")
        print(f"✅ OK:         {ok}")
        print(f"❌ Critical:   {crit}")
        print(f"⚠️  Warning:    {warn}")
        
        # Count by category if available
        categories = health_data.get('categories', {})
        if categories:
            print("\n📋 BY CATEGORY:")
            for cat, data in categories.items():
                status = data.get('status', 'unknown')
                count = data.get('count', 0)
                icon = "✅" if status == "ok" else ("❌" if status == "critical" else "⚠️")
                print(f"   {icon} {cat}: {count}")
        
        # List critical sources
        critical_sources = health_data.get('critical', [])
        if critical_sources:
            print("\n🔴 CRITICAL SOURCES (need API keys or fixes):")
            for src in critical_sources[:30]:  # Show first 30
                name = src.get('name', 'Unknown')
                reason = src.get('reason', '')
                print(f"   • {name}")
                if reason:
                    print(f"     → {reason}")
        
        print("\n" + "="*70)
    except Exception as e:
        print(f"⚠️ Could not fetch health API: {e}")
    
    # Check what data is currently loaded in Redis
    try:
        import urllib.request
        response = urllib.request.urlopen("http://localhost:8079/INFO", timeout=10)
        info_data = response.read().decode()
        print("\n🔍 REDIS INFO (first 50 lines):")
        for i, line in enumerate(info_data.split('\n')[:50]):
            if 'db0:' in line or 'keys=' in line.lower():
                print(f"   {line}")
    except Exception as e:
        print(f"\n⚠️ Could not check Redis: {e}")
    
    browser.close()
