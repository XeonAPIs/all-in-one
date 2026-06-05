from flask import Flask, request, jsonify
import requests
import re
import os
import json
from urllib.parse import urlparse
from http.cookiejar import MozillaCookieJar

app = Flask(__name__)

FB_API = "https://serverless-tooly-gateway-6n4h522y.ue.gateway.dev/facebook/video"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/124.0.0.0 Safari/537.36",
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.instagram.com/",
    "x-ig-app-id": "936619743392459",
}


def get_insta_session():
    """Build a requests session loaded with cookies.txt."""
    session = requests.Session()
    session.headers.update(HEADERS)
    cookie_file = "cookies.txt"
    if os.path.exists(cookie_file):
        jar = MozillaCookieJar(cookie_file)
        jar.load(ignore_discard=True, ignore_expires=True)
        session.cookies = jar
    return session


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
        url = url.split("?")[0].rstrip("/")

        match = re.search(r"(?:reel|p|tv)/([^/?]+)", url)
        if not match:
            return jsonify({
                "status": False,
                "owner": "Xeon Vro",
                "message": "Invalid Instagram URL"
            }), 400

        shortcode = match.group(1)
        session = get_insta_session()

        # Use Instagram's GQL API — works with valid session cookies
        api_url = (
            f"https://www.instagram.com/api/v1/media/"
            f"{shortcode_to_media_id(shortcode)}/info/"
        )

        resp = session.get(api_url, timeout=15)

        # Fallback to /graphql if media ID conversion fails
        if resp.status_code != 200:
            gql_url = (
                "https://www.instagram.com/graphql/query/"
                f"?query_hash=b3055c01b4b222b8a47dc12b090e4e64"
                f"&variables=%7B%22shortcode%22%3A%22{shortcode}%22%7D"
            )
            resp = session.get(gql_url, timeout=15)

        if resp.status_code == 401:
            return jsonify({
                "status": False,
                "owner": "Xeon Vro",
                "platform": "instagram",
                "message": "Cookies expired or invalid. Please update cookies.txt."
            }), 401

        if resp.status_code != 200:
            # Last fallback: scrape the page HTML directly
            return _scrape_insta_html(session, url, shortcode)

        data = resp.json()

        # Parse GQL response
        try:
            media = data["data"]["shortcode_media"]
            if media.get("is_video"):
                return jsonify({
                    "status": True,
                    "owner": "Xeon Vro",
                    "platform": "instagram",
                    "type": "video",
                    "media": media["video_url"]
                })
            else:
                return jsonify({
                    "status": True,
                    "owner": "Xeon Vro",
                    "platform": "instagram",
                    "type": "image",
                    "media": media["display_url"]
                })
        except (KeyError, TypeError):
            pass

        # Parse /api/v1/media/info/ response
        try:
            item = data["items"][0]
            if "video_versions" in item:
                return jsonify({
                    "status": True,
                    "owner": "Xeon Vro",
                    "platform": "instagram",
                    "type": "video",
                    "media": item["video_versions"][0]["url"]
                })
            else:
                candidates = item.get("image_versions2", {}).get("candidates", [])
                if candidates:
                    return jsonify({
                        "status": True,
                        "owner": "Xeon Vro",
                        "platform": "instagram",
                        "type": "image",
                        "media": candidates[0]["url"]
                    })
        except (KeyError, IndexError, TypeError):
            pass

        return _scrape_insta_html(session, url, shortcode)

    except Exception as e:
        return jsonify({
            "status": False,
            "owner": "Xeon Vro",
            "platform": "instagram",
            "error": str(e)
        }), 500


def shortcode_to_media_id(shortcode):
    """Convert Instagram shortcode to numeric media ID."""
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
    media_id = 0
    for char in shortcode:
        media_id = media_id * 64 + alphabet.index(char)
    return media_id


def _scrape_insta_html(session, url, shortcode):
    """Fallback: fetch page HTML and regex out media URLs."""
    try:
        resp = session.get(url, timeout=15)
        html = resp.text

        # Video
        video = re.search(r'"video_url"\s*:\s*"([^"]+)"', html)
        if video:
            return jsonify({
                "status": True,
                "owner": "Xeon Vro",
                "platform": "instagram",
                "type": "video",
                "media": video.group(1).replace("\\u0026", "&")
            })

        # Image
        image = re.search(r'"display_url"\s*:\s*"([^"]+)"', html)
        if image:
            return jsonify({
                "status": True,
                "owner": "Xeon Vro",
                "platform": "instagram",
                "type": "image",
                "media": image.group(1).replace("\\u0026", "&")
            })

        return jsonify({
            "status": False,
            "owner": "Xeon Vro",
            "platform": "instagram",
            "message": "Could not extract media. Cookies may be expired."
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
