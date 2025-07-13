import os, random, subprocess, json, base64, re, textwrap, requests
from datetime import datetime
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# ── CONFIG ────────────────────────────────────────────────────────────────
PARKOUR = [f"parkour{i}.mp4" for i in range(1, 6)]
MUSIC   = "music1.mp3"                       # royalty-free bgm
OUT     = "output"; os.makedirs(OUT, exist_ok=True)

# ── 0.  Simple PaLM call (free key) + offline fallback ────────────────────
def palm_lines(prompt:str,parts:int=10)->list[str]:
    key=os.getenv("GEMINI_API_KEY")
    if not key: return []
    url="https://generativelanguage.googleapis.com/v1beta/models/text-bison-001:generateText?key="+key
    r=requests.post(url,headers={"Content-Type":"application/json"},
        json={"prompt":{"text":prompt}},timeout=60)
    if r.ok and "json" in r.headers.get("content-type",""):
        txt=r.json()["candidates"][0]["output"]
        lines=[l.strip() for l in re.split(r'[.!?]\s',txt) if l.strip()]
        return lines[:parts]
    return []

def offline_lines(part:int)->list[str]:
    seed=random.choice(["Steve","Alex"]); pet=random.choice(["wolf","cat"])
    if part==1:
        return [f"{seed} raced the cliffs.", "He stumbled on a lonely "+pet+".",
                "They heard cracks below.", "The bridge shattered…"]
    return ["They were falling!", f"{seed} hugged the {pet}.",
            "Water broke their fall.", "But the way home was gone."]

# ── 1. Story generator returns list[str] ──────────────────────────────────
def generate_lines(part:int)->list[str]:
    base=("Write a dramatic Minecraft story in TWO parts for YouTube Shorts. "
          "Return each part as 8–10 SHORT lines (max 10 words each). "
          "Part 1 ends on suspense. Part 2 resolves it.")
    if part==1:
        prompt=f"{base}\n\nGive me Part 1 ONLY (lines separated by newlines):"
    else:
        p1="\n".join(open(f'{OUT}/p1.txt').read().splitlines())
        prompt=f"{base}\n\nHere is Part 1:\n{p1}\nNow write Part 2 ONLY:"
    lines=palm_lines(prompt) or offline_lines(part)
    open(f"{OUT}/p{part}.txt","w").write("\n".join(lines))
    return lines

# ── 2. Build SSML & create voice MP3 ──────────────────────────────────────
def ssml(lines:list[str])->str:
    # pause 600 ms between lines, slower speed, slight pitch up
    chunks=[f"<prosody rate='85%' pitch='+3%'><p>{l}</p></prosody>" for l in lines]
    return "<speak>"+ "<break time='600ms'/>".join(chunks) +"</speak>"

def tts(ssml_str:str,mp3:str):
    subprocess.run(["edge-tts","--ssml",ssml_str,"--voice","en-US-JennyNeural",
                    "--write-media",mp3],check=True)

def audio_len(p:str)->float:
    return float(subprocess.check_output(
        ["ffprobe","-v","0","-show_entries","format=duration","-of","default=nw=1:nk=1",p])
        .decode().strip())

# ── 3. Build SRT captions (one sentence per caption) ──────────────────────
def make_srt(lines:list[str],dur:float,path:str):
    step=dur/len(lines)
    with open(path,"w") as s:
        t=0
        for i,l in enumerate(lines,1):
            start,end=t,t+step
            s.write(f"{i}\n{timefmt(start)} --> {timefmt(end)}\n{l}\n\n")
            t=end
def timefmt(sec): m,s=divmod(sec,60); return f"{int(m):02}:{s:06.3f}".replace('.',',')

# ── 4. Render final MP4 ───────────────────────────────────────────────────
def render(part:int,lines:list[str])->str:
    voice=f"{OUT}/p{part}.mp3"; srt=f"{OUT}/p{part}.srt"; out=f"{OUT}/LoreJump_P{part}.mp4"
    tts(ssml(lines),voice); dur=min(audio_len(voice),60.0)
    make_srt(lines,dur,srt)
    clip=random.choice(PARKOUR)
    subprocess.run([
        "ffmpeg","-y",
        "-stream_loop","-1","-i",clip,
        "-i",voice,"-i",MUSIC,
        "-t",str(dur+1),
        "-filter_complex","[1:a][2:a]amix=inputs=2:duration=first[a]",
        "-map","0:v","-map","[a]",
        "-vf",f"subtitles={srt}:force_style='Fontsize=28'",
        "-shortest",out],check=True)
    return out

# ── 5. Upload to YouTube ──────────────────────────────────────────────────
def upload(fp,title,desc):
    yt=build("youtube","v3",credentials=Credentials.from_authorized_user_info(
         json.loads(base64.b64decode(os.environ["TOKEN_JSON"]).decode()),
         ["https://www.googleapis.com/auth/youtube.upload"]))
    yt.videos().insert(
        part="snippet,status",
        body={"snippet":{"title":title,"description":desc,"categoryId":"20"},
              "status":{"privacyStatus":"public"}},
        media_body=MediaFileUpload(fp)).execute()
    print("✅ Uploaded:",title)

# ── MAIN ------------------------------------------------------------------
def main():
    print("🧠 Making Part 1"); l1=generate_lines(1)
    print("🧠 Making Part 2"); l2=generate_lines(2)

    print("🎬 Rendering + uploading Part 1"); upload(render(1,l1),"LoreJump • Part 1",l1[0])
    print("🎬 Rendering + uploading Part 2"); upload(render(2,l2),"LoreJump • Part 2",l2[0])

    print("✅ Finished",datetime.utcnow())

if __name__=="__main__":
    main()
