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

# Ensure output directory exists
os.makedirs(OUT_DIR, exist_ok=True)

# Gemini fallback stories
FALLBACK_STORIES = [
    "Dad worked hard, but his son never understood. One day, roles reversed.",
    "A rich girl mocked a poor boy. Years later, she begged him for a job.",
    "Brother stole from sister. She forgave him. He saved her life one day."
]

# ── STORY GENERATION ─────────────────────────────────────────────────────
def generate_story() -> str:
    prompt = (
        "Write a very short, emotional story (under 500 characters) "
        "involving family, siblings, or rich vs poor. "
        "Format for voice narration."
    )
    try:
        response = requests.post(
            "https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent",
            headers={"Content-Type": "application/json"},
            params={"key": os.environ["GEMINI_API_KEY"]},
            json={"contents": [{"parts": [{"text": prompt}]}]},
            timeout=40
        )
        story = response.json()["candidates"][0]["content"]["parts"][0]["text"]
        # Safety: if Gemini returns code or symbols, fall back
        if "def" in story or "{" in story:
            raise ValueError("Gemini responded with code.")
        return story.strip()
    except Exception as e:
        print(f"⚠️  Gemini failed, using fallback. Reason: {e}")
        return random.choice(FALLBACK_STORIES)

# ── TEXT → LINES → SSML ─────────────────────────────────────────────────
def split_lines(text: str):
    """Return list of (line, voice) tuples."""
    return [
        (line.strip(), random.choice(VOICES))
        for line in text.split(".") if line.strip()
    ]

def ssml(lines):
    blocks = [
        f'<voice name="{v}"><p>{l}.</p></voice>'
        for l, v in lines
    ]
    return (
        "<speak><prosody rate='85%' pitch='+3%'>"
        + '<break time="600ms"/>'.join(blocks) +
        "</prosody></speak>"
    )

# ── TTS / AUDIO UTILS ───────────────────────────────────────────────────
def tts(ssml_text: str, out_path: str):
    subprocess.run(
        ["edge-tts", "--ssml", ssml_text, "--write-media", out_path],
        check=True
    )

def audio_len(path: str) -> float:
    dur = subprocess.check_output(
        ["ffprobe", "-v", "error",
         "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", path]
    )
    return float(dur)

# ── VIDEO RENDERING ─────────────────────────────────────────────────────
def render_video(voice_path: str) -> str:
    video_out = f"{OUT_DIR}/final.mp4"
    subprocess.run([
        "ffmpeg", "-y",
        "-i", VIDEO_FILE,
        "-i", voice_path,
        "-i", MUSIC_FILE,
        "-filter_complex",
        "[1:a]volume=1[a1];[2:a]volume=0.05[a2];[a1][a2]amix=inputs=2"
        "[aout]",
        "-map", "0:v", "-map", "[aout]",
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        "-c:a", "aac",
        "-shortest", video_out
    ], check=True)
    return video_out

# ── YOUTUBE UPLOAD ──────────────────────────────────────────────────────
def upload(video: str, title: str, desc: str):
    creds = Credentials.from_authorized_user_info(
        json.loads(os.environ["YT_CREDENTIALS"])
    )
    yt = youtube_build("youtube", "v3", credentials=creds)
    yt.videos().insert(
        part="snippet,status",
        body={
            "snippet": {
                "title": title,
                "description": desc,
                "tags": ["shorts", "emotional"],
                "categoryId": "22"
            },
            "status": {"privacyStatus": "public"}
        },
        media_body=MediaFileUpload(video)
    ).execute()

# ── MAIN PIPELINE ───────────────────────────────────────────────────────
def main():
    print("🧠 Generating story …")
    story = generate_story()
    lines = split_lines(story)

    print("🎙️  Synthesizing voice …")
    voice_mp3 = f"{OUT_DIR}/voice.mp3"
    tts(ssml(lines), voice_mp3)

    print("🎞️  Rendering video …")
    video_path = render_video(voice_mp3)

    print("⬆️  Uploading …")
    upload(video_path, "LoreJump • Emotional Short", lines[0][0])

    print("✅ Done at", datetime.utcnow())

if __name__ == "__main__":
    main()
