from flask import Flask, request, jsonify
import requests
import instaloader
import re
import os
from urllib.parse import urlparse

app = Flask(__name__)

FB_API = "https://serverless-tooly-gateway-6n4h522y.ue.gateway.dev/facebook/video"

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

try:
    L = instaloader.Instaloader(
        download_pictures=False,
        download_videos=False,
        download_video_thumbnails=False,
        save_metadata=False,
        compress_json=False
    )
except Exception:
    L = None


@app.after_request
def add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    response.headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
    return response


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


@app.route("/favicon.ico")
def favicon():
    return "", 204


@app.route("/insta")
def insta():
    url = request.args.get("url")

    if not url:
        return jsonify({
            "success": False,
            "message": "Missing Instagram URL"
        }), 400

    if L is None:
        return jsonify({
            "success": False,
            "message": "Instaloader initialization failed"
        }), 500

    try:
        url = url.split("?")[0]

        match = re.search(
            r"(?:reel|p|tv)/([^/?]+)",
            url
        )

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


@app.route("/fb")
def fb():
    url = request.args.get("url")

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


@app.route("/pin")
def pin():
    url = request.args.get("url")

    if not url:
        return jsonify({
            "success": False,
            "message": "Missing Pinterest URL"
        }), 400

    try:
        parsed = urlparse(url)

        if not any(domain in parsed.netloc for domain in ["pinterest.com", "pin.it"]):
            return jsonify({
                "success": False,
                "message": "Invalid Pinterest URL"
            }), 400

        response = requests.get(
            url,
            headers=HEADERS,
            timeout=20
        )

        response.raise_for_status()

        html = response.text

        images = list(set(re.findall(
            r"https://i\.pinimg\.com/[^\s'\"<>]+?\.(?:jpg|jpeg|png|webp)",
            html
        )))

        videos = list(set(re.findall(
            r"https://(?:v|v1|i)\.pinimg\.com/[^\s'\"<>]+?\.mp4",
            html
        )))

        return jsonify({
            "success": True,
            "platform": "pinterest",
            "images": images,
            "videos": videos
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "platform": "pinterest",
            "error": str(e)
        }), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port)
