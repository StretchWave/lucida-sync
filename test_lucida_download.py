import asyncio
import os
from lucida_client import LucidaClient
from playwright.async_api import async_playwright

async def test_download():
    # Known working Amazon Music track link (Jake Cornell - Back To You)
    # Ensure this is a valid link. If it expires, we might need a fresh one, but Amazon links are usually stable.
    track_url = "https://music.amazon.com/albums/B0DJ1TCQNJ?trackAsin=B0DJ1RTS6F"
    
    print(f"Testing download for: {track_url}")
    
    # Clean up previous test
    if os.path.exists("test_download_retry.flac"):
        os.remove("test_download_retry.flac")
    
    async with async_playwright() as p:
        # Launch visible browser to monitor the interaction
        browser = await p.chromium.launch(
            headless=False,
            args=["--disable-blink-features=AutomationControlled"]
        )
        page = await browser.new_page()
        
        client = LucidaClient()
        
        print("Starting download process...")
        try:
            result = await client.download_track(track_url, output_path="./test_download_retry.flac", page=page)
            print(f"Download Result: {result}")
        except Exception as e:
            print(f"Test Failed: {e}")
        finally:
            # Keep browser open briefly to see result
            await asyncio.sleep(5)
            await browser.close()

if __name__ == "__main__":
    asyncio.run(test_download())
