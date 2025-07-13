import os import random import subprocess import json import base64 from datetime import datetime from google.oauth2.credentials import Credentials from googleapiclient.discovery import build from googleapiclient.http import MediaFileUpload import requests

=== CONFIG ===

MUSIC = "music1.mp3" OUT_DIR = "output" PARKOUR_CLIPS = [f"parkour{i}.mp4" for i in range(1, 6)] CHAR_VOICES = { "Dad": "en-US-GuyNeural", "Son": "en-US-JennyNeural", "Sister": "en-US-AriaNeural", "Mom": "en-US-AnaNeural", "Narrator": "en-US-EmmaNeural" }

os.makedirs(OUT_DIR, exist_ok=True)

def get_story(): prompt = ( "Write a very short story under 5 sentences." " The story must be emotional or funny." " It must be real-life inspired, like about family, dad/son, sister/brother, rich/poor, sad or funny, etc." " Add clear speaking lines with character names before each line." " Example:\nDad: Where have you been?\nSon: Just playing outside.\n..." ) api_key = os.getenv("GEMINI_API_KEY") url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={api_key}" payload = {"contents": [{"parts": [{"text": prompt}]}]} res = requests.post(url, headers={"Content-Type": "application/json"}, json=payload) try: return res.json()['candidates'][0]['content']['parts'][0]['text'] except: print("⚠️  Gemini responded 404 :", res.text) return ( "Dad: Why are you late?\n" "Son: I was helping a homeless man.\n" "Dad: I’m proud of you.\n" "Son: He reminded me of Grandpa…\n" "Dad: Let's go give him dinner together." )

def save_lines(part: int, story: str) -> list: lines = [] with open(f"{OUT_DIR}/part{part}.txt", "w") as f: for line in story.splitlines(): if ':' in line: role, line = line.split(':', 1) lines.append((role.strip(), line.strip())) f.write(f"{role.strip()}: {line.strip()}\n") return lines

def ssml(lines): parts = [] for role, line in lines: voice = CHAR_VOICES.get(role, CHAR_VOICES['Narrator']) parts.append(f"<voice name="{voice}"><p>{line}</p></voice>") return f"<speak>{''.join(parts)}</speak>"

def tts(ssml_str, out): subprocess.run([ "edge-tts", "--ssml", ssml_str, "--voice", "en-US-JennyNeural", "--write-media", out ], check=True)

def audio_len(mp3): return float(subprocess.check_output([ "ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", mp3 ]).decode().strip())

def render(part: int, duration: float): clip = random.choice(PARKOUR_CLIPS) voice = f"{OUT_DIR}/p{part}.mp3" out = f"{OUT_DIR}/final{part}.mp4" subprocess.run([ "ffmpeg", "-y", "-i", clip, "-i", voice, "-i", MUSIC, "-filter_complex", "[1:a][2:a]amix=inputs=2:duration=first:dropout_transition=2,volume=1.5[a]", "-map", "0:v", "-map", "[a]", "-t", str(duration), "-shortest", out ], check=True) return out

def upload(video, title, descr): creds_json = base64.b64decode(os.getenv("TOKEN_JSON")).decode() creds = Credentials.from_authorized_user_info(json.loads(creds_json), ["https://www.googleapis.com/auth/youtube.upload"]) yt = build("youtube", "v3", credentials=creds) req = yt.videos().insert( part="snippet,status", body={ "snippet": { "title": title, "description": descr, "tags": ["shorts", "emotional", "story", "voiceover"], "categoryId": "22" }, "status": {"privacyStatus": "public"} }, media_body=MediaFileUpload(video) ) resp = req.execute() print("✅ Uploaded to YouTube:", resp['id'])

def main(): print("🧠 Making Part 1") part1_lines = save_lines(1, get_story()) tts(ssml(part1_lines), f"{OUT_DIR}/p1.mp3") print("🎬 Rendering + uploading Part 1") upload(render(1, audio_len(f"{OUT_DIR}/p1.mp3")), "LoreJump • Part 1", part1_lines[0][1])

print("🧠 Making Part 2")
part2_lines = save_lines(2, get_story())
tts(ssml(part2_lines), f"{OUT_DIR}/p2.mp3")
print("🎬 Rendering + uploading Part 2")
upload(render(2, audio_len(f"{OUT_DIR}/p2.mp3")), "LoreJump • Part 2", part2_lines[0][1])

if name == "main": main()

