from flask import Flask, render_template, request, jsonify
from detector import ReferenceDetector
from api_helper import GeniusHelper
import time

app = Flask(__name__)

import os
print("✅ app.root_path =", app.root_path)
print("✅ templates folder =", app.template_folder)
print("✅ resolved templates path =", os.path.join(app.root_path, app.template_folder))
print("✅ index.html exists? =", os.path.exists(os.path.join(app.root_path, app.template_folder, "index.html")))


@app.after_request
def add_no_cache_headers(resp):
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"
    return resp


print("🚀 Starting Music Reference Analyzer...")
detector = ReferenceDetector(max_refs=5, model="qwen2.5:7b")
genius = GeniusHelper()
print("✅ System ready!")


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/analyze", methods=["POST"])
def analyze():
    try:
        data = request.json or {}
        artist = (data.get("artist") or "").strip()
        title = (data.get("title") or "").strip()

        print("\n" + "="*60)
        print(f"🎵 /analyze request: {title} by {artist}")
        print("="*60)

        if not artist or not title:
            return jsonify({"error": "Please provide both artist and song title"}), 400

        start_time = time.time()

        song_data = genius.get_song(artist, title)
        
        print("==== DEBUG LYRICS START ====")
        print((song_data.get("lyrics") or "")[:500])
        print("==== DEBUG LYRICS END ====")


        # 🔎 DEBUG: Check what Genius returned
        print("\n" + "="*60)
        print("🎼 Genius Debug")
        print("="*60)

        if song_data:
            print("DEBUG genius.get_song keys:", list(song_data.keys()))
            print("DEBUG genius title/artist:",
                  song_data.get("title"), "/", song_data.get("artist"))
            print("DEBUG lyrics length:",
                  len(song_data.get("lyrics", "")))
        else:
            print("DEBUG genius returned: None")
        
        if not song_data or not song_data.get("lyrics"):
            return jsonify({"error": f'Could not find "{title}" by {artist}'}), 404

        
        result = detector.analyze_song(song_data["lyrics"], song_data)

        processing_time_ms = int((time.time() - start_time) * 1000)

        youtube_video_url = None
        youtube_video_id = None
        youtube_video_type = None
        youtube_embeddable = None

        yt = result.get("youtube")
        if isinstance(yt, dict):
            youtube_video_url = yt.get("video_url")
            youtube_video_id = yt.get("video_id")
            youtube_video_type = yt.get("video_type")
            youtube_embeddable = yt.get("embeddable") 

        response = {
            "success": True,
            "song": {
                "title": song_data.get("title"),
                "artist": song_data.get("artist"),
                "album": song_data.get("album"),
                "release_date": song_data.get("release_date"),
            },
            "analysis": {
                "sections_count": len(result.get("sections", [])),
                "processing_time_ms": processing_time_ms,
                "song_summary": result.get("song_summary"),
                "youtube_video_id": youtube_video_id,
                "youtube_video_url": youtube_video_url,
                "youtube_video_type": (yt.get("video_type") if isinstance(yt, dict) else None),
            },
            "sections": result.get("sections", []),
        }

        return jsonify(response)

    except Exception as e:
        print("❌ Error:", str(e))
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    print("\n🌐 Starting web server...")
    print("📍 Open: http://localhost:5000")
    print("🛑 Ctrl+C to stop\n")
    app.run(debug=True, host="127.0.0.1", port=5000)

