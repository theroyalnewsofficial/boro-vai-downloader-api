from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import yt_dlp
import os
import uuid
import glob

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

@app.route('/')
def home():
    return jsonify({
        "status": "Boro Vai Downloader API Running 🔥",
        "version": "PRO v5 - Final",
        "endpoints": ["/info", "/download"]
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
        
        ydl_opts = {'quiet': True, 'no_warnings': True, 'skip_download': True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return jsonify({
                "title": info.get('title'),
                "thumbnail": info.get('thumbnail'),
                "channel": info.get('uploader'),
                "duration": info.get('duration'),
                "view_count": info.get('view_count')
            })
    except Exception as e:
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
                'quiet': True
            }
        else:
            # For video
            ydl_opts = {
                'format': f'bestvideo[height<={quality}]+bestaudio/best[height<={quality}]/best',
                'outtmpl': f'{output_path}.%(ext)s',
                'merge_output_format': 'mp4',
                'quiet': True
            }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            
            # Find downloaded file
            files = glob.glob(f'{output_path}.*')
            if not files:
                return jsonify({"error": "File not found after download"}), 500
            
            filepath = files[0]
            title = info.get('title', 'video')
            # Clean title for filename
            safe_title = "".join([c for c in title if c.isalnum() or c in (' ', '-', '_')]).strip()[:50]
            ext = filepath.split('.')[-1]
            download_name = f"{safe_title}.{ext}"
            
            return send_file(filepath, as_attachment=True, download_name=download_name)

    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
