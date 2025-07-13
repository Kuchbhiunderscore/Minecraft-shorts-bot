import os, random, subprocess, json, base64, textwrap
from datetime import datetime
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import requests

# === CONFIG ============================================================= #
MUSIC = "music1.mp3"
PARKOUR_CLIPS = [f"parkour{i}.mp4" for i in range(1, 6)]
OUT_DIR = "output"
os.makedirs(OUT_DIR, exist_ok=True)

# === 0.  GEMINI / PaLM helper  +  offline fallback ====================== #
def call_gemini(prompt: str) -> str | None:
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        return None
    url = (
        "https://generativelanguage.googleapis.com/"
        "v1beta/models/text-bison-001:generateText?key=" + key
    )
    r = requests.post(url, headers={"Content-Type": "application/json"},
                      json={"prompt": {"text": prompt}}, timeout=60)
    if r.ok and r.headers.get("content-type","").startswith("application/json"):
        return r.json()["candidates"][0]["output"].strip()
    print("⚠️ Gemini/PaLM replied:", r.status_code, r.text[:150])
    return None

def offline_stub(part:int)->str:
    hero,pet=random.choice(["Steve","Alex","Noob"]),random.choice(["wolf","cat","parrot"])
    return (
      f"{hero} raced across the cliffs with his loyal {pet}. "
      f"{'Suddenly the path crumbled…' if part==1 else 'They survived, but the price was their home.'}"
    )

# === 1. STORY GENERATION =============================================== #
def generate_story(part:int)->str:
    base=("Write a sad Minecraft story in 2 parts. "
          "Each part ≈150 words. Part 1 ends on cliff-hanger, Part 2 resolves it.")
    prompt =(f"{base}\n\nGive me Part 1:"
             if part==1 else
            f"{base}\n\nHere is Part 1:\n{open(f'{OUT_DIR}/part1_story.txt').read()}\n\nNow give me Part 2:")
    story=call_gemini(prompt) or offline_stub(part)
    with open(f"{OUT_DIR}/part{part}_story.txt","w") as f: f.write(story)
    return story

# === 2. TTS + helper ==================================================== #
def tts(text:str,out_mp3:str):
    subprocess.run(["edge-tts","--text",text,"--voice","en-US-AriaNeural",
                    "--write-media",out_mp3],check=True)

def audio_len(path:str)->float:
    cmd=["ffprobe","-v","error","-show_entries","format=duration",
         "-of","default=nw=1:nk=1",path]
    return float(subprocess.check_output(cmd).decode().strip())

# === 3. RENDER VIDEO (loops clip, matches voice length) ================ #
def render_video(part:int)->str:
    clip  = random.choice(PARKOUR_CLIPS)
    music = MUSIC
    voice = f"{OUT_DIR}/part{part}_voice.mp3"
    story = f"{OUT_DIR}/part{part}_story.txt"
    out   = f"{OUT_DIR}/LoreJump_Part{part}.mp4"

    # create voice-over
    with open(story) as fp: tts(fp.read(), voice)
    dur = min(audio_len(voice), 45.0)

    subprocess.run([
        "ffmpeg","-y",
        "-stream_loop","-1","-i",clip,
        "-i",voice,"-i",music,
        "-t",str(dur+1),
        "-filter_complex","[1:a][2:a]amix=inputs=2:duration=first[a]",
        "-map","0:v","-map","[a]",
        "-shortest",out
    ],check=True)
    return out, dur

# === 4. UPLOAD ========================================================== #
def upload(path,title,descr):
    creds=Credentials.from_authorized_user_info(
        json.loads(base64.b64decode(os.environ["TOKEN_JSON"]).decode()),
        ["https://www.googleapis.com/auth/youtube.upload"])
    yt=build("youtube","v3",credentials=creds)
    resp=yt.videos().insert(
        part="snippet,status",
        body={"snippet":{"title":title,"description":descr,"categoryId":"20"},
              "status":{"privacyStatus":"public"}},
        media_body=MediaFileUpload(path)).execute()
    print("✅ Uploaded:",resp["id"])

# === 5. MAIN ============================================================ #
def main():
    print("🧠 Generating stories …")
    p1=generate_story(1)
    p2=generate_story(2)

    print("🎬 Rendering Part 1 …")
    v1,_=render_video(1)
    upload(v1,"LoreJump • Part 1",textwrap.shorten(p1,100))

    print("🎬 Rendering Part 2 …")
    v2,_=render_video(2)
    upload(v2,"LoreJump • Part 2",textwrap.shorten(p2,100))

    print("✅ Done",datetime.utcnow())

if __name__=="__main__":
    main()
