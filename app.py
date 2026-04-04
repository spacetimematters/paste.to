import os
import uuid
import glob
import mimetypes
from flask import Flask, render_template, request, jsonify, send_file
from yt_dlp import YoutubeDL

app = Flask(__name__)

DOWNLOAD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "downloads")
os.makedirs(DOWNLOAD_DIR, exist_ok=True)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/download", methods=["POST"])
def download():
    data = request.get_json()
    url = data.get("url", "").strip()
    mode = data.get("mode", "video")  # "video" or "thumbnail"

    if not url:
        return jsonify({"error": "No URL provided"}), 400

    task_id = uuid.uuid4().hex[:12]
    task_dir = os.path.join(DOWNLOAD_DIR, task_id)
    os.makedirs(task_dir, exist_ok=True)

    try:
        if mode == "thumbnail":
            ydl_opts = {
                "skip_download": True,
                "writethumbnail": True,
                "outtmpl": os.path.join(task_dir, "%(title).80s.%(ext)s"),
                "quiet": True,
                "no_warnings": True,
            }
        else:
            ydl_opts = {
                "format": "best[ext=mp4]/best",
                "outtmpl": os.path.join(task_dir, "%(title).80s.%(ext)s"),
                "quiet": True,
                "no_warnings": True,
                "merge_output_format": "mp4",
            }

        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            title = info.get("title", "download")

        # Find the downloaded file
        files = glob.glob(os.path.join(task_dir, "*"))
        if not files:
            return jsonify({"error": "Download failed — no file produced"}), 500

        filename = os.path.basename(files[0])
        return jsonify({
            "success": True,
            "title": title,
            "filename": filename,
            "task_id": task_id,
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/file/<task_id>/<filename>")
def serve_file(task_id, filename):
    # Sanitize to prevent path traversal
    safe_task_id = os.path.basename(task_id)
    safe_filename = os.path.basename(filename)
    filepath = os.path.join(DOWNLOAD_DIR, safe_task_id, safe_filename)

    if not os.path.isfile(filepath):
        return "Not found", 404

    mimetype = mimetypes.guess_type(filepath)[0] or "application/octet-stream"
    return send_file(filepath, as_attachment=True, download_name=safe_filename, mimetype=mimetype)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
