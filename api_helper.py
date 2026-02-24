"""
API Helper for Genius 
"""

import os
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
import re

load_dotenv()

class GeniusHelper:
    
    def __init__(self):
        self.token = os.getenv('GENIUS_ACCESS_TOKEN')
        
        if not self.token:
            print("⚠️  No Genius token found")
        else:
            print("✅ Genius API connected!")
        
        self.base_url = "https://api.genius.com"
        self.headers = {
            'Authorization': f'Bearer {self.token}' if self.token else ''
        }
    
    def get_song(self, artist, title):
        print(f"🎵 Searching for: {title} by {artist}")
        
        try:
            if self.token:
                song_info = self._api_search(artist, title)
                if song_info:
                    return song_info
            
            print("📝 Trying direct URL method...")
            song_info = self._direct_search(artist, title)
            return song_info
            
        except Exception as e:
            print(f"❌ Error: {str(e)}")
            return None
    
    def _api_search(self, artist, title):
        try:
            search_url = f"{self.base_url}/search"
            params = {'q': f"{title} {artist}"}
            
            response = requests.get(search_url, headers=self.headers, params=params)
            
            if response.status_code != 200:
                print(f"⚠️  API returned {response.status_code}")
                return None
            
            data = response.json()
            
            if not data.get('response', {}).get('hits'):
                return None
            
            song_url = data['response']['hits'][0]['result']['url']
            lyrics = self._scrape_lyrics(song_url)
            
            if not lyrics or len(lyrics) < 100:
                return None
            
            return {
                'title': data['response']['hits'][0]['result']['title'],
                'artist': data['response']['hits'][0]['result']['primary_artist']['name'],
                'lyrics': lyrics,
                'release_date': 'Unknown',
                'album': 'Unknown',
                'url': song_url
            }
            
        except Exception as e:
            print(f"⚠️  API failed: {e}")
            return None
    
    def _direct_search(self, artist, title):
        artist_clean = artist.lower().replace(' ', '-').replace('.', '').replace("'", '')
        title_clean = title.lower().replace(' ', '-').replace('.', '').replace("'", '')
        
        url_patterns = [
            f"https://genius.com/{artist_clean}-{title_clean}-lyrics",
            f"https://genius.com/{title_clean}-{artist_clean}-lyrics",
        ]
        
        for url in url_patterns:
            print(f"🔗 Trying: {url}")
            try:
                lyrics = self._scrape_lyrics(url)
                if lyrics and len(lyrics) > 100:
                    print(f"✅ Found lyrics!")
                    return {
                        'title': title,
                        'artist': artist,
                        'lyrics': lyrics,
                        'release_date': 'Unknown',
                        'album': 'Unknown',
                        'url': url
                    }
            except Exception as ex:
                continue
        
        return None
    
    def _scrape_lyrics(self, url):
        """
        Scrape lyrics 
        """
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
            }
            
            response = requests.get(url, headers=headers)
            
            if response.status_code != 200:
                return None
            
            # Parse HTML
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Remove script, style, header, footer
            for unwanted in soup.find_all(['script', 'style', 'header', 'footer', 'nav']):
                unwanted.decompose()
            
            # Strategy 1: Find divs with data-lyrics-container attribute
            lyrics_divs = soup.find_all('div', {'data-lyrics-container': 'true'})
            
            # Strategy 2: Find by class name pattern
            if not lyrics_divs:
                lyrics_divs = soup.find_all('div', class_=re.compile('Lyrics__Container'))
            
            # Strategy 3: Find container with specific structure
            if not lyrics_divs:
                container = soup.find('div', class_=re.compile('lyrics'))
                if container:
                    lyrics_divs = [container]
            
            if not lyrics_divs:
                return None
            
            # Extract text from all lyrics divs
            all_text = []
            for div in lyrics_divs:
                text = div.get_text(separator='\n', strip=True)
                all_text.append(text)
            
            combined_text = '\n\n'.join(all_text)
            
            # CRITICAL: Clean out metadata
            # Split into lines
            lines = combined_text.split('\n')
            
            # Filter out metadata lines
            clean_lines = []
            skip_next = False
            
            for line in lines:
                line_stripped = line.strip()
                line_lower = line_stripped.lower()
                
                # Skip empty lines
                if not line_stripped:
                    continue
                
                # Skip metadata keywords
                metadata_keywords = [
                    'contributor', 'translation', 'embed', 'you might also like',
                    'see live', 'get tickets', 'русский', 'türkçe', 'español',
                    'português', 'polski', 'deutsch', 'français', 'العربية',
                    'azərbaycan', 'ironically', 'braggadocious', 'kendrick lamar',
                    'challenges his competition', 'lyrics', 'on the'
                ]
                
                # Check if line contains metadata
                if any(keyword in line_lower for keyword in metadata_keywords):
                    continue
                
                # Skip lines that are just numbers (contributor counts)
                if re.match(r'^\d+\s*(contributor|translation)?s?$', line_lower):
                    continue
                
                # Skip very short lines that look like metadata
                if len(line_stripped) < 3:
                    continue
                
                clean_lines.append(line_stripped)
            
            # Join cleaned lines
            cleaned_lyrics = '\n'.join(clean_lines)
            
            # Final validation
            if len(cleaned_lyrics) < 100:
                return None
            
            # Additional check: if it still starts with numbers or metadata
            first_line = cleaned_lyrics.split('\n')[0] if cleaned_lyrics else ''
            if re.match(r'^\d+', first_line):
                # Remove first line
                cleaned_lyrics = '\n'.join(cleaned_lyrics.split('\n')[1:])
            
            return cleaned_lyrics
            
        except Exception as e:
            print(f"⚠️  Scraping failed: {e}")
            return None


if __name__ == "__main__":
    print("Testing Genius API...")
    print("="*60)
    
    helper = GeniusHelper()
    
    song_data = helper.get_song("Kendrick Lamar", "HUMBLE")
    
    if song_data:
        print("\n" + "="*60)
        print("📊 SUCCESS!")
        print("="*60)
        print(f"Title: {song_data['title']}")
        print(f"Artist: {song_data['artist']}")
        print(f"\nLyrics (first 300 chars):")
        print("-"*60)
        print(song_data['lyrics'][:300])
        print("-"*60)
        print(f"\nTotal lyrics length: {len(song_data['lyrics'])} characters")
    else:
        print("\n❌ Failed to get song")
