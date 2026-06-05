from flask import Flask, request, jsonify
import requests
import re
import os
import json
from urllib.parse import urlparse, quote

app = Flask(__name__)

FB_API = "https://serverless-tooly-gateway-6n4h522y.ue.gateway.dev/facebook/video"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
}


def load_cookies(path="cookies.txt"):
    """Load Netscape-format cookies.txt into a requests CookieJar."""
    jar = requests.cookies.RequestsCookieJar()
    if not os.path.exists(path):
        return jar
    with open(path, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("HttpOnly,"):
                continue
            parts = line.split("\t")
            if len(parts) >= 7:
                domain = parts[0]
                # skip if domain doesn't contain instagram
                if "instagram" not in domain and ".ig" not in domain:
                    # still try to include but keep going
                    pass
                flag = parts[1]
                path_c = parts[2]
                secure = parts[3].lower() == "true"
                expires = parts[4]
                name = parts[5]
                value = parts[6]
                jar.set(name, value, domain=domain, path=path_c, secure=secure)
            else:
                # Handle comma-separated format from some extensions
                parts2 = line.split(",")
                if len(parts2) >= 2:
                    name = parts2[0].strip()
                    value = parts2[1].strip().strip(";")
                    jar.set(name, value, domain=".instagram.com", path="/")
    return jar


COOKIE_JAR = load_cookies()


def get_csrf_token():
    """Extract csrftoken from cookie jar."""
    for cookie in COOKIE_JAR:
        if cookie.name == "csrftoken":
            return cookie.value
    return ""


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
# Instagram Downloader (FIXED)
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

        match = re.search(
            r"(?:reel|p|tv)/([^/?]+)",
            url
        )

        if not match:
            return jsonify({
                "status": False,
                "owner": "Xeon Vro",
                "message": "Invalid Instagram URL"
            }), 400

        shortcode = match.group(1)

        sess = requests.Session()
        sess.headers.update(HEADERS)
        sess.cookies.update(COOKIE_JAR)

        response = sess.get(
            f"https://www.instagram.com/p/{shortcode}/?__a=1&__d=dis",
            timeout=20
        )

        if response.status_code != 200:
            response = sess.get(
                f"https://www.instagram.com/reel/{shortcode}/?__a=1&__d=dis",
                timeout=20
            )

        try:
            data = response.json()
        except:
            return jsonify({
                "status": False,
                "owner": "Xeon Vro",
                "platform": "instagram",
                "error": "Instagram returned invalid response"
            }), 500

        media = []

        media_data = (
            data.get("items", [{}])[0]
            or data.get("graphql", {}).get("shortcode_media", {})
            or data.get("data", {}).get("xdt_shortcode_media", {})
        )

        if not media_data:
            return jsonify({
                "status": False,
                "owner": "Xeon Vro",
                "platform": "instagram",
                "error": "Media not found"
            }), 404

        if media_data.get("carousel_media"):

            for item in media_data["carousel_media"]:

                if item.get("video_versions"):
                    media.append({
                        "type": "video",
                        "url": item["video_versions"][0]["url"]
                    })

                elif item.get("image_versions2"):
                    media.append({
                        "type": "image",
                        "url": item["image_versions2"]["candidates"][0]["url"]
                    })

        else:

            if media_data.get("video_versions"):
                media.append({
                    "type": "video",
                    "url": media_data["video_versions"][0]["url"]
                })

            elif media_data.get("display_url"):
                media.append({
                    "type": "image",
                    "url": media_data["display_url"]
                })

            elif media_data.get("image_versions2"):
                media.append({
                    "type": "image",
                    "url": media_data["image_versions2"]["candidates"][0]["url"]
                })

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
