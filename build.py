import os
import random
import subprocess
import json
import base64
from datetime import datetime

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import requests

# === CONFIG ==================================================================
MUSIC = "music1.mp3"                                     # background track
PARKOUR_CLIPS = [f"parkour{i}.mp4" for i in range(1, 6)] # vertical clips
OUT_DIR = "output"                                       # output folder
os.makedirs(OUT_DIR, exist_ok=True)

# === 1. STORY GENERATION (PaLM text-bison-001) ================================
def generate_story(part: int) -> str:
    base_prompt = (
        "Write a short, emotional Minecraft story in 2 parts. "
        "Each part must be around 1000 characters. Use simple language. "
        "Add a strong twist or cliff-hanger in Part 1."
    )

    if part == 1:
        prompt = f"{base_prompt}\n\nGive me Part 1:"
    else:
        with open(f"{OUT_DIR}/part1_story.txt") as fp:
            part1_text = fp.read()
        prompt = (
            f"{base_prompt}\n\nHere is Part 1:\n{part1_text}\n\nNow give me Part 2:"
        )

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("❌ GEMINI_API_KEY secret is missing")

    url = (
        "https://generativelanguage.googleapis.com/v1beta/"
        f"models/text-bison-001:generateText?key={api_key}"
    )
    resp = requests.post(
        url,
        headers={"Content-Type": "application/json"},
        json={"prompt": {"text": prompt}},
        timeout=60,
    )
    data = resp.json()

    try:
        story = data["candidates"][0]["output"].strip()
    except Exception:
        print("❌ PaLM/Bison response error:", json.dumps(data, indent=2))
        story = (
            "Steve paused on the final block, a chill crawling up his spine…"
            "little did he know the ground beneath him was hollow."
        )

    with open(f"{OUT_DIR}/part{part}_story.txt", "w") as fp:
        fp.write(story)
    return story

# === 2. TEXT-TO-SPEECH (Edge TTS) ============================================
def tts(text: str, outfile: str):
    subprocess.run(
        [
            "edge-tts",
            "--text",
            text,
            "--voice",
            "en-US-AriaNeural",
            "--write-media",
            outfile,
        ],
        check=True,
    )

# === 3. VIDEO COMPOSITION =====================================================
def render_video(part: int) -> str:
    clip = random.choice(PARKOUR_CLIPS)
    story_path = f"{OUT_DIR}/part{part}_story.txt"
    audio_path = f"{OUT_DIR}/part{part}_voice.mp3"
    output_path = f"{OUT_DIR}/LoreJump_Part{part}.mp4"

    # 3a voice-over
    with open(story_path) as fp:
        text = fp.read()
    tts(text, audio_path)

    # 3b merge & loop
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-stream_loop",
            "-1",            # loop parkour clip infinitely
            "-i",
            clip,
            "-i",
            audio_path,
            "-i",
            MUSIC,
            "-filter_complex",
            "[1:a][2:a]amix=inputs=2:duration=longest[a]",
            "-map",
            "0:v",
            "-map",
            "[a]",
            "-shortest",
            output_path,
        ],
        check=True,
    )
    return output_path

# === 4. YOUTUBE UPLOAD ========================================================
def upload_video(path: str, title: str, descr: str, tags: list[str]):
    token_json = base64.b64decode(os.environ["TOKEN_JSON"]).decode()
    creds = Credentials.from_authorized_user_info(
        json.loads(token_json),
        ["https://www.googleapis.com/auth/youtube.upload"],
    )
    youtube = build("youtube", "v3", credentials=creds)

    request = youtube.videos().insert(
        part="snippet,status",
        body={
            "snippet": {
                "title": title,
                "description": descr,
                "tags": tags,
                "categoryId": "20",  # Gaming
            },
            "status": {"privacyStatus": "public"},
        },
        media_body=MediaFileUpload(path),
    )
    resp = request.execute()
    print("✅ Uploaded:", resp["id"])

# === 5. MAIN ================================================================
def main():
    print("🧠 Generating stories …")
    generate_story(1)
    generate_story(2)

    print("🎬 Rendering Part 1 …")
    part1_mp4 = render_video(1)
    print("⬆️  Uploading Part 1 …")
    upload_video(
        part1_mp4,
        "LoreJump • Part 1",
        "Auto-uploaded via LoreJumpBot. Part 2 follows!",
        ["minecraft", "shorts", "story", "parkour"],
    )

    print("🎬 Rendering Part 2 …")
    part2_mp4 = render_video(2)
    print("⬆️  Uploading Part 2 …")
    upload_video(
        part2_mp4,
        "LoreJump • Part 2",
        "Thanks for watching Part 2!",
        ["minecraft", "shorts", "story", "parkour"],
    )

    print("✅ Workflow finished:", datetime.utcnow())

if __name__ == "__main__":
    main()
