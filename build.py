import os
import random
import subprocess
import json
import base64
from datetime import datetime

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# === CONFIG ===
MUSIC = "music1.mp3"
PARKOUR_CLIPS = [f"parkour{i}.mp4" for i in range(1, 6)]
OUT_DIR = "output"
os.makedirs(OUT_DIR, exist_ok=True)

# === GEMINI STORY GENERATOR ===
def fetch_story(part: int):
    base_prompt = (
        "Write a short, emotional Minecraft story in 2 parts. "
        "Each part must be under 400 characters. Add cliffhanger in part 1."
    )
    if part == 1:
        prompt = f"{base_prompt}\n\nGive me Part 1 only:"
    else:
        part1 = open(f"{OUT_DIR}/part1.txt").read()
        prompt = f"{base_prompt}\n\nHere is Part 1:\n{part1}\nNow give me Part 2 only:"

    url = f"https://generativelanguage.googleapis.com/v1beta1/models/gemini-pro:generateContent?key={os.getenv('GEMINI_API_KEY')}"
    headers = {"Content-Type": "application/json"}
    payload = {"contents": [{"parts": [{"text": prompt}]}]}

    r = requests.post(url, headers=headers, json=payload)
    if r.status_code != 200:
        print("⚠️  Gemini responded", r.status_code, ":", r.text)
        return ["Steve ran fast.", "But danger waited…"]

    try:
        text = r.json()["candidates"][0]["content"]["parts"][0]["text"]
        return [line.strip() for line in text.splitlines() if line.strip()]
    except Exception as e:
        print("⚠️  Gemini failed:", e)
        return ["Steve ran fast.", "But danger waited…"]

# === SSML ENCODER ===
def ssml(lines: list[str]) -> str:
    blocks = [f"<p>{line}</p>" for line in lines]
    break_tag = '<break time="600ms"/>'
    return f"<speak><prosody rate='85%' pitch='+3%'>{break_tag.join(blocks)}</prosody></speak>"

# === TTS ===
def tts(ssml_str: str, out: str):
    ssml_path = "temp.ssml"
    with open(ssml_path, "w") as f:
        f.write(ssml_str)
    subprocess.run([
        "edge-tts",
        "--file", ssml_path,
        "--voice", "en-US-JennyNeural",
        "--write-media", out
    ], check=True)
    os.remove(ssml_path)

# === AUDIO LENGTH DETECTOR ===
def audio_len(path: str) -> float:
    cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration",
           "-of", "default=nw=1:nk=1", path]
    return float(subprocess.check_output(cmd).decode().strip())

# === VIDEO RENDERING ===
def render(part: int, duration: float) -> str:
    clip = random.choice(PARKOUR_CLIPS)
    voice = f"{OUT_DIR}/p{part}.mp3"
    out = f"{OUT_DIR}/LoreJump_Part{part}.mp4"
    subprocess.run([
        "ffmpeg", "-y",
        "-i", clip, "-i", voice, "-i", MUSIC,
        "-filter_complex", "[1:a][2:a]amix=inputs=2:duration=first[a]",
        "-map", "0:v", "-map", "[a]",
        "-t", str(duration),
        "-shortest",
        out
    ], check=True)
    return out

# === YOUTUBE UPLOADER ===
def upload(path: str, title: str, lines: list[str]):
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
                "description": "\n".join(lines),
                "tags": ["minecraft", "shorts", "emotional", "parkour"],
                "categoryId": "20"
            },
            "status": {"privacyStatus": "public"}
        },
        media_body=MediaFileUpload(path)
    )
    resp = request.execute()
    print("✅ Uploaded:", resp["id"])

# === MAIN ===
def main():
    print("🧠 Making Part 1")
    part1_lines = fetch_story(1)
    with open(f"{OUT_DIR}/part1.txt", "w") as f:
        f.write("\n".join(part1_lines))
    tts(ssml(part1_lines), f"{OUT_DIR}/p1.mp3")

    print("🧠 Making Part 2")
    part2_lines = fetch_story(2)
    with open(f"{OUT_DIR}/part2.txt", "w") as f:
        f.write("\n".join(part2_lines))
    tts(ssml(part2_lines), f"{OUT_DIR}/p2.mp3")

    print("🎬 Rendering + uploading Part 1")
    d1 = min(audio_len(f"{OUT_DIR}/p1.mp3"), 60.0)
    upload(render(1, d1), "LoreJump • Part 1", part1_lines)

    print("🎬 Rendering + uploading Part 2")
    d2 = min(audio_len(f"{OUT_DIR}/p2.mp3"), 60.0)
    upload(render(2, d2), "LoreJump • Part 2", part2_lines)

    print("✅ Done at", datetime.utcnow())

if __name__ == "__main__":
    import requests
    main()
