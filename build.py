import os
import random
import subprocess
import json, base64
from datetime import datetime

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# === CONFIG ===
MUSIC = "music1.mp3"
PARKOUR_CLIPS = [f"parkour{i}.mp4" for i in range(1, 6)]
OUT_DIR = "output"
PROMPT_FILE = "prompt.txt"

# === PREP ===
os.makedirs(OUT_DIR, exist_ok=True)

# === 0. GEMINI / PALM FALLBACK HANDLER ===

import requests

def _call_palm(prompt: str) -> str:
    key = os.environ["GEMINI_API_KEY"]
    base = "https://generativelanguage.googleapis.com"
    paths = [
        "v1beta/models/text-bison-001:generateText",
        "v1beta2/models/text-bison-001:generateText",
        "v1beta/models/text-bison-001:generateContent",
    ]
    headers = {"Content-Type": "application/json"}
    body_txt = {"prompt": {"text": prompt}}
    body_cnt = {"contents": [{"parts": [{"text": prompt}]}]}

    for p in paths:
        url = f"{base}/{p}?key={key}"
        body = body_txt if "generateText" in p else body_cnt
        try:
            r = requests.post(url, headers=headers, json=body, timeout=60)
            if "application/json" in r.headers.get("content-type", ""):
                data = r.json()
                if "candidates" in data:
                    try:
                        if "output" in data["candidates"][0]:
                            return data["candidates"][0]["output"].strip()
                        else:
                            return data["candidates"][0]["content"]["parts"][0]["text"].strip()
                    except Exception:
                        continue
        except Exception as e:
            print("❌ API error:", e)
    raise RuntimeError("PaLM API: no working endpoint found for this account")

# === 1. STORY GENERATION ===

def generate_story(part: int) -> str:
    base_prompt = (
        "Write a short, emotional Minecraft story in 2 parts. "
        "Each part must be under 400 characters. Add a twist or cliffhanger in Part 1."
    )
    if part == 1:
        prompt = f"{base_prompt}\n\nGive me Part 1:"
    else:
        part1_text = open(f"{OUT_DIR}/part1_story.txt").read()
        prompt = f"{base_prompt}\n\nHere is Part 1:\n{part1_text}\n\nNow give me Part 2:"

    story = _call_palm(prompt)
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

def render_video(part: int, voice_duration: float) -> str:
    clip = random.choice(PARKOUR_CLIPS)
    story_path = f"{OUT_DIR}/part{part}_story.txt"
    audio_path = f"{OUT_DIR}/part{part}_voice.mp3"
    output_path = f"{OUT_DIR}/LoreJump_Part{part}.mp4"

    # 3a. voice-over
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
        "-t", str(voice_duration + 3),  # add buffer seconds
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

# === 5. MAIN WORKFLOW ===

def main():
    print("🧠 Generating stories …")
    part1_text = generate_story(1)
    part2_text = generate_story(2)

    print("🎬 Rendering Part 1 …")
    part1_voice_duration = len(part1_text.split()) / 2.2  # avg ~2.2 words/sec
    part1_mp4 = render_video(1, part1_voice_duration)
    upload_video(
        part1_mp4,
        "LoreJump • Part 1",
        "Auto‑uploaded via LoreJumpBot. Part 2 follows!",
        ["minecraft", "shorts", "story", "parkour"],
    )

    print("🎬 Rendering Part 2 …")
    part2_voice_duration = len(part2_text.split()) / 2.2
    part2_mp4 = render_video(2, part2_voice_duration)
    upload_video(
        part2_mp4,
        "LoreJump • Part 2",
        "Thanks for watching Part 2!",
        ["minecraft", "shorts", "story", "parkour"],
    )

    print("✅ Workflow finished:", datetime.utcnow())

if __name__ == "__main__":
    main()
