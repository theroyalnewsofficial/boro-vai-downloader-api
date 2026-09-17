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
        r'(?:youtube\.com\/watch\?v=|youtu\.be\/)([\w-]{11})',
        r'youtube\.com\/embed\/([\w-]{11})',
        r'youtube\.com\/shorts\/([\w-]{11})'
    ]
    for p in patterns:
        m = re.search(p, url)
        if m:
            return m.group(1)
    return None

def try_cobalt_info(url):
    """Try to get info via oembed + cobalt"""
    try:
        vid = get_youtube_id(url)
        if vid:
            # Get title via oembed (no bot check)
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
                    "id": vid
                }
    except Exception as e:
        print(f"Cobalt info fallback error: {e}")
    return None

def try_cobalt_download(url, quality='720', is_audio=False):
    """Use cobalt API which bypasses youtube bot detection"""
    try:
        # Use public cobalt instances - try multiple
        cobalt_instances = [
            "https://api.cobalt.tools/api/json",
            "https://co.wuk.sh/api/json",
            "https://api.aceimg.app/api/json"
        ]
        
        payload = {
            "url": url,
            "vCodec": "h264",
            "vQuality": quality if quality in ['144','240','360','480','720','1080','1440','2160','max'] else '720',
            "aFormat": "mp3" if is_audio else "best",
            "isAudioOnly": is_audio,
            "isNoTTWatermark": True,
            "isTTFullAudio": False,
            "isAudioMuted": False,
            "dubLang": False,
            "disableMetadata": False
        }
        
        for instance in cobalt_instances:
            try:
                r = requests.post(instance, json=payload, headers={
                    "Accept": "application/json",
                    "Content-Type": "application/json"
                }, timeout=30)
                if r.status_code == 200:
                    data = r.json()
                    if data.get('status') == 'redirect' or data.get('url'):
                        return data.get('url')
                    if data.get('status') == 'tunnel':
                        return data.get('url')
                    if data.get('status') == 'picker':
                        # Multiple qualities, pick first
                        picker = data.get('picker', [])
                        if picker:
                            return picker[0].get('url')
            except Exception as e:
                print(f"Cobalt instance {instance} failed: {e}")
                continue
        return None
    except Exception as e:
        print(f"Cobalt download error: {e}")
        return None

@app.route('/')
def home():
    return jsonify({
        "status": "Boro Vai Downloader API Running 🔥 v7 Cobalt Fallback",
        "version": "PRO v7 - Bot Bypass",
        "cobalt_enabled": True
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
        
        # Try yt-dlp first
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'skip_download': True,
            'extractor_args': {
                'youtube': {
                    'player_client': ['android', 'ios', 'mweb', 'web'],
                    'player_skip': ['webpage']
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
            
            # If bot detection, try cobalt/oembed fallback
            if "bot" in yt_error_str.lower() or "sign in" in yt_error_str.lower():
                fallback = try_cobalt_info(url)
                if fallback:
                    fallback["source"] = "cobalt-fallback"
                    fallback["bot_bypass"] = True
                    return jsonify(fallback)
            
            # Return bot error with helpful message but also try fallback
            fallback = try_cobalt_info(url)
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

        # First try cobalt (more reliable for youtube bot bypass)
        if "youtube.com" in url or "youtu.be" in url or "youtube" in url:
            cobalt_url = try_cobalt_download(url, quality, is_audio)
            if cobalt_url:
                # Return redirect URL for frontend to download directly
                return jsonify({
                    "download_url": cobalt_url,
                    "source": "cobalt",
                    "is_direct": True
                })

        # Fallback to yt-dlp download
        temp_id = str(uuid.uuid4())
        output_path = f'/tmp/{temp_id}'

        if is_audio:
            ydl_opts = {
                'format': 'bestaudio/best',
                'outtmpl': f'{output_path}.%(ext)s',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
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

@app.route('/direct', methods=['GET'])
def direct_proxy():
    """Proxy download to avoid CORS issues"""
    try:
        file_url = request.args.get('url')
        if not file_url:
            return jsonify({"error": "url param missing"}), 400
        r = requests.get(file_url, stream=True, timeout=60)
        headers = {
            'Content-Disposition': f'attachment; filename="BoroVai-{uuid.uuid4()}.mp4"'
        }
        return Response(r.iter_content(chunk_size=8192), content_type=r.headers.get('content-type', 'video/mp4'), headers=headers)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
