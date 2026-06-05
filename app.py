from flask import Flask, request, jsonify
import requests
import re
import os
import json
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright

app = Flask(__name__)

FB_API = "https://serverless-tooly-gateway-6n4h522y.ue.gateway.dev/facebook/video"

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}


def load_cookies_from_file(path="cookies.txt"):
    """Parse Netscape-format cookies.txt into Playwright cookie dicts."""
    cookies = []
    if not os.path.exists(path):
        return cookies
    with open(path, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split("\t")
            if len(parts) < 7:
                continue
            domain, _, path_, secure, expires, name, value = parts[:7]
            cookies.append({
                "name": name,
                "value": value,
                "domain": domain.lstrip("."),
                "path": path_,
                "secure": secure.upper() == "TRUE",
                "sameSite": "Lax"
            })
    return cookies


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
        url = url.split("?")[0]

        match = re.search(r"(?:reel|p|tv)/([^/?]+)", url)
        if not match:
            return jsonify({
                "status": False,
                "owner": "Xeon Vro",
                "message": "Invalid Instagram URL"
            }), 400

        cookies = load_cookies_from_file("cookies.txt")

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                           "AppleWebKit/537.36 (KHTML, like Gecko) "
                           "Chrome/124.0.0.0 Safari/537.36"
            )

            if cookies:
                context.add_cookies([
                    {**c, "domain": "instagram.com"} for c in cookies
                ])

            page = context.new_page()

            media_urls = {"video": [], "image": []}

            def handle_response(response):
                ct = response.headers.get("content-type", "")
                resp_url = response.url
                if "video" in ct or resp_url.endswith(".mp4"):
                    media_urls["video"].append(resp_url)
                elif "instagram.com" in resp_url and re.search(
                    r"\.(jpg|jpeg|png|webp)", resp_url
                ):
                    media_urls["image"].append(resp_url)

            page.on("response", handle_response)
            page.goto(url, wait_until="networkidle", timeout=30000)
            page.wait_for_timeout(3000)

            # Also scrape HTML for media links
            html = page.content()

            browser.close()

        # Try video first, then image
        if media_urls["video"]:
            return jsonify({
                "status": True,
                "owner": "Xeon Vro",
                "platform": "instagram",
                "type": "video",
                "media": media_urls["video"][0]
            })

        # Fallback: parse HTML for image
        images = re.findall(
            r'https://[^"\'<>\s]+\.(?:jpg|jpeg|png|webp)[^"\'<>\s]*',
            html
        )
        images = [i for i in images if "instagram" in i or "cdninstagram" in i]

        if images:
            return jsonify({
                "status": True,
                "owner": "Xeon Vro",
                "platform": "instagram",
                "type": "image",
                "media": images[0]
            })

        return jsonify({
            "status": False,
            "owner": "Xeon Vro",
            "platform": "instagram",
            "message": "Could not extract media. Check cookies or URL."
        }), 500

    except Exception as e:
        return jsonify({
            "status": False,
            "owner": "Xeon Vro",
            "platform": "instagram",
            "error": str(e)
        }), 500


# =========================
# Facebook Downloader  ← UNCHANGED
# =========================
@app.route("/fb")
def fb():
    url = request.args.get("url")
    if not url:
        return jsonify({"status": False, "message": "Missing Facebook URL"}), 400
    try:
        response = requests.get(FB_API, params={"url": url}, timeout=30)
        response.raise_for_status()
        data = response.json()
        return jsonify({
            "status": data.get("success", False),
            "platform": "facebook",
            "title": data.get("title"),
            "videos": data.get("videos", {})
        })
    except Exception as e:
        return jsonify({"status": False, "platform": "facebook", "error": str(e)}), 500


# =========================
# Pinterest Downloader  ← UNCHANGED
# =========================
@app.route("/pin")
def pin():
    url = request.args.get("url")
    if not url:
        return jsonify({"status": False, "message": "Missing Pinterest URL"}), 400
    try:
        parsed = urlparse(url)
        if not any(domain in parsed.netloc for domain in ["pinterest.com", "pin.it"]):
            return jsonify({"status": False, "message": "Invalid Pinterest URL"}), 400
        response = requests.get(url, headers=HEADERS, timeout=20)
        response.raise_for_status()
        html = response.text
        images = list(set(re.findall(
            r"https://i\.pinimg\.com/[^\s'\"<>]+?\.(?:jpg|jpeg|png|webp)", html
        )))
        videos = list(set(re.findall(
            r"https://(?:v|v1|i)\.pinimg\.com/[^\s'\"<>]+?\.mp4", html
        )))
        return jsonify({"status": True, "platform": "pinterest", "images": images, "videos": videos})
    except Exception as e:
        return jsonify({"status": False, "platform": "pinterest", "error": str(e)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port)
