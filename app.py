from flask import Flask, request, jsonify
import requests
import re
from urllib.parse import urlparse

app = Flask(__name__)

FB_API = "https://serverless-tooly-gateway-6n4h522y.ue.gateway.dev/facebook/video"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
}


@app.after_request
def cors(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "*"
    return response


@app.route("/")
def home():
    return jsonify({
        "status": True,
        "owner": "Xeon Vro",
        "apis": {
            "instagram": "/insta?url=",
            "facebook": "/fb?url=",
            "pinterest": "/pin?url="
        }
    })


# =========================
# Instagram (Redvid)
# =========================

@app.route("/insta")
def insta():
    url = request.args.get("url")

    if not url:
        return jsonify({
            "status": False,
            "platform": "instagram",
            "message": "Missing Instagram URL"
        }), 400

    try:
        response = requests.post(
            "https://redvid.io/fetch",
            data={
                "url": url,
                "lang": "en"
            },
            headers={
                **HEADERS,
                "Origin": "https://redvid.io",
                "Referer": "https://redvid.io/",
                "X-Requested-With": "XMLHttpRequest"
            },
            timeout=30
        )

        response.raise_for_status()

        data = response.json()

        if not data.get("success"):
            return jsonify({
                "status": False,
                "platform": "instagram",
                "message": "Failed to fetch media"
            }), 500

        view = data.get("view", "")

        video_links = re.findall(
            r'href="([^"]+\.mp4[^"]*)"',
            view,
            re.I
        )

        image_links = re.findall(
            r'https://[^"\']+\.(?:jpg|jpeg|png|webp)',
            view,
            re.I
        )

        if video_links:
            return jsonify({
                "status": True,
                "owner": "Xeon Vro",
                "platform": "instagram",
                "type": "video",
                "media": video_links[0]
            })

        if image_links:
            return jsonify({
                "status": True,
                "owner": "Xeon Vro",
                "platform": "instagram",
                "type": "image",
                "media": image_links[0]
            })

        return jsonify({
            "status": True,
            "platform": "instagram",
            "raw": data
        })

    except Exception as e:
        return jsonify({
            "status": False,
            "platform": "instagram",
            "error": str(e)
        }), 500


# =========================
# Facebook
# =========================

@app.route("/fb")
def fb():
    url = request.args.get("url")

    if not url:
        return jsonify({
            "status": False,
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
            "status": data.get("success", False),
            "platform": "facebook",
            "title": data.get("title"),
            "videos": data.get("videos", {})
        })

    except Exception as e:
        return jsonify({
            "status": False,
            "platform": "facebook",
            "error": str(e)
        }), 500


# =========================
# Pinterest
# =========================

@app.route("/pin")
def pin():
    url = request.args.get("url")

    if not url:
        return jsonify({
            "status": False,
            "message": "Missing Pinterest URL"
        }), 400

    try:
        parsed = urlparse(url)

        if not any(
            domain in parsed.netloc
            for domain in ["pinterest.com", "pin.it"]
        ):
            return jsonify({
                "status": False,
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
            "status": True,
            "platform": "pinterest",
            "images": images,
            "videos": videos
        })

    except Exception as e:
        return jsonify({
            "status": False,
            "platform": "pinterest",
            "error": str(e)
        }), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
