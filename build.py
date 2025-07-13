import os import random import subprocess import json import base64 from datetime import datetime from google.oauth2.credentials import Credentials from googleapiclient.discovery import build as youtube_build from googleapiclient.http import MediaFileUpload import requests

Constants

OUT_DIR = "output" MUSIC_FILE = "music1.mp3" VIDEO_FILE = "parkour3.mp4" VOICES = ["en-US-JennyNeural", "en-US-GuyNeural", "en-GB-SoniaNeural"]

os.makedirs(OUT_DIR, exist_ok=True)

def generate_emotional_story(): prompt = ( "Write a short emotional story in spoken English style (not written like code). " "Use natural, expressive language. It should be dramatic or touching and fit in a 40-second narration. " "Topics can include family, siblings, rich vs poor, bullying, or unexpected kindness. " "Avoid mentioning Minecraft, technology, or programming. Keep it cinematic." ) try: response = requests.post( "https://api-inference.huggingface.co/models/mistralai/Mistral-7B-Instruct-v0.2", headers={"Authorization": f"Bearer {os.getenv('HUGGINGFACE_TOKEN')}"}, json={"inputs": prompt}, timeout=60 ) response.raise_for_status() return response.json()[0]['generated_text'] except Exception as e: print(f"⚠️  Gemini failed, using fallback.\n{e}") return ( "Sarah lived with her little brother Max. They barely had anything, but shared everything. " "One day, Max gave Sarah his only toy so she could smile again. Sarah cried—not because she was sad, " "but because love had no price." )

def split_lines(story): return [(random.choice(VOICES), line.strip()) for line in story.strip().split('.') if line.strip()]

def ssml(lines): blocks = [f"<voice name='{voice}'><p>{line}</p></voice><break time='600ms'/>" for voice, line in lines] return f"<speak><prosody rate='85%' pitch='+3%'>{''.join(blocks)}</prosody></speak>"

def tts(ssml_str, output_path): subprocess.run([ "edge-tts", "--ssml", ssml_str, "--write-media", output_path ], check=True)

def audio_len(audio_path): cmd = [ "ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", audio_path ] return float(subprocess.check_output(cmd).decode().strip())

def render(video_path, voice_path, music_path, output_path): cmd = [ "ffmpeg", "-y", "-i", video_path, "-i", voice_path, "-i", music_path, "-filter_complex", "[1:a]volume=1.0[a1]; [2:a]volume=0.05[a2]; [a1][a2]amix=inputs=2:duration=first[aout]", "-map", "0:v", "-map", "[aout]", "-c:v", "libx264", "-c:a", "aac", "-strict", "experimental", output_path ] subprocess.run(cmd, check=True)

def upload(video_file, title, description): creds_data = json.loads(os.getenv("YT_CREDENTIALS")) creds = Credentials.from_authorized_user_info(creds_data) youtube = youtube_build("youtube", "v3", credentials=creds) request = youtube.videos().insert( part="snippet,status", body={ "snippet": { "title": title, "description": description, "tags": ["shorts", "emotional story", "sad story"], "categoryId": "22" }, "status": {"privacyStatus": "public"} }, media_body=MediaFileUpload(video_file) ) request.execute()

def main(): print("🧠 Generating story …") story = generate_emotional_story() lines = split_lines(story)

print("🎙️  Synthesizing voices …")
ssml_content = ssml(lines)
voice_path = f"{OUT_DIR}/voice.mp3"
tts(ssml_content, voice_path)

print("🎞️  Rendering video …")
video_path = f"{OUT_DIR}/final.mp4"
render(VIDEO_FILE, voice_path, MUSIC_FILE, video_path)

print("⬆️  Uploading …")
upload(video_path, "LoreJump • Emotional Short", lines[0][1])

if name == "main": main()

