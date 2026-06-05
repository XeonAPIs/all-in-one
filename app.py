from flask import Flask, request, jsonify
import instaloader
import os
import re

app = Flask(__name__)

# -------------------------
# Instaloader Setup
# -------------------------

L = instaloader.Instaloader(
    download_pictures=False,
    download_videos=False,
    download_video_thumbnails=False,
    save_metadata=False,
    compress_json=False,
)

IG_USERNAME = os.getenv("IG_USERNAME")
IG_PASSWORD = os.getenv("IG_PASSWORD")

if IG_USERNAME and IG_PASSWORD:
    try:
        L.login(IG_USERNAME, IG_PASSWORD)
        print("Instagram login successful")
    except Exception as e:
        print(f"Instagram login failed: {e}")

# -------------------------
# CORS
# -------------------------

@app.after_request
def add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    response.headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
    return response

# -------------------------
# Home
# -------------------------

@app.route("/")
def home():
    return jsonify({
        "status": True,
        "platform": "instagram",
        "endpoint": "/insta?url="
    })

# -------------------------
# Instagram Downloader
# -------------------------

@app.route("/insta")
def insta():

    url = request.args.get("url")

    if not url:
        return jsonify({
            "status": False,
            "message": "No URL provided"
        }), 400

    try:

        url = url.split("?")[0]

        match = re.search(
            r"/(?:reel|p|tv)/([^/?]+)/?",
            url
        )

        if not match:
            return jsonify({
                "status": False,
                "message": "Invalid Instagram URL"
            }), 400

        shortcode = match.group(1)

        post = instaloader.Post.from_shortcode(
            L.context,
            shortcode
        )

        media = []

        # Carousel posts
        if post.typename == "GraphSidecar":

            for node in post.get_sidecar_nodes():

                media.append({
                    "type": "video" if node.is_video else "image",
                    "url": node.video_url if node.is_video else node.display_url
                })

        # Single post
        else:

            media.append({
                "type": "video" if post.is_video else "image",
                "url": post.video_url if post.is_video else post.url
            })

        return jsonify({
            "status": True,
            "platform": "instagram",
            "shortcode": shortcode,
            "username": post.owner_username,
            "caption": post.caption or "",
            "likes": post.likes,
            "comments": post.comments,
            "media": media
        })

    except Exception as e:

        return jsonify({
            "status": False,
            "error_type": type(e).__name__,
            "error": str(e)
        }), 500

# -------------------------
# Run
# -------------------------

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port)
