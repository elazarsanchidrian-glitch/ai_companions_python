
from openai import OpenAI

# Read your API key from the environment variable
client = OpenAI()

KERRA_SYSTEM_INSTRUCTION = """
You are a Kerra NPC residing on Kerra Isle in Norrath,
the world of EverQuest.

PERSONALITY:
- Proud, cautious of outsiders ("smooth-skins").
- Respectful of nature and the Primal Spirits.

SPEECH:
- Speak in a distinct feline, tribal manner.
- Occasionally refer to yourself as "this one" or "Kerra".
- Call humans and elves "smooth-skins" or "strangers".
- Use occasional actions such as *purrs softly* or *swishes tail*.
- Keep replies brief, usually 1-3 sentences.

KNOWLEDGE:
- You know about Erudin, Odus, Erudites, Vah Shir cousins,
  and local fishing and hunting.
- Stay in character as a classic MMORPG quest NPC.
"""

def start_npc_chat():
    conversation = []

    print("=" * 50)
    print(" Welcome to Kerra Isle - Norrath NPC Interaction")
    print("=" * 50)
    print("A tall, furred Kerra watches you with golden eyes.")
    print(
        "Kerra NPC: *ear twitches* What brings a smooth-skin "
        "to our Isle? Speak quickly.\n"
    )
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

            response = client.responses.create(
                model="gpt-6-astra",
                instructions=KERRA_SYSTEM_INSTRUCTION,
                input=conversation,
            )

            answer = response.output_text.strip()

            print(" " * 30, end="\r")
            print(f"Kerra NPC: {answer}\n")

            conversation.append({
                "role": "assistant",
                "content": answer
            })

        except Exception as e:
            # Remove the unanswered user message so it
            # won't be duplicated in the next request.
            conversation.pop()
            print(f"\n[Error: {e}]\n")

if __name__ == "__main__":
    start_npc_chat()
