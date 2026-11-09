"""Kerra Isle GUI: portrait, ambience, Ollama chat, Kokoro voice.
Keep this beside kerra_isle_kerra_npc.py, kerra.png and kerra_ambience.ogg.
"""
from pathlib import Path
import queue
import threading
import pygame

BASE = Path(__file__).resolve().parent
WIDTH, HEIGHT = 1000, 700
BG = (24, 30, 35)
PANEL = (37, 45, 51)
WHITE = (235, 238, 234)
MUTED = (167, 182, 177)
ACCENT = (120, 195, 155)

pygame.init()
if not pygame.mixer.get_init():
    pygame.mixer.init()
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Kerra Isle - AI Companion")
clock = pygame.time.Clock()
font = pygame.font.SysFont("arial", 21)
small = pygame.font.SysFont("arial", 17)
heading = pygame.font.SysFont("arial", 29, bold=True)

# Load portrait, keeping its aspect ratio.
portrait = pygame.image.load(str(BASE / "kerra.png")).convert_alpha()
pw, ph = portrait.get_size()
scale = min(400 / pw, 555 / ph)
portrait = pygame.transform.smoothscale(portrait, (int(pw * scale), int(ph * scale)))
portrait_rect = portrait.get_rect(center=(225, 325))

# Sound effects have their own mixer channel; Kokoro uses mixer.music.
ambience = pygame.mixer.Sound(str(BASE / "kerra_ambience.ogg"))
ambience.set_volume(0.25)
ambience_channel = pygame.mixer.Channel(1)
ambience_channel.play(ambience, loops=-1)

messages = [("System", "Welcome to Kerra Isle. Say hello to the shaman!")]
user_text = ""
status = "Loading AI and voice..."
busy = True
jobs = queue.Queue()
results = queue.Queue()
stop_event = threading.Event()


def npc_worker():
    """All slow Ollama/Kokoro work stays off the GUI thread."""
    try:
        import kerra_isle_kerra_npc as npc
        conversation = npc.load_memory()
        results.put(("ready", "Kerra is ready. Type a message and press Enter."))
    except Exception as exc:
        results.put(("fatal", str(exc)))
        return

    while not stop_event.is_set():
        try:
            message = jobs.get(timeout=0.1)
        except queue.Empty:
            continue
        if message is None:
            break
        try:
            results.put(("status", "Kerra is thinking..."))
            # Commit only after a successful response, as in the original NPC.
            pending = conversation + [{"role": "user", "content": message}]
            response = npc.ollama.chat(
                model="llama3.2",
                messages=[
                    {"role": "system", "content": npc.KERRA_SYSTEM_INSTRUCTION},
                    *pending,
                ],
            )
            answer = response["message"]["content"].strip()
            conversation = pending + [{"role": "assistant", "content": answer}]
            npc.save_memory(conversation)
            results.put(("answer", answer))
            results.put(("status", "Kerra is speaking..."))
            npc.speak_text(answer)
            results.put(("ready", "Kerra is listening."))
        except Exception as exc:
            results.put(("error", str(exc)))
            results.put(("ready", "Try another message."))


threading.Thread(target=npc_worker, daemon=True).start()


def wrapped_lines(text, use_font, max_width):
    """Wrap long text to the available chat width."""
    lines = []
    for paragraph in text.split("\n"):
        current = ""
        for word in paragraph.split():
            trial = (current + " " + word).strip()
            if use_font.size(trial)[0] <= max_width:
                current = trial
            else:
                if current:
                    lines.append(current)
                current = word
        lines.append(current)
    return lines


running = True
while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                running = False
            elif event.key == pygame.K_RETURN and not busy and user_text.strip():
                message = user_text.strip()
                messages.append(("You", message))
                jobs.put(message)
                user_text = ""
                busy = True
                status = "Sending message..."
            elif event.key == pygame.K_BACKSPACE:
                user_text = user_text[:-1]
            elif event.unicode and event.unicode.isprintable() and len(user_text) < 300:
                user_text += event.unicode

    while True:
        try:
            kind, value = results.get_nowait()
        except queue.Empty:
            break
        if kind == "ready":
            busy = False
            status = value
        elif kind == "fatal":
            busy = True
            status = "Failed to initialize AI. See error in chat."
            messages.append(("Error", value))
        elif kind == "status":
            status = value
        elif kind == "answer":
            messages.append(("Kerra", value))
        elif kind == "error":
            messages.append(("Error", value))

    screen.fill(BG)
    pygame.draw.rect(screen, PANEL, (15, 15, 420, 670), border_radius=12)
    screen.blit(portrait, portrait_rect)
    screen.blit(heading.render("Kerra Isle", True, ACCENT), (40, 30))
    screen.blit(small.render("Ambient sounds: ON", True, MUTED), (40, 640))

    pygame.draw.rect(screen, PANEL, (450, 15, 535, 670), border_radius=12)
    screen.blit(heading.render("Talk to Kerra", True, WHITE), (470, 30))
    screen.blit(small.render(status[:60], True, ACCENT), (470, 70))

    # Render the most recent messages from the bottom of the chat region.
    rendered = []
    for speaker, message in messages:
        rendered.append((speaker, True))
        for line in wrapped_lines(message, font, 475):
            rendered.append((line, False))
        rendered.append(("", False))
    line_height = 25
    visible_count = 19
    visible = rendered[-visible_count:]
    for i, (line, is_speaker) in enumerate(visible):
        color = ACCENT if is_speaker else WHITE
        use_font = small if is_speaker else font
        screen.blit(use_font.render(line, True, color), (470, 112 + i * line_height))

    pygame.draw.rect(screen, (19, 24, 29), (465, 625, 505, 45), border_radius=8)
    # Show the tail of long input so the cursor remains visible.
    display_text = user_text
    while font.size(display_text)[0] > 465:
        display_text = display_text[1:]
    hint = "Type here, then press Enter..." if not user_text else display_text
    screen.blit(font.render(hint, True, WHITE if user_text else MUTED), (478, 636))
    pygame.display.flip()
    clock.tick(60)

stop_event.set()
jobs.put(None)
ambience_channel.stop()
pygame.mixer.music.stop()
pygame.quit()
