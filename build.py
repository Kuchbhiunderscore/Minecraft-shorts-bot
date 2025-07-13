import os
import random
import subprocess
import json
import base64
from datetime import datetime

import requests
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# ── CONFIG ──────────────────────────────────────────────────────────────
OUT_DIR = "output"
os.makedirs(OUT_DIR, exist_ok=True)

MUSIC = "music1.mp3"                       # royalty-free bg music
PARKOUR_CLIPS = [f"parkour{i}.mp4" for i in range(1, 6)]

CHAR_VOICES = {                           # edge-tts voice map
    "Dad": "en-US-GuyNeural",
    "Mom": "en-US-JennyNeural",
    "Brother": "en-US-DavisNeural",
    "Sister": "en-US-AriaNeural",
    "Narrator": "en-US-EmmaNeural"
}

# ── 1. STORY GENERATION ─────────────────────────────────────────────────
def get_story() -> str:
    prompt = (
        "Write an emotional or funny short story (40–60 seconds when spoken). "
        "Use clear character labels: Dad:, Mom:, Brother:, Sister:, Narrator:. "
        "Keep it under 600 characters. No Minecraft. Real-life themes — "
        "family, rich-poor, friendships, sad or humorous twists."
    )
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        print("⚠️  No GEMINI_API_KEY; using fallback story.")
        return fallback_story()
    url = (
        "https://generativelanguage.googleapis.com/"
        f"v1beta/models/gemini-pro:generateContent?key={key}"
    )
    res = requests.post(
        url,
        headers={"Content-Type": "application/json"},
        json={"contents": [{"parts": [{"text": prompt}]}]},
        timeout=60,
    )
    try:
        return res.json()["candidates"][0]["content"]["parts"][0]["text"]
    except Exception:
        print("⚠️  Gemini failed, using fallback.")
        return fallback_story()


def fallback_story() -> str:
    return (
        "Dad: Why are you late?\n"
        "Son: I gave my lunch to a homeless man.\n"
        "Dad: Proud of you, kid.\n"
        "Narrator: Sometimes missing a meal feeds the soul."
    )


# ── 2. SSML + TTS ───────────────────────────────────────────────────────
def story_to_lines(story: str):
    lines = []
    for raw in story.splitlines():
        if ":" in raw:
            char, line = raw.split(":", 1)
            lines.append((char.strip(), line.strip()))
    return lines


def lines_to_ssml(lines):
    break_tag = '<break time="600ms"/>'
    parts = []
    for char, text in lines:
        voice = CHAR_VOICES.get(char, CHAR_VOICES["Narrator"])
        parts.append(f'<voice name="{voice}"><p>{text}</p></voice>')
    return f"<speak>{break_tag.join(parts)}</speak>"


def tts(ssml_str, out_mp3):
    # Write SSML to temporary file
    ssml_file = "temp.ssml"
    with open(ssml_file, "w") as f:
        f.write(ssml_str)
    subprocess.run(
        [
            "edge-tts",
            "--file", ssml_file,
            "--voice", "en-US-JennyNeural",
            "--write-media", out_mp3,
        ],
        check=True,
    )
    os.remove(ssml_file)


def audio_len(mp3_path) -> float:
    return float(
        subprocess.check_output(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=nw=1:nk=1",
                mp3_path,
            ]
        )
        .decode()
        .strip()
    )


# ── 3. VIDEO RENDERING ──────────────────────────────────────────────────
def render(voice_mp3, duration, out_name):
    clip = random.choice(PARKOUR_CLIPS)
    out = os.path.join(OUT_DIR, out_name)
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-stream_loop",
            "-1",
            "-i",
            clip,
            "-i",
            voice_mp3,
            "-i",
            MUSIC,
            "-t",
            str(duration + 1),
            "-filter_complex",
            "[1:a]volume=1.4[a1];[2:a]volume=0.08[a2];[a1][a2]amix=inputs=2:duration=first[a]",
            "-map",
            "0:v",
            "-map",
            "[a]",
            "-shortest",
            out,
        ],
        check=True,
    )
    return out


# ── 4. UPLOAD TO YOUTUBE ────────────────────────────────────────────────
def upload(video_path, title, description):
    creds_json = base64.b64decode(os.getenv("TOKEN_JSON")).decode()
    creds = Credentials.from_authorized_user_info(
        json.loads(creds_json), ["https://www.googleapis.com/auth/youtube.upload"]
    )
    yt = build("youtube", "v3", credentials=creds)
    request = yt.videos().insert(
        part="snippet,status",
        body={
            "snippet": {
                "title": title,
                "description": description,
                "tags": ["shorts", "emotional", "voiceover"],
                "categoryId": "22",
            },
            "status": {"privacyStatus": "public"},
        },
        media_body=MediaFileUpload(video_path),
    )
    resp = request.execute()
    print("✅ Uploaded:", resp["id"])


# ── 5. MAIN ─────────────────────────────────────────────────────────────
def main():
    print("🧠 Generating story …")
    story_text = get_story()
    lines = story_to_lines(story_text)
    if not lines:
        print("❌ No valid lines generated.")
        return

    print("🎙️  Synthesizing voices …")
    voice_mp3 = os.path.join(OUT_DIR, "voice.mp3")
    tts(lines_to_ssml(lines), voice_mp3)
    dur = min(audio_len(voice_mp3), 60.0)

    print("🎞️  Rendering video …")
    video_path = render(voice_mp3, dur, "final.mp4")

    print("⬆️  Uploading …")
    upload(video_path, "LoreJump • Emotional Short", lines[0][1])

    print("✅ All done:", datetime.utcnow())


if __name__ == "__main__":
    main()
