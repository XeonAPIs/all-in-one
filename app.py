from flask import Flask, request, jsonify
from playwright.sync_api import sync_playwright
import requests
import re
import os
import json
from urllib.parse import urlparse

app = Flask(__name__)

FB_API = "https://serverless-tooly-gateway-6n4h522y.ue.gateway.dev/facebook/video"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
}


def load_playwright_cookies(context):
    try:

        if not os.path.exists("cookies.txt"):
            return

        with open("cookies.txt", "r", encoding="utf-8") as f:
            cookies = json.load(f)

        if isinstance(cookies, list):
            context.add_cookies(cookies)

    except Exception as e:
        print("Cookie load error:", str(e))


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


# =========================
# Instagram Downloader
# =========================
@app.route("/insta")
def insta():

    url = request.args.get("url")

    if not url:
        return jsonify({
            "status": False,
            "owner": "Xeon Vro",
            "message": "No URL provided"
        }), 400

    try:

        with sync_playwright() as p:

            browser = p.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-dev-shm-usage"
                ]
            )

            context = browser.new_context(
                user_agent=HEADERS["User-Agent"]
            )

            load_playwright_cookies(context)

            page = context.new_page()

            page.goto(
                url,
                wait_until="networkidle",
                timeout=60000
            )

            page.wait_for_timeout(3000)

            html = page.content()

            media = []

            video_matches = set()

            for pattern in [
                r'"video_url":"([^"]+)"',
                r'https:\\/\\/[^"]+\.mp4[^"]*'
            ]:
                video_matches.update(re.findall(pattern, html))

            image_matches = set()

            for pattern in [
                r'"display_url":"([^"]+)"',
                r'https:\\/\\/[^"]+\.(?:jpg|jpeg|webp)[^"]*'
            ]:
                image_matches.update(re.findall(pattern, html))

            for video in video_matches:

                video = video.replace("\\u0026", "&")
                video = video.replace("\\/", "/")

                media.append({
                    "type": "video",
                    "url": video
                })

            for image in image_matches:

                image = image.replace("\\u0026", "&")
                image = image.replace("\\/", "/")

                media.append({
                    "type": "image",
                    "url": image
                })

            browser.close()

            if not media:
                return jsonify({
                    "status": False,
                    "owner": "Xeon Vro",
                    "platform": "instagram",
                    "error": "No media found"
                }), 404

            return jsonify({
                "status": True,
                "owner": "Xeon Vro",
                "platform": "instagram",
                "media": media
            })

    except Exception as e:

        return jsonify({
            "status": False,
            "owner": "Xeon Vro",
            "platform": "instagram",
            "error": str(e)
        }), 500


# =========================
# Facebook Downloader
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
# Pinterest Downloader
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

        if not any(domain in parsed.netloc for domain in ["pinterest.com", "pin.it"]):
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
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port)
