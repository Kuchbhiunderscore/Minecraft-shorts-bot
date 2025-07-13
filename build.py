import os, random, subprocess, json, base64, textwrap
from datetime import datetime
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import requests

# === CONFIG =================================================================
MUSIC_TRACKS = [
    "music1.mp3",
    "music2.mp3",
    "music3.mp3",   # add as many royalty-free tracks as you like
]
PARKOUR_CLIPS = [f"parkour{i}.mp4" for i in range(1, 6)]
OUT_DIR = "output"
os.makedirs(OUT_DIR, exist_ok=True)

# === 1. STORY GENERATION (PaLM text-bison-001) ==============================
import requests, os, json, textwrap

def _call_palm(prompt: str) -> str:
    url = (
        "https://generativelanguage.googleapis.com/v1beta/"
        f"models/text-bison-001:generateText?key={os.environ['GEMINI_API_KEY']}"
    )
    r = requests.post(
        url,
        headers={"Content-Type": "application/json"},
        json={"prompt": {"text": prompt}},
        timeout=60,
    )
    try:
        return r.json()["candidates"][0]["output"].strip()
    except Exception:
        print("❌ PaLM/Bison error:\n", textwrap.shorten(r.text, 400))
        raise

def generate_story(part: int) -> str:
    base_prompt = (
        "Write a sad, emotional Minecraft story in 2 parts. "
        "Each part ≈ 200 words. Part 1 ends on a cliff-hanger; "
        "Part 2 resolves it without repeating Part 1."
    )

    if part == 1:
        prompt = f"{base_prompt}\n\nGive me Part 1:"
    else:
        with open(f"{OUT_DIR}/part1_story.txt") as fp:
            p1 = fp.read()
        prompt = f"{base_prompt}\n\nHere is Part 1:\n{p1}\n\nNow give me Part 2:"

    story = def _call_palm(prompt: str) -> str:
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
        r = requests.post(url, headers=headers, json=body, timeout=60)
        if "application/json" in r.headers.get("content-type", ""):
            data = r.json()
            if "candidates" in data:
                try:
                    # generateText ➜ .output   |  generateContent ➜ .content.parts[0].text
                    if "output" in data["candidates"][0]:
                        return data["candidates"][0]["output"].strip()
                    else:
                        return (
                            data["candidates"][0]["content"]["parts"][0]["text"].strip()
                        )
                except Exception:
                    pass  # malformed, try next path
        # log (first 100 chars) for visibility
        print(f"❌ {p} →", r.status_code, r.text[:100])
    raise RuntimeError("PaLM API: no working endpoint found for this account")
    out = f"{OUT_DIR}/part{part}_story.txt"
    with open(out, "w") as fp:
        fp.write(story)
    return story

# === 2. TEXT-TO-SPEECH (Edge TTS) ===========================================
def tts(text: str, outfile: str):
    print("🗣️  TTS chars:", len(text))
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

# === helper: audio duration (seconds) =======================================
def get_audio_duration(path: str) -> float:
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        path,
    ]
    return float(subprocess.check_output(cmd).decode().strip())

# === 3. VIDEO COMPOSITION ====================================================
def render_video(part: int) -> str:
    clip = random.choice(PARKOUR_CLIPS)
    music = random.choice(MUSIC_TRACKS)
    story_path = f"{OUT_DIR}/part{part}_story.txt"
    audio_path = f"{OUT_DIR}/part{part}_voice.mp3"
    output_path = f"{OUT_DIR}/LoreJump_Part{part}.mp4"

    # voice-over
    with open(story_path) as fp:
        tts(fp.read(), audio_path)

    voice_len = min(get_audio_duration(audio_path), 45.0)  # cap 45 s

    # merge & loop video
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-stream_loop",
            "-1",
            "-i",
            clip,
            "-i",
            audio_path,
            "-i",
            music,
            "-t",
            str(voice_len),
            "-filter_complex",
            "[1:a][2:a]amix=inputs=2:duration=first[a]",
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

# === 4. YOUTUBE UPLOAD =======================================================
def upload_video(path: str, title: str, descr: str):
    token_json = base64.b64decode(os.environ["TOKEN_JSON"]).decode()
    creds = Credentials.from_authorized_user_info(
        json.loads(token_json),
        ["https://www.googleapis.com/auth/youtube.upload"],
    )
    yt = build("youtube", "v3", credentials=creds)
    req = yt.videos().insert(
        part="snippet,status",
        body={
            "snippet": {
                "title": title,
                "description": descr,
                "tags": ["minecraft", "shorts", "story", "parkour"],
                "categoryId": "20",
            },
            "status": {"privacyStatus": "public"},
        },
        media_body=MediaFileUpload(path),
    )
    vid = req.execute()["id"]
    print("✅ Uploaded", vid)

# === 5. MAIN ================================================================
def main():
    print("🧠 Generating stories …")
    part1_text = generate_story(1)
    part2_text = generate_story(2)

    print("🎬 Rendering Part 1 …")
    v1 = render_video(1)
    print("⬆️ Uploading Part 1 …")
    upload_video(v1, "LoreJump • Part 1", textwrap.shorten(part1_text, 100))

    print("🎬 Rendering Part 2 …")
    v2 = render_video(2)
    print("⬆️ Uploading Part 2 …")
    upload_video(v2, "LoreJump • Part 2", textwrap.shorten(part2_text, 100))

    print("✅ All done", datetime.utcnow())

if __name__ == "__main__":
    main()
