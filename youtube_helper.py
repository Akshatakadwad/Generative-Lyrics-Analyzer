"""
YouTube API Helper
- Finds an EMBEDDABLE YouTube video for the song (prefers official, but falls back)
- Pulls top comments
- Validates references by counting comment mentions
"""

import os
import re
from dotenv import load_dotenv
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

load_dotenv()


class YouTubeHelper:
    """
    Interface to YouTube for:
    1) finding an embeddable video (official preferred, fallback allowed)
    2) pulling top comments
    3) validating references by counting comment mentions
    """

    def __init__(self):
        api_key = os.getenv("YOUTUBE_API_KEY")
        if not api_key:
            raise ValueError("❌ No YouTube API key! Check .env file")

        self.youtube = build("youtube", "v3", developerKey=api_key)
        print("✅ YouTube API connected!")

    # ----------------------------
    # Small helpers
    # ----------------------------
    def _classify_video_type(self, title: str) -> str:
        t = (title or "").lower()
        if "official audio" in t:
            return "Official Audio"
        if "lyric" in t or "lyrics" in t:
            return "Lyric Video"
        if "live" in t:
            return "Live Performance"
        if "visualizer" in t:
            return "Visualizer"
        if "official video" in t or "music video" in t:
            return "Music Video"
        return "Most Relevant"

    def _is_good_match(self, video_title: str, artist: str, title: str) -> bool:
        """Loose match filter: tries to ensure result relates to requested artist/title."""
        vt = (video_title or "").lower()
        a = (artist or "").lower()
        s = (title or "").lower()

        # remove punctuation for safer contains checks
        vt_clean = re.sub(r"[^a-z0-9\s]", " ", vt)
        a_clean = re.sub(r"[^a-z0-9\s]", " ", a)
        s_clean = re.sub(r"[^a-z0-9\s]", " ", s)

        # basic contains check
        return (a_clean.strip() in vt_clean) or (s_clean.strip() in vt_clean)

    # ----------------------------
    # Core: Search for EMBEDDABLE
    # ----------------------------
    def search_video(self, artist: str, title: str, max_candidates: int = 10):
        """
        Search for a music-related video and return the FIRST EMBEDDABLE option.

        Returns:
        {
          "video_id": "...",
          "title": "...",
          "url": "https://www.youtube.com/watch?v=...",
          "embeddable": True,
          "video_type": "Music Video" | "Official Audio" | ...
        }
        or None
        """
        artist = (artist or "").strip()
        title = (title or "").strip()
        if not artist or not title:
            return None

        try:
            # A few query variants; we’ll try them in order
            queries = [
                f"{artist} {title} official video",
                f"{artist} {title} official",
                f"{artist} {title} lyric video",
                f"{artist} {title}",
            ]

            for q in queries:
                request = self.youtube.search().list(
                    part="snippet",
                    q=q,
                    type="video",
                    videoCategoryId="10",   # Music category
                    maxResults=max_candidates,
                    safeSearch="none",
                )
                response = request.execute()
                items = response.get("items", []) or []
                if not items:
                    continue

                # Collect candidate IDs
                candidate_ids = []
                candidate_snippets = {}
                for it in items:
                    vid = (it.get("id") or {}).get("videoId")
                    snip = it.get("snippet") or {}
                    if vid:
                        candidate_ids.append(vid)
                        candidate_snippets[vid] = snip

                if not candidate_ids:
                    continue

                # Ask YouTube for video status (this is where embeddable is known)
                details = self.youtube.videos().list(
                    part="status,snippet",
                    id=",".join(candidate_ids),
                    maxResults=min(len(candidate_ids), 50),
                ).execute()

                for v in details.get("items", []) or []:
                    vid = v.get("id")
                    status = v.get("status") or {}
                    snip = v.get("snippet") or candidate_snippets.get(vid, {}) or {}

                    embeddable = bool(status.get("embeddable"))
                    privacy = (status.get("privacyStatus") or "").lower()

                    # Must be embeddable + public
                    if not embeddable or privacy != "public":
                        continue

                    vtitle = snip.get("title") or ""
                    # Prefer a result that looks related
                    if not self._is_good_match(vtitle, artist, title):
                        # still allow if query was already very specific; but we prefer matches
                        pass

                    return {
                        "video_id": vid,
                        "title": vtitle,
                        "url": f"https://www.youtube.com/watch?v={vid}",
                        "embeddable": True,
                        "video_type": self._classify_video_type(vtitle),
                    }

            print(f"⚠️  No EMBEDDABLE video found for '{title}' by {artist}")
            return None

        except HttpError as e:
            print(f"⚠️  YouTube error (search_video): {e}")
            return None

    # ----------------------------
    # Comments
    # ----------------------------
    def get_comments(self, video_id: str, max_results: int = 50):
        """Fetch top-level comments from a YouTube video."""
        try:
            request = self.youtube.commentThreads().list(
                part="snippet",
                videoId=video_id,
                textFormat="plainText",
                maxResults=max_results,
                order="relevance",
            )
            response = request.execute()

            comments = []
            for item in response.get("items", []) or []:
                text = (
                    item.get("snippet", {})
                    .get("topLevelComment", {})
                    .get("snippet", {})
                    .get("textDisplay", "")
                )
                if text:
                    comments.append(text.lower())

            return comments

        except HttpError as e:
            if "commentsDisabled" in str(e):
                print("⚠️  Comments disabled for this video")
                return []
            print(f"⚠️  YouTube error (get_comments): {e}")
            return []

    def count_mentions(self, reference_text: str, comments: list[str]) -> int:
        """Count how many comments mention the reference (simple keyword match)."""
        if not comments or not reference_text:
            return 0

        stop_words = {"the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "of"}
        words = reference_text.lower().split()
        key_words = [w for w in words if w not in stop_words and len(w) > 3]

        if not key_words:
            return 0

        count = 0
        for comment in comments:
            if any(word in comment for word in key_words):
                count += 1
        return count

    def validate_reference(self, reference_text: str, artist: str, title: str):
        """Validate reference via YouTube comments: find embeddable video -> comments -> mention count."""
        video = self.search_video(artist, title)

        if not video:
            return {
                "validated": False,
                "confidence_boost": 0.0,
                "mention_count": 0,
                "video_url": None,
                "video_id": None,
                "video_type": None,
                "embeddable": None,
            }

        comments = self.get_comments(video["video_id"], max_results=50)
        mentions = self.count_mentions(reference_text, comments)

        if mentions >= 10:
            boost = 0.15
        elif mentions >= 5:
            boost = 0.10
        elif mentions >= 2:
            boost = 0.05
        else:
            boost = 0.0

        return {
            "validated": mentions > 0,
            "confidence_boost": boost,
            "mention_count": mentions,
            "video_url": video["url"],
            "video_id": video["video_id"],
            "video_type": video.get("video_type"),
            "embeddable": video.get("embeddable"),
        }


if __name__ == "__main__":
    print("Testing YouTube API...")
    youtube = YouTubeHelper()

    print("\n" + "=" * 60)
    print("TEST 1: Search for EMBEDDABLE video")
    print("=" * 60)
    video = youtube.search_video("Coldplay", "Yellow")
    if not video:
        print("❌ Video not found")
    else:
        print(f"✅ Found: {video['title']}")
        print(f"URL: {video['url']}")
        print(f"Type: {video['video_type']}")
        print(f"Embeddable: {video['embeddable']}")

    print("\n" + "=" * 60)
    print("TEST 2: Get comments")
    print("=" * 60)
    if video:
        comments = youtube.get_comments(video["video_id"], max_results=20)
        print(f"Retrieved {len(comments)} comments")
        if comments:
            print("First comment:", comments[0][:100], "...")

    print("\n" + "=" * 60)
    print("TEST 3: Validate reference")
    print("=" * 60)
    validation = youtube.validate_reference("look at the stars", "Coldplay", "Yellow")
    print("Validated:", validation["validated"])
    print("Mentions:", validation["mention_count"])
    print("Confidence boost:", validation["confidence_boost"])

