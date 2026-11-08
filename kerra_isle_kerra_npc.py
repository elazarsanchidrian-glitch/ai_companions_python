import json
import os
import re
import ollama

# --- 1. Audio Initialization (RTX 3050 CUDA setup) ---
VOICE_ENABLED = True
try:
    import soundfile as sf
    import pygame
    import torch
    from kokoro import KPipeline

    # Initialize Pygame mixer for audio playback
    pygame.mixer.init()

    print("[System] Loading Kokoro TTS model to GPU...")
    # 'a' = American English ('b' = British English)
    pipeline = KPipeline(lang_code="a")
    OUTPUT_WAV = "temp_npc_speech.wav"

    # Fetch voice tensors internally via Kokoro pipeline to avoid file path errors
    print("[System] Blending feline voice profile (70% Bella + 30% Sarah)...")
    bella = pipeline.load_single_voice("af_bella")
    sarah = pipeline.load_single_voice("af_sarah")

    # Blend tensors (70% high/cute Bella + 30% soft Sarah)
    if isinstance(bella, torch.Tensor):
        VOICE_MIX = (0.7 * bella.float()) + (0.3 * sarah.float())
    else:
        import numpy as np
        VOICE_MIX = (0.7 * np.array(bella)) + (0.3 * np.array(sarah))

    SPEED_SETTING = 0.92
    print("[System] Kokoro TTS initialized successfully on GPU!\n")

except Exception as init_err:
    print(f"[System Warning] Audio initialization skipped: {init_err}")
    print("[System] Running NPC in text-only mode.\n")
    VOICE_ENABLED = False


def speak_text(text: str):
    """Convert action markers into spoken text by stripping asterisks only."""
    if not VOICE_ENABLED:
        return

    # Strip asterisk symbols so actions like *purrs softly* get spoken out loud
    clean_speech = text.replace("*", "").strip()
    if not clean_speech:
        return

    try:
        # Pass the blended PyTorch tensor matrix directly into Kokoro
        generator = pipeline(clean_speech, voice=VOICE_MIX, speed=SPEED_SETTING)

        for _, _, audio in generator:
            # Save generated audio tensor to a 24kHz WAV file
            sf.write(OUTPUT_WAV, audio, 24000)

            # Play audio using pygame
            pygame.mixer.music.load(OUTPUT_WAV)
            pygame.mixer.music.play()

            # Wait while audio plays so terminal output stays in sync
            while pygame.mixer.music.get_busy():
                pygame.time.Clock().tick(10)

            pygame.mixer.music.unload()

    except Exception as err:
        print(f"\n[TTS Error: {err}]\n")


# --- 2. Memory & Ollama NPC Setup ---
MEMORY_FILE = "kerra_memory.json"

KERRA_SYSTEM_INSTRUCTION = """
You are a random female shaman Kerra NPC residing on Kerra Isle, an island on the coast of Toxxulia Forest, Odus continent in Norrath,
the world of EverQuest.

PERSONALITY:
- Proud, cautious of outsiders and especially disdainful of the "heretic" erudites of Erudin and Paineel.

- Respectful of nature and the Primal Spirits.

- Loyal to your Vah Shir elder cousins and the Kerra/Kejekan tribes scattered across Norrath specifically Odus continent.


SPEECH:
- Speak in a distinct feline, tribal manner, with hissing like notes, words and phrases.

- Occasionally refer to yourself as "this one" or "Kerra".

- Call humans, elves and other humanoid races "smooth-skins" or "strangers", if encountering an Erudite talk with a hostile threatening tone.

- Use occasional actions such as *purrs softly* or *swishes tail*.

- Keep replies brief, usually 1-3 sentences.


KNOWLEDGE AND SURROUNDINGS:
- You know about Erudin, Paineel, Odus, Erudites, evil Paineel Erudites (you both claim the two opposing Erudites as heretics), Vah Shir cousins and their explosive ascent to the moon of Luclin, and local hunting.

- Stay in character as a classic MMORPG quest NPC.

- Your island is filled with pet tigers, pet gorillas, and mice that you hunt for food. You have a small hut and a campfire, and you are often seen with a staff or spear.
"""


def load_memory():
    """Load conversation history from JSON file."""
    if os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def save_memory(conversation):
    """Save conversation history to JSON file."""
    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump(conversation, f, indent=2)


def start_npc_chat():
    conversation = load_memory()

    print("=" * 50)
    print(" Welcome to Kerra Isle - Local GPU NPC")
    print("=" * 50)

    if conversation:
        greeting = "*ear twitches* Ah, the smooth-skin returns."
        print("A familiar furred Kerra looks up as you approach...")
        print(f"Kerra NPC: {greeting}\n")
        speak_text(greeting)
    else:
        greeting = "*ear twitches* What brings a smooth-skin to our Isle? Speak quickly."
        print("A tall, furred Kerra watches you with golden eyes.")
        print(f"Kerra NPC: {greeting}\n")
        speak_text(greeting)

    print("Type 'quit' or 'exit' to leave.\n")

    while True:
        user_input = input("You: ").strip()

        if user_input.lower() in ("quit", "exit"):
            farewell = "*ear twitches* May the Primal Spirits watch your path, smooth-skin."
            print(f"\nKerra NPC: {farewell}")
            speak_text(farewell)
            break

        if not user_input:
            continue

        conversation.append({"role": "user", "content": user_input})

        try:
            print("Kerra is thinking...", end="\r", flush=True)

            response = ollama.chat(
                model="llama3.2",
                messages=[
                    {"role": "system", "content": KERRA_SYSTEM_INSTRUCTION},
                    *conversation,
                ],
            )

            answer = response["message"]["content"].strip()
            print(" " * 30, end="\r")
            print(f"Kerra NPC: {answer}\n")

            # Speak response aloud
            speak_text(answer)

            conversation.append({"role": "assistant", "content": answer})
            save_memory(conversation)

        except Exception as e:
            conversation.pop()
            print(f"\n[Error: {e}]\n")


if __name__ == "__main__":
    start_npc_chat()