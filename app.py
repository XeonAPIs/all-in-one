from flask import Flask, request, jsonify
import requests
import re
import os
from urllib.parse import urlparse

app = Flask(__name__)

FB_API = "https://serverless-tooly-gateway-6n4h522y.ue.gateway.dev/facebook/video"
FB_FALLBACK_API = "https://getindevice.com/api/download/"
IG_API = "https://7kpgrnvomroojzq6fw5e6qkogq0zyiuv.lambda-url.eu-north-1.on.aws/api/instagram/fetch"

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/json,*/*",
}

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
        resolved_url = _resolve_facebook_url(url)

        data = _call_fb_extractor(resolved_url)

        videos = data.get("videos", {}) or {}
        hd_url = videos.get("hd", {}).get("url")
        sd_url = videos.get("sd", {}).get("url")

        # If the extractor came back empty on the first try, retry once —
        # this API occasionally needs a second attempt for slower Facebook
        # scrapes (cold cache on their end, transient hiccup, etc).
        if not hd_url and not sd_url:
            data = _call_fb_extractor(resolved_url)
            videos = data.get("videos", {}) or {}
            hd_url = videos.get("hd", {}).get("url")
            sd_url = videos.get("sd", {}).get("url")

        # Still nothing? Some specific videos that the primary extractor
        # can't handle DO work through getindevice.com — try it as a
        # fallback before giving up entirely.
        if not hd_url and not sd_url:
            fallback = _call_fb_fallback(resolved_url)
            if fallback:
                return jsonify({
                    "status": True,
                    "platform": "facebook",
                    "title": fallback.get("title") or "Untitled",
                    "videos": {
                        "hd": {
                            "size": fallback.get("size"),
                            "url": fallback.get("url")
                        },
                        "sd": {
                            "size": None,
                            "url": None
                        }
                    }
                })

        return jsonify({
            "status": bool(hd_url or sd_url),
            "platform": "facebook",
            "title": data.get("title", "Untitled"),
            "videos": {
                "hd": {
                    "size": videos.get("hd", {}).get("size"),
                    "url": hd_url
                },
                "sd": {
                    "size": videos.get("sd", {}).get("size"),
                    "url": sd_url
                }
            }
        })

    except requests.exceptions.Timeout:
        return jsonify({
            "status": False,
            "platform": "facebook",
            "message": "Upstream extractor timed out. Please try again."
        }), 504

    except requests.exceptions.HTTPError as e:
        return jsonify({
            "status": False,
            "platform": "facebook",
            "message": f"Upstream extractor returned an error: {e}"
        }), 502

    except Exception as e:
        return jsonify({
            "status": False,
            "platform": "facebook",
            "error": str(e)
        }), 500


def _resolve_facebook_url(url):
    """
    Facebook shortlinks (share/, fb.watch, and reel share links) redirect to
    the real canonical post/video URL. The extractor API can't always follow
    that redirect itself, so we resolve it here first and pass the final
    canonical URL along instead.
    """
    try:
        head_resp = requests.get(
            url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/125.0.0.0 Safari/537.36"
                )
            },
            allow_redirects=True,
            timeout=15
        )
        if head_resp.url:
            return head_resp.url
    except requests.exceptions.RequestException:
        pass

    return url


def _call_fb_extractor(resolved_url):
    """Call the upstream Facebook extractor API and return its parsed JSON."""
    response = requests.get(
        FB_API,
        params={"url": resolved_url},
        timeout=60
    )
    response.raise_for_status()
    return response.json()


def _call_fb_fallback(resolved_url):
    """
    Fallback extractor (getindevice.com). This site rejects bare API calls
    with 403 because it expects a browser-like session — so we first load
    its homepage to pick up cookies, then reuse that session for the
    actual POST. Returns the best available video dict, or None on failure.
    """
    try:
        session = requests.Session()
        session.headers.update(BROWSER_HEADERS)

        # Establish cookies/session by hitting the homepage first
        session.get("https://getindevice.com/", timeout=15)

        resp = session.post(
            FB_FALLBACK_API,
            json={"url": resolved_url},
            headers={
                "Content-Type": "application/json",
                "Origin": "https://getindevice.com",
                "Referer": "https://getindevice.com/",
            },
            timeout=30
        )
        resp.raise_for_status()
        data = resp.json()

        videos = data.get("videos", []) or []
        if not videos:
            return None

        # Pick the largest/best available video (by size if present)
        best = sorted(
            videos,
            key=lambda v: (v.get("size") or 0),
            reverse=True
        )[0]

        if not best.get("url"):
            return None

        return {
            "title": data.get("title"),
            "url": best.get("url"),
            "size": best.get("size"),
        }

    except requests.exceptions.RequestException:
        return None

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
