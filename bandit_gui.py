import soundfile as sf
import torch
import torchaudio

# Monkey-patch torchaudio.load to use soundfile
def _soundfile_load(filepath, *args, **kwargs):
    data, sr = sf.read(filepath, dtype="float32", always_2d=True)
    return torch.from_numpy(data.T), sr

torchaudio.load = _soundfile_load

import glob
import json
import os
import re
import threading
import queue
import random
import pygame
import ollama



# --- 1. Configuration & Constants ---
WIDTH, HEIGHT = 960, 640
FPS = 60
MEMORY_FILE = "bandit_memory.json"
AMBIENCE_FILE = "bandit_ambience.ogg"
PORTRAIT_FILE = "bandit.png"
OUTPUT_WAV = "temp_bandit_speech.wav"

# S.T.A.L.K.E.R. PDA Color Palette
BG_DARK = (18, 20, 18)
PANEL_BG = (26, 30, 26)
BORDER_COLOR = (74, 84, 70)
ACCENT_AMBER = (218, 165, 32)
ACCENT_GREEN = (110, 185, 95)
TEXT_LIGHT = (220, 224, 215)
TEXT_MUTED = (135, 145, 130)
ACTION_COLOR = (175, 155, 110)
USER_COLOR = (120, 180, 210)
DANGER_RED = (200, 70, 60)

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


# --- 2. Backend Engine (TTS + Ollama + Memory) ---
class BanditEngine:
    def __init__(self, ui_queue: queue.Queue):
        self.ui_queue = ui_queue
        self.voice_enabled = True
        self.muted = False
        self.tts = None
        self.ref_clips = []
        self.conversation = self.load_memory()
        self.is_busy = False

    def load_memory(self):
        if os.path.exists(MEMORY_FILE):
            try:
                with open(MEMORY_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return []
        return []

    def save_memory(self):
        with open(MEMORY_FILE, "w", encoding="utf-8") as f:
            json.dump(self.conversation, f, indent=2)

    def init_audio_and_tts(self):
        """Runs in a background thread at startup so the GUI opens immediately."""
        self.ui_queue.put(("status", "Initializing audio & XTTS-v2..."))
        try:
            from TTS.api import TTS

            if os.path.exists(AMBIENCE_FILE):
                pygame.mixer.music.load(AMBIENCE_FILE)
                pygame.mixer.music.set_volume(0.55)
                pygame.mixer.music.play(loops=-1)

            self.ref_clips = (
                glob.glob("bandit_refs/*.wav")
                + glob.glob("bandit_refs/*.ogg")
                + glob.glob("bandit_refs/*.mp3")
            )
            if not self.ref_clips:
                raise FileNotFoundError("No audio samples in 'bandit_refs/'")

            device = "cuda" if torch.cuda.is_available() else "cpu"
            print(f"DEBUG -> CUDA Available: {torch.cuda.is_available()}, Using Device: {device}")
            self.ui_queue.put(("status", f"Loading XTTS-v2 on {device.upper()}..."))
            self.tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to(device)
            self.ui_queue.put(("system_msg", f"[PDA] Voice cloner online ({device.upper()}, {len(self.ref_clips)} samples)."))

        except Exception as err:
            self.voice_enabled = False
            self.ui_queue.put(("system_msg", f"[PDA Warning] Text-only mode ({err})"))

        # Trigger initial greeting once loaded
        greeting = (
            "*adjusts gas mask* Look who crawled back out of the anomaly."
            if self.conversation
            else "*spits on the ground* Drop the weapon and step into the light, sucker!"
        )
        self.ui_queue.put(("bandit_msg", greeting))
        self.speak_text(greeting)
        self.ui_queue.put(("status", "Ready — Waiting for input"))

    def speak_text(self, text: str):
        if not self.voice_enabled or self.muted or not self.tts:
            return

        # Keep the actions, but remove the '*' characters so TTS reads the action words naturally
        clean_speech = text.replace("*", "").strip()
        if not clean_speech:
            return

        try:
            self.ui_queue.put(("status", "Synthesizing voice..."))
            self.tts.tts_to_file(
                text=clean_speech,
                speaker_wav=self.ref_clips,
                language="en",
                file_path=OUTPUT_WAV,
            )

            self.ui_queue.put(("status", "Bandit is speaking..."))
            speech_sound = pygame.mixer.Sound(OUTPUT_WAV)
            channel = speech_sound.play()
            while channel.get_busy():
                if self.muted:
                    channel.stop()
                    break
                pygame.time.wait(50)

        except Exception as err:
            self.ui_queue.put(("system_msg", f"[TTS Error: {err}]"))

    def process_user_message(self, user_text: str):
        if self.is_busy:
            return
        self.is_busy = True
        threading.Thread(target=self._worker_reply, args=(user_text,), daemon=True).start()

    def _worker_reply(self, user_text: str):
        try:
            self.ui_queue.put(("status", "Bandit is thinking..."))
            self.conversation.append({"role": "user", "content": user_text})

            response = ollama.chat(
                model="llama3.2",
                messages=[
                    {"role": "system", "content": BANDIT_SYSTEM_INSTRUCTION},
                    *self.conversation,
                ],
            )

            answer = response["message"]["content"].strip()
            self.conversation.append({"role": "assistant", "content": answer})
            self.save_memory()

            self.ui_queue.put(("bandit_msg", answer))
            self.speak_text(answer)

        except Exception as e:
            if self.conversation and self.conversation[-1]["role"] == "user":
                self.conversation.pop()
            self.ui_queue.put(("system_msg", f"[Comms Error: {e}]"))
        finally:
            self.is_busy = False
            self.ui_queue.put(("status", "Ready — Waiting for input"))


# --- 3. Pygame PDA GUI ---
class BanditGUI:
    def __init__(self):
        pygame.init()
        pygame.mixer.init()
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("S.T.A.L.K.E.R. PDA // Campfire Comms")
        self.clock = pygame.time.Clock()

        # Fonts
        self.font_title = pygame.font.SysFont("consolas", 20, bold=True)
        self.font_main = pygame.font.SysFont("consolas", 16)
        self.font_small = pygame.font.SysFont("consolas", 13)

        # State
        self.ui_queue = queue.Queue()
        self.engine = BanditEngine(self.ui_queue)
        self.chat_log = []  # List of (sender, text)
        self.input_text = ""
        self.status_text = "Booting PDA..."
        self.scroll_offset = 0
        self.cursor_timer = 0

        # Campfire Ember Particles
        self.embers = [
            [random.randint(40, 260), random.randint(250, 380), random.uniform(0.4, 1.2), random.randint(2, 4)]
            for _ in range(28)
        ]

        # Load portrait while preserving aspect ratio
        self.portrait = None
        if os.path.exists(PORTRAIT_FILE):
            img = pygame.image.load(PORTRAIT_FILE).convert_alpha()
            w, h = img.get_size()
            scale = min(220 / w, 220 / h)
            new_size = (int(w * scale), int(h * scale))
            self.portrait = pygame.transform.smoothscale(img, new_size)

        # Populate previous memory into chat log
        for msg in self.engine.conversation[-12:]:
            sender = "You" if msg["role"] == "user" else "Bandit"
            self.chat_log.append((sender, msg["content"]))

        # Start TTS & Greeting thread
        threading.Thread(target=self.engine.init_audio_and_tts, daemon=True).start()

    def wrap_text(self, text: str, max_width: int):
        words = text.split(" ")
        lines = []
        current_line = ""
        for word in words:
            test_line = f"{current_line} {word}".strip()
            if self.font_main.size(test_line)[0] <= max_width:
                current_line = test_line
            else:
                if current_line:
                    lines.append(current_line)
                current_line = word
        if current_line:
            lines.append(current_line)
        return lines

    def draw_left_panel(self):
        panel_rect = pygame.Rect(20, 20, 260, HEIGHT - 40)
        pygame.draw.rect(self.screen, PANEL_BG, panel_rect, border_radius=6)
        pygame.draw.rect(self.screen, BORDER_COLOR, panel_rect, 2, border_radius=6)

        # Portrait Frame
        frame_rect = pygame.Rect(40, 40, 220, 220)
        pygame.draw.rect(self.screen, (15, 17, 15), frame_rect)
        if self.portrait:
            img_rect = self.portrait.get_rect(center=frame_rect.center)
            self.screen.blit(self.portrait, img_rect.topleft)
        else:
            # Stylized Bandit Gas-Mask Silhouette Fallback
            pygame.draw.circle(self.screen, (45, 50, 45), (150, 125), 48)
            pygame.draw.ellipse(self.screen, (35, 38, 35), (90, 170, 120, 90))
            # Glowing amber goggles
            pygame.draw.circle(self.screen, ACCENT_AMBER, (133, 120), 11)
            pygame.draw.circle(self.screen, ACCENT_AMBER, (167, 120), 11)
            pygame.draw.circle(self.screen, (20, 20, 20), (133, 120), 11, 2)
            pygame.draw.circle(self.screen, (20, 20, 20), (167, 120), 11, 2)
            # Respirator filter
            pygame.draw.circle(self.screen, (65, 70, 65), (150, 152), 16)

        pygame.draw.rect(self.screen, BORDER_COLOR, frame_rect, 2)

        # Campfire Ember Animation inside lower portrait / campfire box
        fire_rect = pygame.Rect(40, 275, 220, 110)
        pygame.draw.rect(self.screen, (20, 16, 14), fire_rect, border_radius=4)
        pygame.draw.rect(self.screen, BORDER_COLOR, fire_rect, 1, border_radius=4)

        for ember in self.embers:
            ember[1] -= ember[2]
            ember[0] += random.uniform(-0.5, 0.5)
            if ember[1] < 280:
                ember[1] = 380
                ember[0] = random.randint(55, 245)
            color = ACCENT_AMBER if ember[1] > 330 else DANGER_RED
            pygame.draw.circle(self.screen, color, (int(ember[0]), int(ember[1])), ember[3] // 2)

        lbl_fire = self.font_small.render("CAMPFIRE // DARK VALLEY", True, TEXT_MUTED)
        self.screen.blit(lbl_fire, (55, 362))

        # NPC Stats / Controls
        info_y = 405
        details = [
            ("FACTION:", "Bandits", DANGER_RED),
            ("RANK:", "Experienced", TEXT_LIGHT),
            ("MOOD:", "Suspicious", ACCENT_AMBER),
            ("VOICE:", "MUTED" if self.engine.muted else "ACTIVE", DANGER_RED if self.engine.muted else ACCENT_GREEN),
        ]
        for label, val, col in details:
            lbl_s = self.font_small.render(label, True, TEXT_MUTED)
            val_s = self.font_small.render(val, True, col)
            self.screen.blit(lbl_s, (40, info_y))
            self.screen.blit(val_s, (125, info_y))
            info_y += 26

        # Help footer
        hints = ["[ENTER] Send message", "[TAB] Toggle Voice Mute", "[ESC] Leave Campfire"]
        hint_y = HEIGHT - 95
        for h in hints:
            hs = self.font_small.render(h, True, TEXT_MUTED)
            self.screen.blit(hs, (40, hint_y))
            hint_y += 20

    def draw_right_panel(self):
        panel_rect = pygame.Rect(300, 20, WIDTH - 320, HEIGHT - 40)
        pygame.draw.rect(self.screen, PANEL_BG, panel_rect, border_radius=6)
        pygame.draw.rect(self.screen, BORDER_COLOR, panel_rect, 2, border_radius=6)

        # Header Bar
        header_rect = pygame.Rect(300, 20, WIDTH - 320, 42)
        pygame.draw.rect(self.screen, (34, 40, 34), header_rect, border_top_left_radius=6, border_top_right_radius=6)
        pygame.draw.line(self.screen, BORDER_COLOR, (300, 62), (WIDTH - 20, 62), 2)

        title_surf = self.font_title.render("LOCAL COMMS // BANDIT CAMPFIRE", True, ACCENT_AMBER)
        self.screen.blit(title_surf, (318, 30))

        # Chat History Area
        chat_area = pygame.Rect(315, 72, WIDTH - 350, HEIGHT - 175)
        self.screen.set_clip(chat_area)

        rendered_lines = []
        max_w = chat_area.width - 10
        for sender, text in self.chat_log:
            if sender == "System":
                for line in self.wrap_text(text, max_w):
                    rendered_lines.append((line, TEXT_MUTED))
            elif sender == "You":
                wrapped = self.wrap_text(f"You: {text}", max_w)
                for line in wrapped:
                    rendered_lines.append((line, USER_COLOR))
            else:
                # Highlight *actions* vs spoken words
                wrapped = self.wrap_text(f"Bandit: {text}", max_w)
                for line in wrapped:
                    col = ACTION_COLOR if "*" in line else TEXT_LIGHT
                    rendered_lines.append((line, col))
            rendered_lines.append(("", TEXT_LIGHT))  # spacing

        line_height = 22
        total_height = len(rendered_lines) * line_height
        start_y = chat_area.bottom - total_height + self.scroll_offset
        if total_height < chat_area.height:
            start_y = chat_area.top

        for line, color in rendered_lines:
            if chat_area.top - line_height <= start_y <= chat_area.bottom:
                surf = self.font_main.render(line, True, color)
                self.screen.blit(surf, (chat_area.left, start_y))
            start_y += line_height

        self.screen.set_clip(None)

        # Status Bar
        status_y = HEIGHT - 96
        pygame.draw.line(self.screen, BORDER_COLOR, (300, status_y - 6), (WIDTH - 20, status_y - 6), 1)
        dot_color = ACCENT_AMBER if self.engine.is_busy else ACCENT_GREEN
        pygame.draw.circle(self.screen, dot_color, (324, status_y + 8), 5)
        status_surf = self.font_small.render(self.status_text, True, ACCENT_AMBER if self.engine.is_busy else TEXT_MUTED)
        self.screen.blit(status_surf, (338, status_y))

        # Input Box
        input_rect = pygame.Rect(315, HEIGHT - 68, WIDTH - 350, 36)
        pygame.draw.rect(self.screen, (16, 18, 16), input_rect, border_radius=4)
        border_col = ACCENT_AMBER if not self.engine.is_busy else BORDER_COLOR
        pygame.draw.rect(self.screen, border_col, input_rect, 2, border_radius=4)

        cursor = "_" if (self.cursor_timer // 30) % 2 == 0 and not self.engine.is_busy else ""
        display_input = self.input_text + cursor
        # Keep right side of long text visible
        while self.font_main.size(display_input)[0] > input_rect.width - 20:
            display_input = display_input[1:]

        inp_surf = self.font_main.render(display_input, True, TEXT_LIGHT)
        self.screen.blit(inp_surf, (input_rect.left + 10, input_rect.top + 9))

    def handle_queue(self):
        while not self.ui_queue.empty():
            event_type, payload = self.ui_queue.get()
            if event_type == "status":
                self.status_text = payload
            elif event_type == "bandit_msg":
                self.chat_log.append(("Bandit", payload))
                self.scroll_offset = 0
            elif event_type == "system_msg":
                self.chat_log.append(("System", payload))
                self.scroll_offset = 0

    def run(self):
        running = True
        while running:
            self.clock.tick(FPS)
            self.cursor_timer += 1
            self.handle_queue()

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False

                elif event.type == pygame.MOUSEWHEEL:
                    self.scroll_offset += event.y * 25
                    self.scroll_offset = max(0, self.scroll_offset)

                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        running = False
                    elif event.key == pygame.K_TAB:
                        self.engine.muted = not self.engine.muted
                    elif event.key == pygame.K_RETURN:
                        msg = self.input_text.strip()
                        if msg and not self.engine.is_busy:
                            if msg.lower() in ("quit", "exit"):
                                running = False
                            else:
                                self.chat_log.append(("You", msg))
                                self.input_text = ""
                                self.scroll_offset = 0
                                self.engine.process_user_message(msg)
                    elif event.key == pygame.K_BACKSPACE:
                        self.input_text = self.input_text[:-1]
                    else:
                        if event.unicode and event.unicode.isprintable():
                            self.input_text += event.unicode

            self.screen.fill(BG_DARK)
            self.draw_left_panel()
            self.draw_right_panel()
            pygame.display.flip()

        pygame.quit()


if __name__ == "__main__":
    app = BanditGUI()
    app.run()