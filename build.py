# ✅ build.py (final, production-ready)

import os
import random
import subprocess
import json
from datetime import datetime
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build as youtube_build
from googleapiclient.http import MediaFileUpload
import requests

# Constants
OUT_DIR = "output"
MUSIC_FILE = "music1.mp3"
VIDEO_FILE = "parkour3.mp4"
VOICES = ["en-US-JennyNeural", "en-US-GuyNeural", "en-GB-SoniaNeural"]

# Fallback stories if Gemini fails
FALLBACK_STORIES = [
    "Dad worked hard, but his son never understood. One day, roles reversed.",
    "A rich girl mocked a poor boy. Years later, she begged him for a job.",
    "Brother stole from sister. She forgave. He saved her life one day."
]

# Ensure output directory exists
os.makedirs(OUT_DIR, exist_ok=True)

def generate_story():
    prompt = "Write a very short, emotional story (under 500 characters) involving family, siblings, or rich vs poor. Format for voice narration."
    try:
        response = requests.post(
            "https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent",
            headers={"Content-Type": "application/json"},
            params={"key": os.environ["GEMINI_API_KEY"]},
            json={"contents": [{"parts": [{"text": prompt}]}]}
        )
        result = response.json()
        story = result["candidates"][0]["content"]["parts"][0]["text"]
        if "def" in story or "{" in story:
            raise ValueError("Gemini responded with code instead of a story.")
        return story.strip()
    except Exception as e:
        print(f"⚠️  Gemini failed -> fallback: {e}")
        return random.choice(FALLBACK_STORIES)

def split_lines(text):
    return [(line.strip(), random.choice(VOICES)) for line in text.split('.') if line.strip()]

def ssml(lines):
    blocks = [f'<voice name="{v}"><p>{l}.</p></voice>' for l, v in lines]
    inner = "<break time='600ms'/>".join(blocks)
    return f"<speak><prosody rate='85%' pitch='+3%'>{inner}</prosody></speak>"

def tts(ssml_text, path):
    ssml_path = "temp_ssml.txt"
    with open(ssml_path, "w", encoding="utf-8") as f:
        f.write(ssml_text)
    subprocess.run([
        "edge-tts",
        "--file", ssml_path,
        "--write-media", path
    ], check=True)
    os.remove(ssml_path)

def audio_len(path):
    cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", path]
    return float(subprocess.check_output(cmd).decode().strip())

def render_video(voice_path):
    video_path = f"{OUT_DIR}/final.mp4"
    subprocess.run([
        "ffmpeg", "-y",
        "-i", VIDEO_FILE,
        "-i", voice_path,
        "-i", MUSIC_FILE,
        "-filter_complex",
        "[1:a]volume=1[a1];[2:a]volume=0.05[a2];[a1][a2]amix=inputs=2:duration=first:dropout_transition=2[aout]",
        "-map", "0:v",
        "-map", "[aout]",
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "23",
        "-c:a", "aac",
        "-shortest",
        video_path
    ], check=True)
    return video_path

def upload(path, title, desc):
    creds = Credentials.from_authorized_user_info(json.loads(os.environ["token_json"]))
    youtube = youtube_build("youtube", "v3", credentials=creds)
    request = youtube.videos().insert(
        part="snippet,status",
        body={
            "snippet": {"title": title, "description": desc, "tags": ["shorts"]},
            "status": {"privacyStatus": "public"}
        },
        media_body=MediaFileUpload(path)
    )
    request.execute()

def main():
    print("🧠  Story …")
    story = generate_story()
    lines = split_lines(story)

    print("🎙️  Voice …")
    voice_mp3 = f"{OUT_DIR}/voice.mp3"
    tts(ssml(lines), voice_mp3)

    print("🎞️  Video …")
    video = render_video(voice_mp3)

    print("⬆️  Uploading …")
    upload(video, "LoreJump • Emotional Short", lines[0][0])

if __name__ == "__main__":
    main()
