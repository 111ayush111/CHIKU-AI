import threading
import speech_recognition as sr
import pyttsx3
import asyncio
import edge_tts
import tempfile
import os
import pygame
import time
from groq import Groq

# ===================== GROQ SETUP =====================
API_KEY = "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"
client = Groq(api_key=API_KEY)

# ===================== SPEECH ENGINE =====================
engine = pyttsx3.init()
# Fallback faster, more natural voice if available
for v in engine.getProperty("voices"):
    if "prabhat" in v.name.lower() or "india" in v.name.lower():
        engine.setProperty("voice", v.id)
        break

recognizer = sr.Recognizer()
VOICE = "en-IN-PrabhatNeural"  # Indian male neural voice
TTS_RATE = "+20%"              # Faster speech

pygame.mixer.init()
current_channel = None
is_speaking = False
stop_talking = False
speak_thread = None

# Shared query variable and lock
user_query = None
query_lock = threading.Lock()

def stop_speech():
    global stop_talking, current_channel, is_speaking
    stop_talking = True
    if current_channel and current_channel.get_busy():
        current_channel.stop()
    is_speaking = False

async def _speak_async(text):
    global is_speaking, stop_talking, current_channel
    is_speaking = True
    stop_talking = False

    # Single chunk synthesis (no split) for speed
    communicate = edge_tts.Communicate(text.replace("*",""), VOICE, rate=TTS_RATE)
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                tmp.write(chunk["data"])
        path = tmp.name

    if not stop_talking:
        sound = pygame.mixer.Sound(path)
        current_channel = sound.play()
        while current_channel.get_busy():
            if stop_talking:
                current_channel.stop()
                break
            await asyncio.sleep(0.05)

    os.remove(path)
    is_speaking = False

def speak(text):
    global speak_thread
    # Wait for any ongoing speech to finish
    if speak_thread and speak_thread.is_alive():
        speak_thread.join()
    speak_thread = threading.Thread(
        target=lambda: asyncio.run(_speak_async(text)), daemon=True
    )
    speak_thread.start()

def wake_and_listen():
    """Continuously listen for 'chiku' then capture one query."""
    global user_query
    mic = sr.Microphone()
    while True:
        with mic as src:
            recognizer.adjust_for_ambient_noise(src, duration=0.15)
            try:
                audio = recognizer.listen(src, timeout=1, phrase_time_limit=2)
                phrase = recognizer.recognize_google(audio).strip().lower()
                if phrase == "chiku":
                    with query_lock:
                        print("🗣️ Wake word 'chiku' detected. Listening for your question...")
                        audio2 = recognizer.listen(src, timeout=4, phrase_time_limit=6)
                        q = recognizer.recognize_google(audio2).strip()
                        print(f"🧑 You: {q}")
                        user_query = q
            except:
                pass

def get_ai_response(text):
    try:
        r = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role":"user","content":text}],
            max_tokens=150, temperature=0.7
        )
        return r.choices[0].message.content.replace("*","")
    except Exception as e:
        return f"⚠️ API Error: {e}"

def ai_chat():
    global user_query
    print("🤖 AI Assistant Started. Say 'chiku' to wake me.")
    threading.Thread(target=wake_and_listen, daemon=True).start()

    while True:
        # Wait for a new query
        with query_lock:
            q = user_query
            user_query = None

        if not q:
            time.sleep(0.1)
            continue

        # Greeting logic
        if q.lower() in ["hi","hello","hey","good morning","good afternoon"]:
            resp = "Hello! What would you like to talk about?"
        else:
            resp = get_ai_response(q)

        print(f"🤖 AI: {resp}")
        speak(resp)

if __name__ == "__main__":
    ai_chat()
