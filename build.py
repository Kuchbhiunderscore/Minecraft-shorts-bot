import os
import random
import subprocess
from datetime import datetime

# === CONFIG ===
MUSIC = "music1.mp3"
PARKOUR_CLIPS = [f"parkour{i}.mp4" for i in range(1, 6)]
OUT_DIR = "output"
ASSETS_DIR = "assets"
PROMPT_FILE = "prompt.txt"

# === CREATE OUTPUT FOLDER ===
os.makedirs(OUT_DIR, exist_ok=True)

# === GENERATE STORY (PART 1 & 2) ===
def generate_story(part):
    with open(PROMPT_FILE, "r") as f:
        base_prompt = f.read()

    prompt = f"{base_prompt}\n\nWrite part {part} of the story:"
    response = f"This is auto-generated story Part {part}."  # placeholder
    with open(f"{OUT_DIR}/part{part}_story.txt", "w") as f:
        f.write(response)
    return response

# === TEXT TO SPEECH (USING PYTTSX3 OR EDGE TTS) ===
def text_to_speech(text, output_file):
    subprocess.run([
        "edge-tts",
        "--text", text,
        "--voice", "en-US-AriaNeural",
        "--write-media", output_file
    ])

# === GENERATE VIDEO ===
def combine_video(part):
    clip = random.choice(PARKOUR_CLIPS)
    story_file = f"{OUT_DIR}/part{part}_story.txt"
    audio_file = f"{OUT_DIR}/part{part}_voice.mp3"
    output = f"{OUT_DIR}/LoreJump_Part{part}.mp4"

    # Voice generation
    with open(story_file, "r") as f:
        story_text = f.read()
    text_to_speech(story_text, audio_file)

    # Combine video + audio + music (simple)
    subprocess.run([
        "ffmpeg", "-y",
        "-i", clip,
        "-i", audio_file,
        "-i", MUSIC,
        "-filter_complex", "[1:a][2:a]amix=inputs=2:duration=first[a]",
        "-map", "0:v", "-map", "[a]",
        "-shortest",
        output
    ])
    return output

# === MAIN ===
def main():
    print("🧠 Generating story...")
    part1 = generate_story(1)
    part2 = generate_story(2)

    print("🔊 Generating video for Part 1...")
    combine_video(1)
    print("🎥 Part 1 done.")

    print("🔊 Generating video for Part 2...")
    combine_video(2)
    print("🎥 Part 2 done.")

    print("✅ All done at", datetime.now())

if __name__ == "__main__":
    main()
    
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import json, base64, os

def upload_video(path, title, descr, tags):
    token_json = base64.b64decode(os.environ["TOKEN_JSON"]).decode()
    creds = Credentials.from_authorized_user_info(
        json.loads(token_json),
        ["https://www.googleapis.com/auth/youtube.upload"]
    )
    youtube = build("youtube", "v3", credentials=creds)

    request = youtube.videos().insert(
        part="snippet,status",
        body={
            "snippet": {
                "title": title,
                "description": descr,
                "tags": tags,
                "categoryId": "20"
            },
            "status": {
                "privacyStatus": "public"
            }
        },
        media_body=MediaFileUpload(path)
    )
    response = request.execute()
    print("✅ Uploaded to YouTube:", response["id"])
