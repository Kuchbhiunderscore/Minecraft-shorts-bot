import os
import random
import subprocess
import json, base64
from datetime import datetime
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import requests

# === CONFIG ===
MUSIC = "music1.mp3"
PARKOUR_CLIPS = [f"parkour{i}.mp4" for i in range(1, 6)]
OUT_DIR = "output"
PROMPT_FILE = "prompt.txt"

os.makedirs(OUT_DIR, exist_ok=True)

# === 1. STORY GENERATION ===
def generate_story(part):
    base_prompt = (
        "Write a short, emotional Minecraft story in 2 parts. "
        "Each part must be about 200 words. Add a twist or cliffhanger in Part 1. "
        "Do not repeat Part 1 in Part 2. Use emotional and immersive language."
    )

    if part == 1:
        prompt = f"{base_prompt}\n\nGive me Part 1:"
    else:
        part1_text = open(f"{OUT_DIR}/part1_story.txt").read()
        prompt = f"{base_prompt}\n\nHere is Part 1:\n{part1_text}\n\nNow give me Part 2:"

    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
    if not GEMINI_API_KEY:
        raise Exception("❌ Missing GEMINI_API_KEY environment variable!")

    url = f"https://generativelanguage.googleapis.com/v1beta1/models/gemini-pro:generateContent?key={GEMINI_API_KEY}"
    headers = {"Content-Type": "application/json"}
    payload = { "contents": [{ "parts": [{ "text": prompt }] }] }

    response = requests.post(url, headers=headers, json=payload)
    result = response.json()

    try:
        story = result["candidates"][0]["content"]["parts"][0]["text"].strip()
    except Exception:
        raise Exception(f"❌ Error getting story: {json.dumps(result)}")

    with open(f"{OUT_DIR}/part{part}_story.txt", "w") as f:
        f.write(story)
    return story

# === 2. TEXT‑TO‑SPEECH ===
def tts(text: str, outfile: str):
    subprocess.run([
        "edge-tts",
        "--text", text,
        "--voice", "en-US-AriaNeural",
        "--write-media", outfile,
    ], check=True)

# === 3. VIDEO COMPOSITION ===
def render_video(part: int) -> str:
    clip = random.choice(PARKOUR_CLIPS)
    story_path = f"{OUT_DIR}/part{part}_story.txt"
    audio_path = f"{OUT_DIR}/part{part}_voice.mp3"
    output_path = f"{OUT_DIR}/LoreJump_Part{part}.mp4"

    with open(story_path, "r") as f:
        text = f.read()
    tts(text, audio_path)

    # Match video length to voice-over (max 40 sec)
    duration_cmd = [
        "ffprobe", "-v", "error", "-show_entries",
        "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", audio_path
    ]
    duration = float(subprocess.check_output(duration_cmd).decode().strip())
    duration = min(duration, 40.0)

    subprocess.run([
        "ffmpeg", "-y",
        "-t", str(duration),
        "-i", clip,
        "-i", audio_path,
        "-i", MUSIC,
        "-filter_complex", "[1:a][2:a]amix=inputs=2:duration=first[a]",
        "-map", "0:v", "-map", "[a]",
        "-shortest",
        output_path,
    ], check=True)
    return output_path

# === 4. YOUTUBE UPLOAD ===
def upload_video(path: str, title: str, descr: str, tags: list[str]):
    token_json = base64.b64decode(os.environ["TOKEN_JSON"]).decode()
    creds = Credentials.from_authorized_user_info(
        json.loads(token_json), ["https://www.googleapis.com/auth/youtube.upload"]
    )
    youtube = build("youtube", "v3", credentials=creds)

    request = youtube.videos().insert(
        part="snippet,status",
        body={
            "snippet": {
                "title": title,
                "description": descr,
                "tags": tags,
                "categoryId": "20",
            },
            "status": {"privacyStatus": "public"},
        },
        media_body=MediaFileUpload(path),
    )
    resp = request.execute()
    print("✅ Uploaded to YouTube:", resp["id"])

# === MAIN PIPELINE ===
def main():
    print("🧠 Generating stories …")
    part1 = generate_story(1)
    part2 = generate_story(2)

    print("🎬 Rendering Part 1 …")
    part1_mp4 = render_video(1)
    print("⬆️  Uploading Part 1 …")
    upload_video(part1_mp4, "LoreJump • Part 1", part1, ["minecraft", "shorts", "story"])

    print("🎬 Rendering Part 2 …")
    part2_mp4 = render_video(2)
    print("⬆️  Uploading Part 2 …")
    upload_video(part2_mp4, "LoreJump • Part 2", part2, ["minecraft", "shorts", "story"])

    print("✅ Workflow finished at", datetime.utcnow())

if __name__ == "__main__":
    main()
