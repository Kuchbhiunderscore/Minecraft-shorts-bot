import os
import json
import random
import subprocess
from datetime import datetime
import base64
import requests

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build as youtube_build
from googleapiclient.http import MediaFileUpload

# === CONFIG ===
OUT_DIR = "output"
PARKOUR_CLIPS = [f"parkour{i}.mp4" for i in range(1, 6)]
MUSIC = "music1.mp3"
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

os.makedirs(OUT_DIR, exist_ok=True)


# ── 1. Gemini story generation ─────────────────────────────
def _call_gemini(prompt: str) -> str:
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={GEMINI_API_KEY}"
        headers = {"Content-Type": "application/json"}
        payload = {"contents": [{"parts": [{"text": prompt}]}]}
        res = requests.post(url, headers=headers, json=payload)
        if res.status_code != 200:
            print("⚠️  Gemini responded", res.status_code, ":", res.text)
            raise Exception("Gemini error")
        data = res.json()
        return data["candidates"][0]["content"]["parts"][0]["text"].strip()
    except Exception:
        return None


def generate_story(part: int) -> list[str]:
    base_prompt = (
        "Write a Minecraft story in short poetic lines. Format like:\n"
        "Steve ran from the cave.\nThe diamond slipped away.\nHe fell into lava.\nBut woke up safe.\n"
        f"Keep it under 8 lines. Add a twist. Return only Part {part}."
    )
    if part == 2:
        try:
            prev = open(f"{OUT_DIR}/part1.txt").read()
            base_prompt += f"\n\nHere is Part 1:\n{prev}\n\nContinue with Part 2."
        except:
            pass

    text = _call_gemini(base_prompt)
    if not text:
        print("💤 Switching to offline fallback text.")
        text = (
            "Steve raced the cliffs.\n"
            "He stumbled on a lonely cat.\n"
            "They heard cracks below.\n"
            "The bridge shattered…"
        ) if part == 1 else (
            "They fell but survived.\n"
            "A mineshaft broke their fall.\n"
            "The cat purred beside him.\n"
            "Together, they climbed back up."
        )
    with open(f"{OUT_DIR}/part{part}.txt", "w") as f:
        f.write(text)
    return text.strip().split("\n")


# ── 2. TTS with SSML (fixed flag) ─────────────────────────
def ssml(lines: list[str]) -> str:
    blocks = [f"<p>{line}</p>" for line in lines]
    return f"<speak><prosody rate='85%' pitch='+3%'>{'<break time=\"600ms\"/>'.join(blocks)}</prosody></speak>"


def tts(ssml_str: str, out_mp3: str):
    subprocess.run(
        [
            "edge-tts",
            "--text", ssml_str,
            "--voice", "en-US-JennyNeural",
            "--write-media", out_mp3
        ],
        check=True,
    )


# ── 3. Get audio length ───────────────────────────────────
def audio_len(path: str) -> float:
    cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration",
           "-of", "default=nw=1:nk=1", path]
    return float(subprocess.check_output(cmd).decode().strip())


# ── 4. Burn subtitles into video ──────────────────────────
def burn_subs(lines: list[str], duration: float, out_path: str) -> str:
    n = len(lines)
    dur = duration / n
    subs_file = f"{OUT_DIR}/temp.srt"
    with open(subs_file, "w") as f:
        for i, line in enumerate(lines):
            start = i * dur
            end = start + dur
            f.write(f"{i+1}\n")
            f.write(
                f"00:00:{int(start):02d},000 --> 00:00:{int(end):02d},000\n{line}\n\n"
            )
    return subs_file


# ── 5. Render video ───────────────────────────────────────
def render(part: int, lines: list[str]) -> str:
    mp3 = f"{OUT_DIR}/p{part}.mp3"
    tts(ssml(lines), mp3)
    dur = min(audio_len(mp3), 60.0)
    clip = random.choice(PARKOUR_CLIPS)
    subs = burn_subs(lines, dur, f"{OUT_DIR}/subs{part}.srt")
    out = f"{OUT_DIR}/LoreJump_Part{part}.mp4"

    subprocess.run([
        "ffmpeg", "-y",
        "-i", clip,
        "-i", mp3,
        "-i", MUSIC,
        "-filter_complex",
        "[1:a][2:a]amix=inputs=2:duration=first[a]",
        "-map", "0:v", "-map", "[a]",
        "-vf", f"subtitles={subs}:force_style='FontSize=24,PrimaryColour=&HFFFFFF&'",
        "-shortest", out,
    ], check=True)

    return out


# ── 6. Upload to YouTube ─────────────────────────────────
def upload(path: str, title: str, lines: list[str]):
    token_json = base64.b64decode(os.environ["TOKEN_JSON"]).decode()
    creds = Credentials.from_authorized_user_info(
        json.loads(token_json), ["https://www.googleapis.com/auth/youtube.upload"]
    )
    yt = youtube_build("youtube", "v3", credentials=creds)
    request = yt.videos().insert(
        part="snippet,status",
        body={
            "snippet": {
                "title": title,
                "description": "\n".join(lines),
                "tags": ["minecraft", "shorts", "parkour", "story"],
                "categoryId": "20",
            },
            "status": {"privacyStatus": "public"},
        },
        media_body=MediaFileUpload(path),
    )
    resp = request.execute()
    print("✅ Uploaded:", resp["id"])


# ── 7. Pipeline ──────────────────────────────────────────
def main():
    print("🧠 Making Part 1"); lines1 = generate_story(1)
    print("🧠 Making Part 2"); lines2 = generate_story(2)

    print("🎬 Rendering + uploading Part 1")
    upload(render(1, lines1), "LoreJump • Part 1", lines1)

    print("🎬 Rendering + uploading Part 2")
    upload(render(2, lines2), "LoreJump • Part 2", lines2)

    print("🎉 Done:", datetime.utcnow())


if __name__ == "__main__":
    main()
