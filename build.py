import os, random, subprocess, json, base64, textwrap
from datetime import datetime
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import requests, secrets, string

# === CONFIG ============================================================== #
MUSIC = "music1.mp3"
PARKOUR_CLIPS = [f"parkour{i}.mp4" for i in range(1, 6)]
OUT_DIR = "output"
os.makedirs(OUT_DIR, exist_ok=True)

# === 0. AI CALLER with FALLBACK ========================================= #
def call_gemini(prompt: str) -> str | None:
    """Return response text or None if every attempt fails."""
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        print("⚠️  GEMINI_API_KEY not set")
        return None

    url = (
        "https://generativelanguage.googleapis.com/"
        "v1beta/models/gemini-pro:generateContent?key=" + key
    )
    body = {"contents": [{"parts": [{"text": prompt}]}]}
    try:
        r = requests.post(url, headers={"Content-Type": "application/json"}, json=body, timeout=60)
        if r.status_code == 200 and r.headers.get("content-type","").startswith("application/json"):
            data = r.json()
            return data["candidates"][0]["content"]["parts"][0]["text"].strip()
        print("⚠️  Gemini responded", r.status_code, ":", r.text[:120])
    except Exception as e:
        print("⚠️  Gemini exception:", e)
    return None

def local_fallback(part: int) -> str:
    """Extremely simple offline story generator (so pipeline never dies)."""
    random.seed(secrets.randbits(64))
    hero = random.choice(["Steve", "Alex", "Noob", "Herobrine"])
    pet  = random.choice(["wolf", "cat", "parrot"])
    if part == 1:
        return (
            f"{hero} was sprint-jumping across the Nether when a lonely {pet} "
            "blocked the bridge. Thunder cracked—end of Part 1."
        )
    else:
        return (
            f"{hero} rescued the {pet}, but the bridge collapsed behind them. "
            "Sometimes saving a friend means losing the way home."
        )

# === 1. STORY GENERATION ================================================= #
def generate_story(part: int) -> str:
    base_prompt = (
        "Write a sad, emotional Minecraft story in 2 parts for YouTube Shorts. "
        "Each part ≈ 150 words. Part 1 ends on a cliff-hanger; Part 2 resolves it. "
        "Use simple language. Do NOT repeat Part 1 in Part 2."
    )
    if part == 1:
        prompt = f"{base_prompt}\n\nGive me Part 1:"
    else:
        with open(f"{OUT_DIR}/part1_story.txt") as fp:
            p1 = fp.read()
        prompt = f"{base_prompt}\n\nHere is Part 1:\n{p1}\n\nNow give me Part 2:"

    story = call_gemini(prompt)
    if story is None:
        print("💤 Switching to offline fallback text.")
        story = local_fallback(part)

    out = f"{OUT_DIR}/part{part}_story.txt"
    with open(out, "w") as f:
        f.write(story)
    return story

# === 2. TEXT-TO-SPEECH =================================================== #
def tts(text: str, out_mp3: str):
    subprocess.run(
        ["edge-tts", "--text", text, "--voice", "en-US-AriaNeural", "--write-media", out_mp3],
        check=True,
    )

def audio_len(path: str) -> float:
    cmd = ["ffprobe","-v","error","-show_entries","format=duration","-of","default=nw=1:nk=1",path]
    return float(subprocess.check_output(cmd).decode().strip())

# === 3. RENDER VIDEO ===================================================== #
def render_video(part: int, duration: float) -> str:
    clip   = random.choice(PARKOUR_CLIPS)
    music  = MUSIC
    voice  = f"{OUT_DIR}/part{part}_voice.mp3"
    story  = f"{OUT_DIR}/part{part}_story.txt"
    out_mp4= f"{OUT_DIR}/LoreJump_Part{part}.mp4"

    # TTS
    with open(story) as fp: tts(fp.read(), voice)

    # merge, loop clip, sync to voice len (cap 45 s)
    duration = min(audio_len(voice), 45.0)
    subprocess.run([
        "ffmpeg","-y",
        "-stream_loop","-1","-i",clip,
        "-i",voice,"-i",music,
        "-t",str(duration+1),
        "-filter_complex","[1:a][2:a]amix=inputs=2:duration=first[a]",
        "-map","0:v","-map","[a]","-shortest",out_mp4
    ],check=True)
    return out_mp4

# === 4. UPLOAD =========================================================== #
def upload(path:str,title:str,descr:str):
    token = base64.b64decode(os.environ["TOKEN_JSON"]).decode()
    creds = Credentials.from_authorized_user_info(json.loads(token),["https://www.googleapis.com/auth/youtube.upload"])
    yt = build("youtube","v3",credentials=creds)
    req = yt.videos().insert(
        part="snippet,status",
        body={"snippet":{"title":title,"description":descr,"categoryId":"20"},
              "status":{"privacyStatus":"public"}},
        media_body=MediaFileUpload(path)
    )
    vid = req.execute()["id"]
    print("✅ Uploaded:",vid)

# === 5. MAIN ============================================================= #
def main():
    print("🧠 Generating stories …")
    part1 = generate_story(1)
    part2 = generate_story(2)

    print("🎬 Rendering …")
    vid1 = render_video(1, audio_len(f"{OUT_DIR}/part1_voice.mp3"))
    vid2 = render_video(2, audio_len(f"{OUT_DIR}/part2_voice.mp3"))

    print("⬆️  Uploading …")
    upload(vid1, "LoreJump • Part 1", textwrap.shorten(part1, 100))
    upload(vid2, "LoreJump • Part 2", textwrap.shorten(part2, 100))
    print("✅ Done —", datetime.utcnow())

if __name__ == "__main__":
    main()
