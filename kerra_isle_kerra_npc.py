import json
import os
import re
import ollama

# --- 1. Audio Initialization (RTX 3050 CUDA setup) ---
VOICE_ENABLED = True
try:
    import soundfile as sf
    import pygame
    from kokoro import KPipeline

    # Initialize Pygame mixer for audio playback
    pygame.mixer.init()

    print("[System] Loading Kokoro TTS model to RTX 3050...")
    # 'a' = American English ('b' = British English)
    pipeline = KPipeline(lang_code="a")
    OUTPUT_WAV = "temp_npc_speech.wav"
    print("[System] Kokoro TTS initialized successfully on GPU!\n")

except Exception as init_err:
    print(f"[System Warning] Audio initialization skipped: {init_err}")
    print("[System] Running NPC in text-only mode.\n")
    VOICE_ENABLED = False


# Configured for a feline, tribal undertone (blended voice + slower pace)
VOICE_NAME = "bm_fable"
SPEED_SETTING = 0.90


def speak_text(text: str):
    """Clean action markers, run through Kokoro on GPU, and play audio."""
    if not VOICE_ENABLED:
        return

    # Strip action descriptions inside asterisks so TTS only speaks dialogue
    clean_speech = re.sub(r"\*.*?\*", "", text).strip()
    if not clean_speech:
        return

    try:
        # Pass the blended voice name and slower feline pace setting
        generator = pipeline(clean_speech, voice=VOICE_NAME, speed=SPEED_SETTING)

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
You are a random Kerra NPC residing on Kerra Isle, an island on the coast of Toxxulia Forest, Odus continent in Norrath,
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

KNOWLEDGE:
- You know about Erudin, Paineel, Odus, Erudites, evil Paineel Erudites (you both claim the two opposing Erudites as heretics), Vah Shir cousins and their explosive ascent to the moon of Luclin, and local hunting.
- Stay in character as a classic MMORPG quest NPC.
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