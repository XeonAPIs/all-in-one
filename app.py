from flask import Flask, request, jsonify
import requests
import re
import os
from urllib.parse import urlparse

app = Flask(__name__)

FB_API = "https://getindevice.com/api/download/"
IG_API = "https://7kpgrnvomroojzq6fw5e6qkogq0zyiuv.lambda-url.eu-north-1.on.aws/api/instagram/fetch"

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
            "owner": "XeonModz",
            "platform": "instagram",
            "message": "No URL provided"
        }), 400

    if "instagram.com" not in url:
        return jsonify({
            "status": False,
            "owner": "XeonModz",
            "platform": "instagram",
            "message": "Invalid Instagram URL"
        }), 400

    try:
        response = requests.post(
            IG_API,
            json={"url": url},
            headers={"Content-Type": "application/json"},
            timeout=30
        )

        response.raise_for_status()

        raw = response.json()
        data = raw.get("data", {}) if isinstance(raw, dict) else {}
        post_info = data.get("postInfo", {}) or {}
        media_items = data.get("mediaItems", []) or []

        media = []
        for item in media_items:
            media.append({
                "type": item.get("type"),
                "url": item.get("url"),
                "thumbnail": item.get("thumbnail"),
                "dimensions": item.get("dimensions")
            })

        return jsonify({
            "status": raw.get("success", False) if isinstance(raw, dict) else False,
            "owner": "XeonModz",
            "platform": "instagram",
            "caption": post_info.get("caption", ""),
            "mediaCount": len(media),
            "isCarousel": len(media) > 1,
            "media": media
        })

    except requests.exceptions.Timeout:
        return jsonify({
            "status": False,
            "owner": "XeonModz",
            "platform": "instagram",
            "error": "Upstream request timed out"
        }), 504

    except requests.exceptions.RequestException as e:
        return jsonify({
            "status": False,
            "owner": "XeonModz",
            "platform": "instagram",
            "error": str(e)
        }), 500

    except Exception as e:
        return jsonify({
            "status": False,
            "owner": "XeonModz",
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
            "platform": "facebook",
            "message": "Missing Facebook URL"
        }), 400

    try:
        response = requests.post(
            FB_API,
            json={"url": url},
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/125.0.0.0 Safari/537.36"
                ),
                "Origin": "https://getindevice.com",
                "Referer": "https://getindevice.com/",
            },
            timeout=30
        )

        response.raise_for_status()

        data = response.json()

        videos = data.get("videos", []) or []

        # Sort by size (descending) when available, otherwise keep original order
        sorted_videos = sorted(
            videos,
            key=lambda v: (v.get("size") or 0),
            reverse=True
        )

        hd_video = sorted_videos[0] if len(sorted_videos) > 0 else {}
        sd_video = sorted_videos[1] if len(sorted_videos) > 1 else hd_video

        return jsonify({
            "status": True if videos else False,
            "platform": "facebook",
            "title": data.get("title") or "Untitled",
            "videos": {
                "hd": {
                    "size": hd_video.get("size"),
                    "url": hd_video.get("url")
                },
                "sd": {
                    "size": sd_video.get("size"),
                    "url": sd_video.get("url")
                }
            },
            "photos": data.get("photos", [])
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

IGNORE_LINKS = {
    "https://i.pinimg.com/originals/d5/3b/01/d53b014d86a6b6761bf649a0ed813c2b.png"
}

@app.route("/pin")
def pin():

    url = request.args.get("url")

    if not url:
        return jsonify({
            "status": False,
            "platform": "pinterest",
            "message": "Missing Pinterest URL"
        }), 400

    try:

        parsed = urlparse(url)

        if not any(domain in parsed.netloc for domain in ["pinterest.com", "pin.it"]):
            return jsonify({
                "status": False,
                "platform": "pinterest",
                "message": "Invalid Pinterest URL"
            }), 400

        response = requests.get(
            url,
            headers=HEADERS,
            timeout=20
        )

        response.raise_for_status()

        html = response.text

        result = {}

        # -------- Images --------
        image_urls = re.findall(
            r"https://i\.pinimg\.com/[^\s'\"<>]+?\.(?:jpg|jpeg|png|webp)",
            html
        )

        image_urls = [
            u for u in set(image_urls)
            if u not in IGNORE_LINKS
        ]

        if image_urls:

            originals = [
                u for u in image_urls
                if "/originals/" in u
            ]

            if originals:
                result["images"] = sorted(set(originals))

            else:
                res_map = {}

                for u in image_urls:
                    m = re.search(r"/(\d+)x/", u)

                    size = int(m.group(1)) if m else 0

                    res_map.setdefault(size, []).append(u)

                if res_map:
                    largest = max(res_map.keys())
                    result["images"] = sorted(
                        set(res_map[largest])
                    )

        # -------- Videos --------
        video_urls = re.findall(
            r"https://(?:v|v1|i)\.pinimg\.com/[^\s'\"<>]+?\.mp4",
            html
        )

        if video_urls:
            result["videos"] = sorted(
                set(video_urls),
                key=len,
                reverse=True
            )

        result.setdefault("images", [])
        result.setdefault("videos", [])

        return jsonify({
            "status": True,
            "platform": "pinterest",
            "images": result["images"],
            "videos": result["videos"]
        })

    except Exception as e:
        return jsonify({
            "status": False,
            "platform": "pinterest",
            "error": str(e)
        }), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
