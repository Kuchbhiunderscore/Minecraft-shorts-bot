import os import random import subprocess import json from datetime import datetime from google.oauth2.credentials import Credentials from googleapiclient.discovery import build as youtube_build from googleapiclient.http import MediaFileUpload import requests

Constants

OUT_DIR = "output" MUSIC_FILE = "music1.mp3" VIDEO_FILE = "parkour3.mp4" VOICES = ["en-US-JennyNeural", "en-US-GuyNeural", "en-GB-SoniaNeural"]

Ensure output directory exists

os.makedirs(OUT_DIR, exist_ok=True)

Gemini fallback stories

FALLBACK_STORIES = [ "Dad worked hard, but his son never understood. One day, roles reversed.", "A rich girl mocked a poor boy. Years later, she begged him for a job.", "Brother stole from sister. She forgave. He saved her life one day." ]

def generate_story(): prompt = "Write a very short, emotional story (under 500 characters) involving family, siblings, or rich vs poor. Format for voice narration." try: response = requests.post( "https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent", headers={"Content-Type": "application/json"}, params={"key": os.environ["GEMINI_API_KEY"]}, json={"contents": [{"parts": [{"text": prompt}]}]} ) result = response.json() story = result["candidates"][0]["content"]["parts"][0]["text"] if "def" in story or "{" in story: raise ValueError("Gemini responded with code instead of a story.") return story.strip() except Exception as e: print(f"⚠️  Gemini failed, using fallback.\nReason: {e}") return random.choice(FALLBACK_STORIES)

def split_lines(text): return [(line.strip(), random.choice(VOICES)) for line in text.split('.') if line.strip()]

def ssml(lines):
    blocks = [f'<voice name="{v}"><p>{l}.</p></voice>' for l, v in lines]
    return f"<speak><prosody rate='85%' pitch='+3%'>{'<break time=\"600ms\"/>'.join(blocks)}</prosody></speak>"

def tts(ssml_text, path): subprocess.run([ "edge-tts", "--ssml", ssml_text, "--voice", "en-US-JennyNeural", "--write-media", path ], check=True)

def audio_len(path): cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", path] return float(subprocess.check_output(cmd).decode().strip())

def render_video(): voice_path = f"{OUT_DIR}/voice.mp3" video_path = f"{OUT_DIR}/final.mp4" subprocess.run([ "ffmpeg", "-y", "-i", VIDEO_FILE, "-i", voice_path, "-i", MUSIC_FILE, "-filter_complex", "[1:a]volume=1[a1];[2:a]volume=0.05[a2];[a1][a2]amix=inputs=2:duration=first:dropout_transition=2", "-map", "0:v", "-map", "[aout]", "-c:v", "libx264", "-preset", "fast", "-crf", "23", "-c:a", "aac", "-shortest", video_path ], check=True) return video_path

def upload(path, title, desc): creds = Credentials.from_authorized_user_info(json.loads(os.environ["YT_CREDENTIALS"])) youtube = youtube_build("youtube", "v3", credentials=creds) request = youtube.videos().insert( part="snippet,status", body={ "snippet": {"title": title, "description": desc, "tags": ["shorts"]}, "status": {"privacyStatus": "public"} }, media_body=MediaFileUpload(path) ) request.execute()

def main(): print("🧠 Generating story …") story = generate_story() lines = split_lines(story)

print("🎙️  Synthesizing voices …")
tts(ssml(lines), f"{OUT_DIR}/voice.mp3")

print("🎞️  Rendering video …")
video_path = render_video()

print("⬆️  Uploading …")
upload(video_path, "LoreJump • Emotional Short", lines[0][0])

if name == "main": main()

