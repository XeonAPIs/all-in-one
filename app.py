from flask import Flask, request, jsonify
import requests
import instaloader
import re
from urllib.parse import urlparse

app = Flask(__name__)

# =========================
# CONFIG
# =========================

FB_API = "https://serverless-tooly-gateway-6n4h522y.ue.gateway.dev/facebook/video"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

IGNORE_LINKS = {
    "https://i.pinimg.com/originals/d5/3b/01/d53b014d86a6b6761bf649a0ed813c2b.png"
}

L = instaloader.Instaloader(
    download_pictures=False,
    download_videos=False,
    download_video_thumbnails=False,
    save_metadata=False,
    compress_json=False
)


# =========================
# CORS
# =========================

@app.after_request
def add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    response.headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
    return response


@app.route("/favicon.ico")
def favicon():
    return "", 204


# =========================
# HOME
# =========================

@app.route("/")
def home():
    return jsonify({
        "success": True,
        "owner": "Xeon Vro",
        "apis": {
            "instagram": "/insta?url=",
            "facebook": "/fb?url=",
            "pinterest": "/pin?url="
        }
    })


# =========================
# INSTAGRAM
# =========================

@app.route("/insta")
def insta():
    url = request.args.get("url", "").strip()

    if not url:
        return jsonify({
            "success": False,
            "message": "Missing Instagram URL"
        }), 400

    try:
        url = url.split("?")[0]

        match = re.search(r"(?:reel|p|tv)/([^/?]+)", url)

        if not match:
            return jsonify({
                "success": False,
                "message": "Invalid Instagram URL"
            }), 400

        shortcode = match.group(1)

        post = instaloader.Post.from_shortcode(
            L.context,
            shortcode
        )

        return jsonify({
            "success": True,
            "platform": "instagram",
            "type": "video" if post.is_video else "image",
            "media": post.video_url if post.is_video else post.url
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "platform": "instagram",
            "error": str(e)
        }), 500


# =========================
# FACEBOOK
# =========================

@app.route("/fb")
def fb():
    url = request.args.get("url", "").strip()

    if not url:
        return jsonify({
            "success": False,
            "message": "Missing Facebook URL"
        }), 400

    try:
        response = requests.get(
            FB_API,
            params={"url": url},
            timeout=30
        )

        response.raise_for_status()

        data = response.json()

        return jsonify({
            "success": data.get("success", False),
            "platform": "facebook",
            "title": data.get("title"),
            "videos": data.get("videos", {})
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "platform": "facebook",
            "error": str(e)
        }), 500


# =========================
# PINTEREST
# =========================

@app.route("/pin")
def pin():
    url = request.args.get("url", "").strip()

    if not url:
        return jsonify({
            "success": False,
            "message": "Missing Pinterest URL"
        }), 400

    parsed = urlparse(url)

    if not any(domain in parsed.netloc for domain in ["pinterest.com", "pin.it"]):
        return jsonify({
            "success": False,
            "message": "Invalid Pinterest URL"
        }), 400

    try:
        response = requests.get(
            url,
            headers=HEADERS,
            timeout=15
        )

        response.raise_for_status()

        html = response.text

        images = re.findall(
            r"https://i\.pinimg\.com/[^\s'\"<>]+?\.(?:jpg|png|webp)",
            html
        )

        images = [
            img for img in set(images)
            if img not in IGNORE_LINKS
        ]

        videos = re.findall(
            r"https://(?:v|v1|i)\.pinimg\.com/[^\s'\"<>]+?\.mp4",
            html
        )

        return jsonify({
            "success": True,
            "platform": "pinterest",
            "images": sorted(set(images)),
            "videos": sorted(set(videos))
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "platform": "pinterest",
            "error": str(e)
        }), 500


# =========================
# START
# =========================

if __name__ == "__main__":
    import os

    port = int(os.environ.get("PORT", 5000))
    app.run(
        host="0.0.0.0",
        port=port
    )
