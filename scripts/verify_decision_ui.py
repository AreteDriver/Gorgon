#!/usr/bin/env python3
"""Verify Decision Support UI is working correctly with Playwright."""

import asyncio
import subprocess
from pathlib import Path
from playwright.async_api import async_playwright

SCREENSHOTS_DIR = Path("/tmp/gorgon-ui-verify")
FRONTEND_URL = "http://localhost:3001"


async def get_token():
    """Get auth token via curl."""
    result = subprocess.run(
        [
            "curl",
            "-s",
            "-X",
            "POST",
            "http://localhost:8000/v1/auth/login",
            "-H",
            "Content-Type: application/json",
            "-d",
            '{"user_id": "demo", "password": "demo"}',
        ],
        capture_output=True,
        text=True,
    )
    import json

    try:
        data = json.loads(result.stdout)
        return data.get("access_token")
    except Exception:
        return None


async def verify_decision_support():
    """Run through the Decision Support flow and capture screenshots."""
    SCREENSHOTS_DIR.mkdir(exist_ok=True)

    print("1. Getting auth token...")
    token = await get_token()
    if not token:
        print("   FAILED to get token")
        return False
    print(f"   Token: {token[:15]}...")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1920, "height": 1080})
        page = await context.new_page()

        print("2. Loading app and setting token...")
        await page.goto(FRONTEND_URL)
        await page.wait_for_load_state("networkidle")
        await page.evaluate(f"() => localStorage.setItem('gorgon_token', '{token}')")
        print("   Token stored: Yes")

        print("3. Navigating to Decision Support...")
        await page.goto(f"{FRONTEND_URL}/decisions")
        await page.wait_for_load_state("networkidle")
        await page.wait_for_timeout(1000)
        await page.screenshot(path=SCREENSHOTS_DIR / "01_decision_page.png")

        print("4. Filling form...")
        await page.wait_for_selector("textarea", timeout=5000)
        await page.locator("textarea").first.fill(
            "Should we use PostgreSQL or MongoDB for our user management microservice?"
        )
        textareas = page.locator("textarea")
        if await textareas.count() > 1:
            await textareas.nth(1).fill(
                "Building a user management service with complex relationships"
            )
        await page.screenshot(path=SCREENSHOTS_DIR / "02_form_filled.png")

        print("5. Clicking Get Recommendation...")
        btn = page.locator('button:has-text("Get Recommendation")')
        await btn.click()
        await page.wait_for_timeout(3000)
        await page.screenshot(path=SCREENSHOTS_DIR / "03_after_click.png")

        # Check for loading state (more flexible matching)
        analyzing = await page.locator("text=/Analyzing/i").count() > 0
        analyzing_decision = await page.locator('text="Analyzing Decision"').count() > 0
        print(f"   Loading state: {analyzing or analyzing_decision}")

        if analyzing or analyzing_decision:
            print("6. Workflow started! Waiting for completion (up to 4 min)...")
            try:
                await page.wait_for_selector('text="Analysis Complete"', timeout=240000)
                print("   SUCCESS!")
                await page.screenshot(
                    path=SCREENSHOTS_DIR / "04_completed.png", full_page=True
                )
            except Exception:
                print("   Timeout - capturing current state...")
                await page.screenshot(
                    path=SCREENSHOTS_DIR / "04_timeout.png", full_page=True
                )
        else:
            print("6. No loading state detected")
            await page.screenshot(path=SCREENSHOTS_DIR / "04_no_loading.png")

        # Final verification
        print("\n7. Final state:")
        await page.screenshot(path=SCREENSHOTS_DIR / "05_final.png", full_page=True)

        has_recommendation = (
            await page.locator(
                'h3:has-text("Recommendation"), [class*="CardTitle"]:has-text("Recommendation")'
            ).count()
            > 0
        )
        has_analysis = await page.locator('text="Analysis Complete"').count() > 0
        has_metrics = await page.locator('text="Tokens Used"').count() > 0

        print(f"   Analysis Complete: {has_analysis}")
        print(f"   Recommendation section: {has_recommendation}")
        print(f"   Metrics displayed: {has_metrics}")

        await browser.close()

    print(f"\nScreenshots: {SCREENSHOTS_DIR}")
    return True


if __name__ == "__main__":
    asyncio.run(verify_decision_support())
