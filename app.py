from flask import Flask, request, jsonify
import requests
import re
import os
import json
from urllib.parse import urlparse
from http.cookiejar import MozillaCookieJar

app = Flask(**name**)

FB_API = "https://serverless-tooly-gateway-6n4h522y.ue.gateway.dev/facebook/video"

HEADERS = {
"User-Agent": "Mozilla/5.0"
}

def get_instagram_session():
session = requests.Session()

session.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/137.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.instagram.com/",
    "Accept-Language": "en-US,en;q=0.9"
})

if os.path.exists("cookies.txt"):
    try:
        cj = MozillaCookieJar("cookies.txt")
        cj.load(ignore_discard=True, ignore_expires=True)

        for cookie in cj:
            session.cookies.set(
                cookie.name,
                cookie.value,
                domain=cookie.domain
            )

        print("Loaded cookies:", len(cj))

    except Exception as e:
        print("Cookie Error:", e)

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

@app.route("/insta")
def insta():

url = request.args.get("url")

if not url:
    return jsonify({
        "status": False,
        "message": "No URL provided"
    }), 400

try:

    url = url.split("?")[0].rstrip("/") + "/"

    session = get_instagram_session()

    response = session.get(
        url,
        timeout=30,
        allow_redirects=True
    )

    response.raise_for_status()

    html = response.text

    media_url = None
    media_type = None

    og_video = re.search(
        r'<meta property="og:video" content="([^"]+)"',
        html
    )

    if og_video:
        media_url = og_video.group(1)
        media_type = "video"

    if not media_url:
        og_image = re.search(
            r'<meta property="og:image" content="([^"]+)"',
            html
        )

        if og_image:
            media_url = og_image.group(1)
            media_type = "image"

    if not media_url:
        video_match = re.search(
            r'"video_url":"([^"]+)"',
            html
        )

        if video_match:
            media_url = (
                video_match.group(1)
                .replace("\\u0026", "&")
                .replace("\\/", "/")
            )
            media_type = "video"

    if not media_url:
        image_match = re.search(
            r'"display_url":"([^"]+)"',
            html
        )

        if image_match:
            media_url = (
                image_match.group(1)
                .replace("\\u0026", "&")
                .replace("\\/", "/")
            )
            media_type = "image"

    if not media_url:
        json_match = re.search(
            r'<script type="application/ld\+json">(.*?)</script>',
            html,
            re.DOTALL
        )

        if json_match:
            try:
                data = json.loads(json_match.group(1))

                media_url = (
                    data.get("contentUrl")
                    or data.get("thumbnailUrl")
                )

                media_type = (
                    "video"
                    if data.get("contentUrl")
                    else "image"
                )

            except Exception:
                pass

    if not media_url:
        return jsonify({
            "status": False,
            "platform": "instagram",
            "message": "Media not found"
        }), 404

    return jsonify({
        "status": True,
        "platform": "instagram",
        "type": media_type,
        "media": media_url
    })

except Exception as e:
    return jsonify({
        "status": False,
        "platform": "instagram",
        "error": str(e)
    }), 500

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

if **name** == "**main**":
port = int(os.environ.get("PORT", 8000))
app.run(host="0.0.0.0", port=port)
