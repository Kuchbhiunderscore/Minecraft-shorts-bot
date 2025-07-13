import os
import random
import subprocess
import json, base64
from datetime import datetime

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# === CONFIG ===
MUSIC = "music1.mp3"                               # background track in assets/
PARKOUR_CLIPS = [f"parkour{i}.mp4" for i in range(1, 6)]  # pre‑recorded vertical clips
OUT_DIR = "output"                                  # where finished files go
PROMPT_FILE = "prompt.txt"                          # story prompt for the AI

# === PREP ===
os.makedirs(OUT_DIR, exist_ok=True)

# === 1. STORY GENERATION (placeholder text right now) ===

import openai

def generate_story(part):
    openai.api_key = os.environ["OPENAI_API_KEY"]

    base_prompt = "Write a short but emotional Minecraft story in 2 parts. Each part should be less than 400 characters. Add cliffhanger at end of Part 1."

    if part == 1:
        prompt = f"{base_prompt}\n\nGive me Part 1:"
    else:
        prompt = f"{base_prompt}\n\nHere is Part 1:\n{open('output/part1_story.txt').read()}\n\nNow write Part 2:"

    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",  # or "gpt-4" if you're upgraded
        messages=[{"role": "user", "content": prompt}]
    )

    story = response["choices"][0]["message"]["content"].strip()
    with open(f"{OUT_DIR}/part{part}_story.txt", "w") as f:
        f.write(story)

    return story

# === 2. TEXT‑TO‑SPEECH (Edge TTS) ===

def tts(text: str, outfile: str):
    subprocess.run([
        "edge-tts",
        "--text", text,
        "--voice", "en-US-AriaNeural",
        "--write-media", outfile,
    ], check=True)

# === 3. VIDEO COMPOSITION ===

def render_video(part: int) -> str:
    """Create the final MP4 for <part> and return its path."""
    clip = random.choice(PARKOUR_CLIPS)
    story_path = f"{OUT_DIR}/part{part}_story.txt"
    audio_path = f"{OUT_DIR}/part{part}_voice.mp3"
    output_path = f"{OUT_DIR}/LoreJump_Part{part}.mp4"

    # 3a. voice‑over
    with open(story_path, "r") as f:
        text = f.read()
    tts(text, audio_path)

    # 3b. merge video + voice + music
    subprocess.run([
        "ffmpeg", "-y",
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
                "categoryId": "20",  # Gaming
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
    generate_story(1)
    generate_story(2)

    print("🎬 Rendering Part 1 …")
    part1_mp4 = render_video(1)
    print("⬆️  Uploading Part 1 …")
    upload_video(
        part1_mp4,
        "LoreJump • Part 1",
        "Auto‑uploaded via LoreJumpBot. Part 2 follows!",
        ["minecraft", "shorts", "story", "parkour"],
    )

    print("🎬 Rendering Part 2 …")
    part2_mp4 = render_video(2)
    print("⬆️  Uploading Part 2 …")
    upload_video(
        part2_mp4,
        "LoreJump • Part 2",
        "Thanks for watching Part 2!",
        ["minecraft", "shorts", "story", "parkour"],
    )

    print("✅ Workflow finished:", datetime.utcnow())


if __name__ == "__main__":
    main()
