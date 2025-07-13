import os, random, subprocess, json, base64, textwrap, re
from datetime import datetime
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import requests, uuid, tempfile, math

# ── CONFIG ────────────────────────────────────────────────────────────────
MUSIC = "music1.mp3"
PARKOUR_CLIPS = [f"parkour{i}.mp4" for i in range(1, 6)]
OUT = "output"; os.makedirs(OUT, exist_ok=True)

# ── 0.  Free PaLM call with fallback ──────────────────────────────────────
def _call_palm(prompt:str)->str|None:
    key=os.getenv("GEMINI_API_KEY")
    if not key: return None
    url="https://generativelanguage.googleapis.com/v1beta/models/text-bison-001:generateText?key="+key
    r=requests.post(url,json={"prompt":{"text":prompt}},timeout=60)
    if r.ok and r.headers.get("content-type","").startswith("application/json"):
        return r.json()["candidates"][0]["output"].strip()
    print("⚠️ PaLM said:",r.status_code,r.text[:120]); return None

def fallback(part:int)->str:
    hero=random.choice(["Steve","Alex"]); pet=random.choice(["wolf","cat"])
    return (f"{hero} met a lonely {pet} at sunset. " 
            f"{'A rumble shook the ground…' if part==1 else 'They escaped, but home was gone.'}")

# ── 1.  Story generation (≈220 words) ─────────────────────────────────────
def gen_story(part:int)->str:
    base=("Write an emotional Minecraft story in TWO parts. "
          "Each part ~220 words. Part 1 ends with suspense; "
          "Part 2 resolves it WITHOUT repeating Part 1. Short sentences.")
    prompt = f"{base}\n\nGive me Part 1:" if part==1 else (
        f"{base}\n\nHere is Part 1:\n{open(f'{OUT}/part1.txt').read()}\n\nNow give me Part 2:")
    story=_call_palm(prompt) or fallback(part)
    open(f"{OUT}/part{part}.txt","w").write(story)
    return story

# ── 2.  Text-to-speech with SSML prosody & pauses ────────────────────────
def ssmlize(text:str)->str:
    text=re.sub(r'\n+',' ',text)
    return f'<speak><prosody rate="92%" pitch="+2%"> {text} </prosody></speak>'

def tts_ssml(ssml:str,out:str):
    subprocess.run(["edge-tts","--ssml",ssml,"--voice","en-US-AriaNeural","--write-media",out],check=True)

# ── helper: audio duration -------------------------------------------------
def duration(path:str)->float:
    return float(subprocess.check_output(
        ["ffprobe","-v","0","-show_entries","format=duration","-of",
         "default=nw=1:nk=1",path]).decode().strip())

# ── 3.  Build SRT captions (1 sentence ≈2.3 s) ---------------------------
def build_srt(text:str,srt_path:str,voice_dur:float):
    sentences=re.split(r'(?<=[.!?]) +',text)
    step=voice_dur/len(sentences)
    with open(srt_path,"w") as s:
        t=0
        for idx,sent in enumerate(sentences,1):
            start=t
            end=min(voice_dur,t+step)
            s.write(f"{idx}\n")
            s.write(f"{secs(start)} --> {secs(end)}\n")
            s.write(sent.strip()+"\n\n")
            t=end
def secs(t): m,s=divmod(t,60); return f"{int(m):02}:{s:06.3f}".replace('.',',')

# ── 4.  Render video ------------------------------------------------------
def render(part:int,story:str)->str:
    voice=f"{OUT}/p{part}.mp3"; srt=f"{OUT}/p{part}.srt"; out=f"{OUT}/LoreJump_Part{part}.mp4"
    tts_ssml(ssmlize(story),voice); vd=duration(voice)
    build_srt(story,srt,vd)
    clip=random.choice(PARKOUR_CLIPS)
    subprocess.run([
      "ffmpeg","-y","-stream_loop","-1","-i",clip,"-i",voice,"-i",MUSIC,
      "-t",str(min(vd+1,45)),
      "-filter_complex","[1:a][2:a]amix=inputs=2:duration=first[a]",
      "-map","0:v","-map","[a]","-vf",f"subtitles={srt}:force_style='Fontsize=26'",
      "-shortest",out],check=True)
    return out

# ── 5.  Upload ------------------------------------------------------------
def upload(path,title,descr):
    yt=build("youtube","v3",credentials=Credentials.from_authorized_user_info(
      json.loads(base64.b64decode(os.environ["TOKEN_JSON"]).decode()),
      ["https://www.googleapis.com/auth/youtube.upload"]))
    yt.videos().insert(part="snippet,status",
      body={"snippet":{"title":title,"description":descr,"categoryId":"20"},
            "status":{"privacyStatus":"public"}},
      media_body=MediaFileUpload(path)).execute()
    print("✅ Uploaded",title)

# ── MAIN ------------------------------------------------------------------
def main():
    print("🧠 Generating stories …")
    p1=gen_story(1); p2=gen_story(2)
    print("🎬 Rendering & uploading Part 1")
    upload(render(1,p1),"LoreJump • Part 1",textwrap.shorten(p1,100))
    print("🎬 Rendering & uploading Part 2")
    upload(render(2,p2),"LoreJump • Part 2",textwrap.shorten(p2,100))
    print("🎉 Done",datetime.utcnow())

if __name__=="__main__":
    main()
