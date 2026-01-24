import os
import time
import random
import re
import asyncio
from lucida_client import LucidaClient
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from dotenv import load_dotenv, set_key
from rich.console import Console
from rich.prompt import Prompt
from playwright.async_api import async_playwright

console = Console()

class SpotifyToFlac:
    def __init__(self):
        self.client = LucidaClient()
        self.setup_credentials()
        
    def setup_credentials(self):
        """Load credentials from .env or ask user."""
        load_dotenv()
        
        self.sp_client_id = os.getenv("SPOTIPY_CLIENT_ID")
        self.sp_client_secret = os.getenv("SPOTIPY_CLIENT_SECRET")
        self.download_dir = os.getenv("DOWNLOAD_DIR")
        
        env_file = ".env"
        updates_needed = False

        if not self.sp_client_id or not self.sp_client_secret:
            console.print("[bold yellow]First time setup detected![/bold yellow]")
            console.print("Please enter your Spotify API credentials.")
            console.print("You can get them from: [link]https://developer.spotify.com/dashboard[/link]\n")
            
            self.sp_client_id = Prompt.ask("Enter Spotify Client ID")
            self.sp_client_secret = Prompt.ask("Enter Spotify Client Secret", password=True)
            
            set_key(env_file, "SPOTIPY_CLIENT_ID", self.sp_client_id)
            set_key(env_file, "SPOTIPY_CLIENT_SECRET", self.sp_client_secret)
            updates_needed = True

        if not self.download_dir:
            default_dir = r"C:\Musics\FLAC"
            console.print(f"\nWhere should tracks be downloaded? (Default: [cyan]{default_dir}[/cyan])")
            self.download_dir = Prompt.ask("Enter Download Directory", default=default_dir)
            
            set_key(env_file, "DOWNLOAD_DIR", self.download_dir)
            updates_needed = True
            
        if updates_needed:
            console.print(f"[green]Configuration saved to {env_file}[/green]\n")

        try:
            auth_manager = SpotifyClientCredentials(
                client_id=self.sp_client_id, 
                client_secret=self.sp_client_secret
            )
            self.sp = spotipy.Spotify(auth_manager=auth_manager)
        except Exception as e:
            console.print(f"[bold red]Error initializing Spotify client:[/bold red] {e}")
            # If auth fails, maybe prompt to reset? For now, just exit.
            exit(1)

    def _sanitize_filename(self, name):
        """Clean string for use as a filename."""
        return re.sub(r'[<>:"/\\|?*]', '', name).strip()

    async def get_direct_amazon_link_async(self, query, page):
        from urllib.parse import quote
        
        search_url = f"https://music.amazon.com/search/{quote(query)}"
        console.print(f"[cyan]Searching Amazon Music:[/cyan] {query}")
        
        try:
            # Short wait for Amazon
            await page.goto(search_url, wait_until="domcontentloaded", timeout=45000)
            
            try:
                # Pierce shadow DOM to find results
                await page.wait_for_selector('music-responsive-list-item a, music-vertical-item a, a[href*="trackAsin"]', timeout=15000)
            except:
                pass

            hrefs = await page.locator("a").evaluate_all("els => els.map(e => e.href)")
            
            for href in hrefs:
                if 'trackAsin=' in href: return href
            for href in hrefs:
                if '/tracks/' in href: return href

            return None
            
        except Exception as e:
            console.print(f"[dim red]Amazon search failed for {query}: {e}[/dim red]")
            return None

    def get_playlist_tracks(self, playlist_url):
        """Extracts Name, Artist from Spotify"""
        try:
            playlist_id = playlist_url.split("/")[-1].split("?")[0]
            console.print(f"Fetching tracks from Spotify Playlist ID: [green]{playlist_id}[/green]...")
            
            results = self.sp.playlist_items(playlist_id)
            tracks = []
            
            for item in results['items']:
                track = item['track']
                if track:
                    tracks.append({
                        "query": f"{track['artists'][0]['name']} {track['name']}",
                        "name": track['name'],
                        "artist": track['artists'][0]['name']
                    })
            return tracks
        except Exception as e:
            console.print(f"[bold red]Error accessing Spotify playlist:[/bold red] {e}")
            return []

    async def process_track_async(self, context, track_info, semaphore, index):
        """Async worker: Search Amazon -> Download Lucida."""
        # HIGHER STAGGERED START (5s per slot) to reduce initial burst load
        await asyncio.sleep(index * 5) 

        async with semaphore:
            page = None
            slot_id = f"[bold magenta]Slot {index+1}[/bold magenta]"
            try:
                page = await context.new_page()
                page.set_default_timeout(60000)
                await page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
                
                console.print(f"\n{slot_id} [cyan]Processing:[/cyan] {track_info['name']}")
                
                # RETRY LOOP FOR SEARCH
                amazon_url = None
                for attempt in range(3):
                    if attempt > 0:
                        console.print(f"{slot_id} [yellow]Retrying Search (Attempt {attempt+1})...[/yellow]")
                    
                    amazon_url = await self.get_direct_amazon_link_async(track_info['query'], page)
                    if amazon_url:
                        break
                    await asyncio.sleep(2)

                if not amazon_url:
                    console.print(f"{slot_id} [red]Skipping {track_info['name']}: Link not found after 3 tries.[/red]")
                    return
                
                # RETRY LOOP FOR DOWNLOAD
                safe_name = self._sanitize_filename(f"{track_info['artist']} - {track_info['name']}.flac")
                output_path = os.path.join(self.download_dir, safe_name)
                
                success = False
                for attempt in range(2):
                    if attempt > 0:
                        console.print(f"{slot_id} [yellow]Retrying Download (Attempt {attempt+1})...[/yellow]")
                    
                    result = await self.client.download_track(amazon_url, output_path=output_path, page=page)
                    if result.get("success"):
                        console.print(f"{slot_id} [bold green]✓ COMPLETED:[/bold green] {safe_name}")
                        success = True
                        break
                    else:
                        console.print(f"{slot_id} [dim red]Attempt {attempt+1} failed: {result.get('error')}[/dim red]")
                        # navigate back or refresh if stuck
                        await page.goto("about:blank")
                        await asyncio.sleep(2)

                if not success:
                    console.print(f"{slot_id} [bold red]✗ PERMANENT FAILURE:[/bold red] {safe_name}")

            except Exception as e:
                console.print(f"{slot_id} [bold red]Worker Error ({track_info['name']}):[/bold red] {e}")
            finally:
                if page:
                    try:
                        await page.close()
                    except:
                        pass

    async def sync_playlist_async(self):
        while True:
            playlist_url = Prompt.ask("\nEnter Spotify Playlist URL (or 'q' to quit)")
            if playlist_url.lower() == 'q':
                break
            if "spotify.com/playlist" not in playlist_url:
                console.print("[red]Invalid URL. Please enter a valid Spotify Playlist URL.[/red]")
                continue
                
            tracks = self.get_playlist_tracks(playlist_url)
            if not tracks:
                continue
                
            user_data_dir = os.path.abspath("./lucida_session")

            async with async_playwright() as p:
                # Persistent context to keep cookies/session
                context = await p.chromium.launch_persistent_context(
                    user_data_dir,
                    headless=False,
                    accept_downloads=True,
                    args=["--disable-blink-features=AutomationControlled"]
                )
                
                console.print(f"[bold yellow]Syncing {len(tracks)} tracks (3 concurrent slots)...[/bold yellow]")
                
                # Create semaphore INSIDE the async loop
                semaphore = asyncio.Semaphore(3)
                
                # Launch tasks with staggered start
                tasks = []
                for i, track in enumerate(tracks):
                    tasks.append(self.process_track_async(context, track, semaphore, i))
                
                await asyncio.gather(*tasks)

                await context.close()
                console.print("[bold green]Playlist sync complete![/bold green]")

async def main():
    try:
        syncer = SpotifyToFlac()
        await syncer.sync_playlist_async()
    except KeyboardInterrupt:
        console.print("\n[bold red]Operation cancelled by user.[/bold red]")
    except Exception as e:
        console.print(f"\n[bold red]An unexpected error occurred: {e}[/bold red]")

if __name__ == "__main__":
    asyncio.run(main())