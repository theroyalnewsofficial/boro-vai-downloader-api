from flask import Flask, request, jsonify, send_file, Response
from flask_cors import CORS
import yt_dlp
import os
import uuid
import glob
import requests
import re

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

def get_youtube_id(url):
    patterns = [
        r'(?:youtube\.com/watch\?v=|youtu\.be/)([\w-]{11})',
        r'youtube\.com/embed/([\w-]{11})',
        r'youtube\.com/shorts/([\w-]{11})'
    ]
    for p in patterns:
        m = re.search(p, url)
        if m:
            return m.group(1)
    return None

def try_oembed_info(url):
    try:
        vid = get_youtube_id(url)
        if vid:
            oembed_url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={vid}&format=json"
            r = requests.get(oembed_url, timeout=10)
            if r.status_code == 200:
                data = r.json()
                return {
                    "title": data.get('title', 'YouTube Video'),
                    "thumbnail": f"https://img.youtube.com/vi/{vid}/maxresdefault.jpg",
                    "channel": data.get('author_name', 'YouTube Channel'),
                    "duration": 0,
                    "view_count": 0,
                    "id": vid,
                    "source": "oembed-fallback"
                }
    except Exception as e:
        print(f"oembed fallback error: {e}")
    return None

@app.route('/')
def home():
    return jsonify({
        "status": "Boro Vai Downloader API Running v8 Fixed",
        "version": "PRO v8 - Bot Bypass + Requests Fixed"
    })

@app.route('/info', methods=['POST', 'OPTIONS'])
def get_info():
    if request.method == 'OPTIONS':
        return '', 200
    try:
        data = request.get_json()
        url = data.get('url')
        if not url:
            return jsonify({"error": "URL missing"}), 400
        
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'skip_download': True,
            'extractor_args': {
                'youtube': {
                    'player_client': ['android', 'ios', 'web', 'mweb'],
                    'player_skip': ['webpage', 'configs']
                }
            },
            'nocheckcertificate': True,
            'noplaylist': True,
        }
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                return jsonify({
                    "title": info.get('title'),
                    "thumbnail": info.get('thumbnail') or f"https://img.youtube.com/vi/{info.get('id')}/maxresdefault.jpg",
                    "channel": info.get('uploader') or info.get('channel'),
                    "duration": info.get('duration'),
                    "view_count": info.get('view_count'),
                    "id": info.get('id'),
                    "source": "yt-dlp"
                })
        except Exception as yt_error:
            yt_error_str = str(yt_error)
            print(f"yt-dlp failed: {yt_error_str}")
            fallback = try_oembed_info(url)
            if fallback:
                return jsonify(fallback)
            return jsonify({"error": yt_error_str}), 500
            
    except Exception as e:
        print(f"Info Error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/download', methods=['POST', 'OPTIONS'])
def download():
    if request.method == 'OPTIONS':
        return '', 200
    try:
        data = request.get_json()
        url = data.get('url')
        quality = data.get('quality', '720')
        is_audio = data.get('is_audio', False)
        
        if not url:
            return jsonify({"error": "URL missing"}), 400

        if "youtube.com" in url or "youtu.be" in url:
            try:
                cobalt_payload = {
                    "url": url,
                    "vCodec": "h264",
                    "vQuality": "720",
                    "aFormat": "mp3" if is_audio else "best",
                    "isAudioOnly": is_audio
                }
                r = requests.post("https://api.cobalt.tools/api/json", 
                                   json=cobalt_payload, 
                                   headers={"Accept":"application/json","Content-Type":"application/json"}, 
                                   timeout=30)
                if r.status_code == 200:
                    cdata = r.json()
                    dl_url = cdata.get('url')
                    if dl_url:
                        return jsonify({"download_url": dl_url, "source": "cobalt", "is_direct": True})
            except Exception as ce:
                print(f"Cobalt failed, falling back to yt-dlp: {ce}")

        temp_id = str(uuid.uuid4())
        output_path = f'/tmp/{temp_id}'

        if is_audio:
            ydl_opts = {
                'format': 'bestaudio/best',
                'outtmpl': f'{output_path}.%(ext)s',
                'postprocessors': [{'key': 'FFmpegExtractAudio','preferredcodec': 'mp3','preferredquality': '192'}],
                'quiet': True,
                'extractor_args': {'youtube': {'player_client': ['android', 'ios']}},
                'nocheckcertificate': True,
                'noplaylist': True,
            }
        else:
            ydl_opts = {
                'format': f'bestvideo[height<={quality}]+bestaudio/best[height<={quality}]/best',
                'outtmpl': f'{output_path}.%(ext)s',
                'merge_output_format': 'mp4',
                'quiet': True,
                'extractor_args': {'youtube': {'player_client': ['android', 'ios']}},
                'nocheckcertificate': True,
                'noplaylist': True,
            }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            files = glob.glob(f'{output_path}.*')
            if not files:
                return jsonify({"error": "File not found after download"}), 500
            filepath = files[0]
            title = info.get('title', 'video')
            safe_title = "".join([c for c in title if c.isalnum() or c in (' ', '-', '_')]).strip()[:50]
            ext = filepath.split('.')[-1]
            download_name = f"{safe_title}.{ext}"
            return send_file(filepath, as_attachment=True, download_name=download_name)

    except Exception as e:
        print(f"Download Error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
