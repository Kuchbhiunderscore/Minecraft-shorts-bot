import os
import random
import subprocess
import json
from datetime import datetime

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build as youtube_build
from googleapiclient.http import MediaFileUpload
import requests

# ── CONSTANTS ────────────────────────────────────────────────────────────
OUT_DIR = "output"
MUSIC_FILE = "music1.mp3"
VIDEO_FILE = "parkour3.mp4"
VOICES = ["en-US-JennyNeural", "en-US-GuyNeural", "en-GB-SoniaNeural"]

os.makedirs(OUT_DIR, exist_ok=True)

FALLBACK_STORIES = [
    "Dad worked hard, but his son never understood. One day, roles reversed.",
    "A rich girl mocked a poor boy. Years later, she begged him for a job.",
    "Brother stole from sister. She forgave him. He saved her life one day."
]

# ── 1. STORY GENERATION ─────────────────────────────────────────────────
def generate_story() -> str:
    prompt = (
        "Write a very short, emotional story (under 500 characters) "
        "about family or rich vs poor. Format it for spoken narration."
    )
    try:
        res = requests.post(
            "https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent",
            headers={"Content-Type": "application/json"},
            params={"key": os.environ["GEMINI_API_KEY"]},
            json={"contents": [{"parts": [{"text": prompt}]}]},
            timeout=40,
        )
        text = res.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
        if "def" in text or "{" in text:
            raise ValueError("Gemini returned code-like text.")
        return text
    except Exception as e:
        print("⚠️  Gemini failed -> fallback:", e)
        return random.choice(FALLBACK_STORIES)

# ── 2. TEXT → SSML ──────────────────────────────────────────────────────
def split_lines(text):
    return [(line.strip(), random.choice(VOICES)) for line in text.split(".") if line.strip()]

def ssml(lines):
    blocks = [f'<voice name="{v}"><p>{l}.</p></voice>' for l, v in lines]
    break_tag = '<break time="600ms"/>'
    return f"<speak><prosody rate='85%' pitch='+3%'>{break_tag.join(blocks)}</prosody></speak>"

# ── 3. TTS ----------------------------------------------------------------
def tts(ssml_text: str, out_path: str):
    tmp = os.path.join(OUT_DIR, "tmp.ssml")
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(ssml_text)
    subprocess.run(["edge-tts", "--file", tmp, "--write-media", out_path], check=True)
    os.remove(tmp)

# ── 4. VIDEO RENDERING ----------------------------------------------------
def render_video(voice_mp3: str) -> str:
    out_mp4 = f"{OUT_DIR}/final.mp4"
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-i", VIDEO_FILE,
            "-i", voice_mp3,
            "-i", MUSIC_FILE,
            "-filter_complex",
            "[1:a]volume=1[a1];[2:a]volume=0.05[a2];[a1][a2]amix=inputs=2[aout]",
            "-map", "0:v", "-map", "[aout]",
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-c:a", "aac", "-shortest", out_mp4,
        ],
        check=True,
    )
    return out_mp4

# ── 5. UPLOAD -------------------------------------------------------------
def upload(video_path: str, title: str, desc: str):
    creds = Credentials.from_authorized_user_info(json.loads(os.environ["YT_CREDENTIALS"]))
    yt = youtube_build("youtube", "v3", credentials=creds)
    yt.videos().insert(
        part="snippet,status",
        body={
            "snippet": {"title": title, "description": desc, "tags": ["shorts"]},
            "status": {"privacyStatus": "public"},
        },
        media_body=MediaFileUpload(video_path),
    ).execute()

# ── 6. MAIN ---------------------------------------------------------------
def main():
    print("🧠  Story …")
    story = generate_story()
    lines = split_lines(story)

    print("🎙️  Voice …")
    voice_mp3 = f"{OUT_DIR}/voice.mp3"
    tts(ssml(lines), voice_mp3)

    print("🎞️  Video …")
    video = render_video(voice_mp3)

    print("⬆️  Upload …")
    upload(video, "LoreJump • Emotional Short", lines[0][0])

    print("✅ Finished:", datetime.utcnow())

if __name__ == "__main__":
    main()
