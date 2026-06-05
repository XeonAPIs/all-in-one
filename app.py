from flask import Flask, request, jsonify
import requests
import re
from urllib.parse import urlparse

app = Flask(__name__)

FB_API = "https://serverless-tooly-gateway-6n4h522y.ue.gateway.dev/facebook/video"

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}


@app.after_request
def add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    response.headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
    return response


@app.route("/")
def home():
    return jsonify({
        "status": True,
        "owner": "Xeon Vro"
    })


# =========================
# Instagram
# =========================

@app.route("/insta")
def insta():
    url = request.args.get("url")

    if not url:
        return jsonify({
            "status": False,
            "owner": "Xeon Vro"
        }), 400

    try:
        response = requests.post(
            "https://redvid.io/fetch",
            data={
                "url": url,
                "lang": "en"
            },
            headers={
                "User-Agent": HEADERS["User-Agent"],
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
                "owner": "Xeon Vro"
            }), 500

        view = data.get("view", "")

        if 'class="download-video"' in view:
            return jsonify({
                "status": True,
                "owner": "Xeon Vro",
                "type": "video"
            })

        if "thumbnail-image" in view:
            return jsonify({
                "status": True,
                "owner": "Xeon Vro",
                "type": "image"
            })

        return jsonify({
            "status": False,
            "owner": "Xeon Vro"
        }), 404

    except Exception:
        return jsonify({
            "status": False,
            "owner": "Xeon Vro"
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
            "owner": "Xeon Vro"
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
            "owner": "Xeon Vro",
            "type": "video"
        })

    except Exception:
        return jsonify({
            "status": False,
            "owner": "Xeon Vro"
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
            "owner": "Xeon Vro"
        }), 400

    try:
        parsed = urlparse(url)

        if not any(
            domain in parsed.netloc
            for domain in ["pinterest.com", "pin.it"]
        ):
            return jsonify({
                "status": False,
                "owner": "Xeon Vro"
            }), 400

        response = requests.get(
            url,
            headers=HEADERS,
            timeout=20
        )

        response.raise_for_status()

        html = response.text

        images = re.findall(
            r"https://i\.pinimg\.com/[^\s'\"<>]+?\.(?:jpg|jpeg|png|webp)",
            html
        )

        videos = re.findall(
            r"https://(?:v|v1|i)\.pinimg\.com/[^\s'\"<>]+?\.mp4",
            html
        )

        media_type = "video" if videos else "image"

        return jsonify({
            "status": True,
            "owner": "Xeon Vro",
            "type": media_type
        })

    except Exception:
        return jsonify({
            "status": False,
            "owner": "Xeon Vro"
        }), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
