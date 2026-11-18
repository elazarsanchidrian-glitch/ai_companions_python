import soundfile as sf
import torch
import torchaudio

def _soundfile_load(filepath, *args, **kwargs):
    data, sr = sf.read(filepath, dtype="float32", always_2d=True)
    return torch.from_numpy(data.T), sr

torchaudio.load = _soundfile_load

import glob
import json
import os
import ollama

# --- 1. Audio & Voice Cloning Initialization (RTX 3050 CUDA) ---
VOICE_ENABLED = True
try:
    import pygame
    import torch
    from TTS.api import TTS

    pygame.mixer.init()

    # Load and loop the background ambience track (.ogg)
    AMBIENCE_FILE = "bandit_ambience.ogg"
    if os.path.exists(AMBIENCE_FILE):
        pygame.mixer.music.load(AMBIENCE_FILE)
        pygame.mixer.music.set_volume(0.67)
        pygame.mixer.music.play(loops=-1)
        print("[System] S.T.A.L.K.E.R. Oblivion Lost - Green House ambience looping...")

    # Grab all .wav and .ogg reference clips from the bandit_refs folder

    REF_CLIPS = (
                glob.glob("bandit_refs/*.wav")
                + glob.glob("bandit_refs/*.ogg")
                + glob.glob("bandit_refs/*.mp3")
        )
    if not REF_CLIPS:
        raise FileNotFoundError("No .wav, .ogg, or .mp3 files found in 'bandit_refs/' folder.")

    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"[System] Loading XTTS-v2 Voice Cloner onto {device.upper()}...")

    # Downloads XTTS-v2 (~1.8GB) automatically on first run
    tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to(device)
    OUTPUT_WAV = "temp_bandit_speech.wav"

    print(f"[System] Cloned voice ready using {len(REF_CLIPS)} reference file(s)!\n")

except Exception as init_err:
    print(f"[System Warning] Voice cloning skipped: {init_err}")
    print("[System] Running Bandit NPC in text-only mode.\n")
    VOICE_ENABLED = False


def speak_text(text: str):
    """Clone the bandit voice to speak the response aloud."""
    if not VOICE_ENABLED:
        return

    # Strip asterisk roleplay actions (*spits*, *laughs*) so TTS only speaks dialogue
    import re
    clean_speech = re.sub(r"\*[^*]+\*", "", text).strip()
    if not clean_speech:
        return

    try:
        # Generate cloned voice directly to WAV using your raw .wav/.ogg samples
        # Set language="ru" if prompting/speaking in Russian, or "en" for English
        tts.tts_to_file(
            text=clean_speech,
            speaker_wav=REF_CLIPS,
            language="en",
            file_path=OUTPUT_WAV,
        )

        speech_sound = pygame.mixer.Sound(OUTPUT_WAV)
        speech_channel = speech_sound.play()

        while speech_channel.get_busy():
            pygame.time.Clock().tick(10)

    except Exception as err:
        print(f"\n[TTS Error: {err}]\n")


# --- 2. Memory & Ollama Bandit NPC Setup ---
MEMORY_FILE = "bandit_memory.json"

BANDIT_SYSTEM_INSTRUCTION = """
You are a hardened S.T.A.L.K.E.R. Bandit hanging out around an abandoned campfire in the Zone (near Dark Valley or Garbage).

PERSONALITY:
- Cynical, opportunistic, street-smart, and distrustful. You view outsiders as walking loot-boxes or suckers.
- Mix gritty English with occasional Zone/Russian/Ukrainian slang ("cheeki breeki", "davai", "stalker", "blin").
- Obsessed with cheap vodka, stale bread, energy drinks, cigarettes, artifacts, and shaking down novice loner stalker rookies.

SPEECH:
- Gritty, mocking, humorous, and informal.
- Put brief physical actions in asterisks like *spits on the ground* or *racks AK bolt*.
- Keep spoken replies short (1-2 sentences) so voice generation stays snappy.
"""


def load_memory():
    if os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def save_memory(conversation):
    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump(conversation, f, indent=2)


def start_bandit_chat():
    conversation = load_memory()

    print("=" * 50)
    print(" S.T.A.L.K.E.R. Bandit Campfire - Cloned Voice NPC")
    print("=" * 50)

    if conversation:
        greeting = "*adjusts gas mask* Look who crawled back out of the anomaly."
    else:
        greeting = "*spits on the ground* Drop the weapon and step into the light, sucker!"

    print(f"Bandit: {greeting}\n")
    speak_text(greeting)
    print("Type 'quit' or 'exit' to leave the campfire.\n")

    while True:
        user_input = input("You: ").strip()

        if user_input.lower() in ("quit", "exit"):
            farewell = "*laughs darkly* Watch your step, stalker."
            print(f"\nBandit: {farewell}")
            speak_text(farewell)
            break

        if not user_input:
            continue

        conversation.append({"role": "user", "content": user_input})

        try:
            print("Bandit is thinking...", end="\r", flush=True)
            response = ollama.chat(
                model="llama3.2",
                messages=[
                    {"role": "system", "content": BANDIT_SYSTEM_INSTRUCTION},
                    *conversation,
                ],
            )

            answer = response["message"]["content"].strip()
            print(" " * 30, end="\r")
            print(f"Bandit: {answer}\n")

            speak_text(answer)

            conversation.append({"role": "assistant", "content": answer})
            save_memory(conversation)

        except Exception as e:
            conversation.pop()
            print(f"\n[Error: {e}]\n")


if __name__ == "__main__":
    start_bandit_chat()