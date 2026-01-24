"""
Lucida-Sync - Python Web Scraper
Web scraping client for Lucida.to
"""
from curl_cffi import requests
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
import asyncio 
from typing import Optional, List, Dict, Any, Union
import re
import os
import random
from urllib.parse import urljoin, quote
import time
from collections import deque
from datetime import datetime, timedelta
from rich.console import Console

console = Console()

class RateLimiter:
    """
    Advanced rate limiter with sliding window and exponential backoff.
    Ensures we never exceed Lucida.to's request limits.
    """

    def __init__(
        self,
        requests_per_minute: int = 30,
        requests_per_hour: int = 500,
        min_delay: float = 2.0,
    ):
        self.requests_per_minute = requests_per_minute
        self.requests_per_hour = requests_per_hour
        self.min_delay = min_delay

        # Track request timestamps
        self.request_times = deque(maxlen=requests_per_hour)
        self.last_request_time = 0

        # Exponential backoff for errors
        self.consecutive_errors = 0
        self.max_backoff = 300  # 5 minutes max

    def wait(self):
        """Wait if necessary to respect rate limits"""
        current_time = time.time()

        # Enforce minimum delay between requests
        time_since_last = current_time - self.last_request_time
        if time_since_last < self.min_delay:
            sleep_time = self.min_delay - time_since_last
            time.sleep(sleep_time)
            current_time = time.time()

        # Check per-minute limit (sliding window)
        one_minute_ago = current_time - 60
        recent_requests = sum(1 for t in self.request_times if t > one_minute_ago)
        if recent_requests >= self.requests_per_minute:
            # Calculate wait time until oldest request expires
            oldest_in_window = min(
                (t for t in self.request_times if t > one_minute_ago),
                default=one_minute_ago,
            )
            wait_time = 60 - (current_time - oldest_in_window) + 1
            print(f"Rate limit: waiting {wait_time:.1f}s (per-minute limit)")
            time.sleep(wait_time)
            current_time = time.time()

        # Check per-hour limit
        one_hour_ago = current_time - 3600
        hour_requests = sum(1 for t in self.request_times if t > one_hour_ago)
        if hour_requests >= self.requests_per_hour:
            oldest_in_hour = min(
                (t for t in self.request_times if t > one_hour_ago),
                default=one_hour_ago,
            )
            wait_time = 3600 - (current_time - oldest_in_hour) + 1
            print(f"Rate limit: waiting {wait_time / 60:.1f}m (per-hour limit)")
            time.sleep(wait_time)
            current_time = time.time()

        # Exponential backoff for consecutive errors
        if self.consecutive_errors > 0:
            backoff = min(
                self.min_delay * (2**self.consecutive_errors),
                self.max_backoff,
            )
            print(
                f"Exponential backoff: waiting {backoff:.1f}s "
                f"(error #{self.consecutive_errors})"
            )
            time.sleep(backoff)
            current_time = time.time()

        # Record this request
        self.request_times.append(current_time)
        self.last_request_time = current_time

    def record_success(self):
        """Reset error counter on successful request"""
        self.consecutive_errors = 0

    def record_error(self):
        """Increment error counter for backoff calculation"""
        self.consecutive_errors += 1

    def get_stats(self) -> Dict[str, Any]:
        """Get current rate limiter statistics"""
        current_time = time.time()
        one_minute_ago = current_time - 60
        one_hour_ago = current_time - 3600

        return {
            "requests_last_minute": sum(
                1 for t in self.request_times if t > one_minute_ago
            ),
            "requests_last_hour": sum(
                1 for t in self.request_times if t > one_hour_ago
            ),
            "consecutive_errors": self.consecutive_errors,
            "total_requests": len(self.request_times),
        }


class LucidaClient:
    """Client for interacting with Lucida.to"""

    def __init__(
        self,
        base_url: str = "https://lucida.to",
        timeout: int = 30,
        requests_per_minute: int = 30,
        requests_per_hour: int = 500,
    ):
        self.base_url = base_url
        self.timeout = timeout
        self.session = requests.Session(impersonate="chrome120")
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }
        )

        # Initialize advanced rate limiter
        self.rate_limiter = RateLimiter(
            requests_per_minute=requests_per_minute,
            requests_per_hour=requests_per_hour,
            min_delay=2.0,  # Conservative 2 second minimum delay
        )

    def _rate_limit(self):
        """Apply rate limiting before making requests"""
        self.rate_limiter.wait()

    def _launch_browser_context(self, p, user_data_dir: str):
        """Helper to launch a persistent browser context with stealth settings."""
        args = [
            "--disable-blink-features=AutomationControlled",
            "--disable-infobars",
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--disable-extensions",
            "--disable-gpu",
            "--exclude-switches=enable-automation",
            "--use-fake-ui-for-media-stream",
        ]
        
        context = p.chromium.launch_persistent_context(
            user_data_dir,
            headless=False,
            args=args,
            viewport={'width': 1920, 'height': 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        
        # Additional stealth scripts
        if context.pages:
            page = context.pages[0]
        else:
            page = context.new_page()
            
        page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        return context, page

    async def download_track(self, url: str, output_path: Optional[str] = None, page=None) -> Dict[str, Any]:
        """
        Asynchronous version of download_track.
        """
        download_dir = os.getenv("DOWNLOAD_DIR", r"C:\Musics\FLAC")
        
        async def _perform_download_async(p_page):
            try:
                os.makedirs(download_dir, exist_ok=True)
                
                console.print(f"[cyan]Navigating to Lucida:[/cyan] {url}")
                # Use 'commit' to get control the moment the server responds
                await p_page.goto(f"{self.base_url}?url={url}", wait_until="commit", timeout=90000)

                download_btn_selector = "button:has-text('Download'), button:has-text('Get')"
                
                # Wait for button
                console.print(f"[dim]Waiting for download button...[/dim]")
                button_found = False
                for i in range(150): # 30 seconds max
                    if await p_page.locator(download_btn_selector).first.is_visible():
                        button_found = True
                        break
                    
                    if await p_page.locator("iframe[src*='cloudflare']").is_visible() or "Verify you are human" in await p_page.title():
                        console.print("[bold red]CAPTCHA DETECTED: Solve it to continue...[/bold red]")
                        await p_page.wait_for_selector(download_btn_selector, timeout=300000)
                        button_found = True
                        break
                        
                    await asyncio.sleep(0.1) # Faster polling (0.1s)
                
                if not button_found:
                    return {"success": False, "error": "Download button never appeared."}

                await p_page.wait_for_selector(download_btn_selector, state="visible", timeout=10000)
                
                # Click as soon as visible (no more long stabilization sleep)
                await asyncio.sleep(0.3) 
                
                console.print(f"[bold yellow]Clicking download button...[/bold yellow]")
                async with p_page.expect_download(timeout=300000) as download_info:
                    await p_page.locator(download_btn_selector).first.click(force=True)
                
                download = await download_info.value
                console.print(f"[green]Download starting:[/green] {download.suggested_filename}")
                
                if output_path:
                    final_path = os.path.abspath(output_path)
                else:
                    final_path = os.path.abspath(os.path.join(download_dir, download.suggested_filename))
                
                os.makedirs(os.path.dirname(final_path), exist_ok=True)
                await download.save_as(final_path)
                
                if os.path.exists(final_path):
                    size = os.path.getsize(final_path)
                    return {"success": True, "filepath": final_path, "size": size}
                else:
                    return {"success": False, "error": f"File saved but not found at: {final_path}"}

            except Exception as e:
                return {"success": False, "error": str(e)}

        if page:
            return await _perform_download_async(page)
        else:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                new_page = await browser.new_page()
                result = await _perform_download_async(new_page)
                await browser.close()
                return result
