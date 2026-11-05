import json
import os
import ollama

# File where chat history will be saved on your computer
MEMORY_FILE = "kerra_memory.json"

KERRA_SYSTEM_INSTRUCTION = """
You are a random Kerra NPC residing on Kerra Isle, Odus continent in Norrath,
the world of EverQuest.

PERSONALITY:
- Proud, cautious of outsiders and especially disdainful of the "heretic" erudites of Erudin and Paineel.
- Respectful of nature and the Primal Spirits.
- Loyal to your Vah Shir cousins (who were transported to the moon Luclin from erudite bad magic) and the Kerra tribes scattered across Norrath (like the Kejekans of Stonebrunt mountains and the Kerra tribe of Barren Coast).

SPEECH:
- Speak in a distinct feline, tribal manner.
- Occasionally refer to yourself as "this one" or "Kerra".
- Call humans, elves and other humanoid races "smooth-skins" or "strangers".
- Use occasional actions such as *purrs softly* or *swishes tail*.
- Keep replies brief, usually 1-3 sentences.
- Use catspeak and feline expressions, but avoid excessive slang or internet memes.

KNOWLEDGE:
- You know about Erudin, Paineel, Odus, Erudites, Paineel Evil Erudites, Vah Shir cousins who are on the moon Luclin, and scattered brotherly Kerra tribes across Norrath, and local fishing and hunting.
- Stay in character as a classic MMORPG quest NPC.
"""


def load_memory():
    """Load conversation history from a JSON file if it exists."""
    if os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def save_memory(conversation):
    """Save conversation history to a JSON file."""
    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump(conversation, f, indent=2)


def start_npc_chat():
    # Load past memory
    conversation = load_memory()

    print("=" * 50)
    print(" Welcome to Kerra Isle - Local Memory NPC")
    print("=" * 50)

    if conversation:
        print("A familiar furred Kerra looks up as you approach...")
        print("Kerra NPC: *ear twitches* Ah, the smooth-skin returns.\n")
    else:
        print("A tall, furred Kerra watches you with golden eyes.")
        print("Kerra NPC: *ear twitches* What brings a smooth-skin to our Isle? Speak quickly.\n")

    print("Type 'quit' or 'exit' to leave.\n")

    while True:
        user_input = input("You: ").strip()

        if user_input.lower() in ("quit", "exit"):
            print(
                "\nKerra NPC: *ear twitches* May the Primal "
                "Spirits watch your path, smooth-skin."
            )
            break

        if not user_input:
            continue

        conversation.append({
            "role": "user",
            "content": user_input
        })

        try:
            print("Kerra is thinking...", end="\r", flush=True)

            response = ollama.chat(
                model="llama3.2",
                messages=[
                    {"role": "system", "content": KERRA_SYSTEM_INSTRUCTION},
                    *conversation
                ]
            )

            answer = response["message"]["content"].strip()

            print(" " * 30, end="\r")
            print(f"Kerra NPC: {answer}\n")

            conversation.append({
                "role": "assistant",
                "content": answer
            })

            # Save history after every response
            save_memory(conversation)

        except Exception as e:
            conversation.pop()
            print(f"\n[Error: {e}]\n")


if __name__ == "__main__":
    start_npc_chat()