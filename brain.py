import os
import sys
import time
import glob
import json
import sqlite3
import datetime
import threading
import subprocess
import webbrowser
import pyautogui
import psutil
import AppOpener
import numpy as np
import speech_recognition as sr
import pyttsx3

DB_FILE = "memory.db"
VECTOR_FILE = "vector_store.json"
LOG_FILE = "logs.txt"

# ==========================================
# 1. DATABASE & MEMORY MANAGEMENT
# ==========================================
def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS long_term_memory (
            key TEXT PRIMARY KEY,
            value TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS command_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            command TEXT,
            action_taken TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_preferences (
            pref_key TEXT PRIMARY KEY,
            pref_value TEXT,
            frequency INTEGER DEFAULT 1,
            feedback_score REAL DEFAULT 1.0
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# ==========================================
# 2. VECTOR MEMORY ENGINE
# ==========================================
class VectorMemory:
    def __init__(self):
        self.memories = []
        self.load_memories()

    def load_memories(self):
        if os.path.exists(VECTOR_FILE):
            try:
                with open(VECTOR_FILE, "r") as f:
                    self.memories = json.load(f)
            except Exception:
                self.memories = []

    def save_memories(self):
        with open(VECTOR_FILE, "w") as f:
            json.dump(self.memories, f, indent=2)

    def add_memory(self, text, category="general"):
        self.memories.append({
            "text": text,
            "category": category,
            "timestamp": str(datetime.datetime.now())
        })
        self.save_memories()

    def search_memory(self, query):
        query_words = set(query.lower().split())
        best_match = None
        max_overlap = 0
        for item in self.memories:
            text_words = set(item["text"].lower().split())
            overlap = len(query_words.intersection(text_words))
            if overlap > max_overlap:
                max_overlap = overlap
                best_match = item["text"]
        return best_match

# ==========================================
# 3. VOICE ENGINE (THREAD-SAFE CONTINUOUS TTS)
# ==========================================
class VoiceEngine:
    def __init__(self, log_callback=None):
        self.log_callback = log_callback
        self.recognizer = sr.Recognizer()

    def speak(self, text):
        print(f"JARVIS: {text}")
        if self.log_callback:
            self.log_callback(f"JARVIS: {text}")

        def tts_worker(phrase):
            try:
                engine = pyttsx3.init('sapi5' if os.name == 'nt' else 'espeak')
                voices = engine.getProperty('voices')
                if voices:
                    engine.setProperty('voice', voices[0].id)
                engine.setProperty('rate', 185)
                engine.say(phrase)
                engine.runAndWait()
            except Exception as e:
                print(f"[TTS Error]: {e}")

        speaker_thread = threading.Thread(target=tts_worker, args=(text,))
        speaker_thread.start()
        speaker_thread.join()

    def listen(self):
        with sr.Microphone() as source:
            self.recognizer.adjust_for_ambient_noise(source, duration=0.4)
            if self.log_callback:
                self.log_callback("[Listening...]")
            try:
                audio = self.recognizer.listen(source, timeout=5, phrase_time_limit=8)
                if self.log_callback:
                    self.log_callback("[Understanding...]")
                query = self.recognizer.recognize_google(audio, language='en-US')
                return query.lower().strip()
            except Exception:
                return ""

# ==========================================
# 4. ADVANCED BRAIN & OS AUTOMATION
# ==========================================
class JarvisBrain:
    def __init__(self, voice_engine, ui_updater=None):
        self.voice = voice_engine
        self.ui_updater = ui_updater
        self.vector_mem = VectorMemory()
        self.pending_feedback_command = None
        self.context = {
            "active_app": "Unknown",
            "last_command": "None",
            "recent_commands": [],
            "active_task": "Idle",
            "current_time": "",
            "current_date": ""
        }
        self.update_context()

    def detect_active_application(self):
        try:
            for proc in psutil.process_iter(['name']):
                if proc.info['name'] in ['chrome.exe', 'code.exe', 'msedge.exe', 'notepad.exe', 'python.exe', 'spotify.exe', 'VALORANT-Win64-Shipping.exe']:
                    return proc.info['name']
            return "Desktop / Explorer"
        except Exception:
            return "System Workspace"

    def update_context(self):
        now = datetime.datetime.now()
        self.context["current_time"] = now.strftime("%I:%M %p")
        self.context["current_date"] = now.strftime("%A, %B %d, %Y")
        self.context["active_app"] = self.detect_active_application()

    def log_execution(self, command, action):
        self.context["last_command"] = command
        self.context["recent_commands"].append(command)
        if len(self.context["recent_commands"]) > 5:
            self.context["recent_commands"].pop(0)

        with open(LOG_FILE, "a") as f:
            f.write(f"[{datetime.datetime.now()}] CMD: '{command}' | ACTION: '{action}'\n")

        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO command_logs (command, action_taken) VALUES (?, ?)", (command, action))
        cursor.execute("SELECT frequency FROM user_preferences WHERE pref_key = ?", (command,))
        row = cursor.fetchone()
        if row:
            cursor.execute("UPDATE user_preferences SET frequency = frequency + 1 WHERE pref_key = ?", (command,))
        else:
            cursor.execute("INSERT INTO user_preferences (pref_key, pref_value, frequency, feedback_score) VALUES (?, ?, 1, 1.0)", (command, action))
        conn.commit()
        conn.close()

        if self.ui_updater:
            self.ui_updater()

    def confirm_action(self, warning_message):
        self.voice.speak(f"Hold on boss. {warning_message}. Are you sure you want me to proceed? Say yes or no.")
        response = self.voice.listen()
        if "yes" in response or "confirm" in response or "do it" in response:
            return True
        self.voice.speak("Got it. Aborting action.")
        return False

    def process_feedback(self, command, is_positive):
        score_change = 0.5 if is_positive else -0.5
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("UPDATE user_preferences SET feedback_score = feedback_score + ? WHERE pref_key = ?", (score_change, command))
        conn.commit()
        conn.close()
        if is_positive:
            self.voice.speak("Awesome! I'll remember you like it this way.")
        else:
            self.voice.speak("Noted. I will adjust how I handle that next time.")

    def execute_command(self, query):
        if not query:
            return
        
        # Clean wake word from the start
        query = query.replace("jarvis", "").strip()

        self.update_context()
        self.context["active_task"] = f"Executing: '{query}'"

        # Reinforcement Feedback
        if query in ["that was good", "nice job", "good work"]:
            if self.pending_feedback_command:
                self.process_feedback(self.pending_feedback_command, True)
                self.pending_feedback_command = None
            return
        elif query in ["bad action", "wrong", "don't do that"]:
            if self.pending_feedback_command:
                self.process_feedback(self.pending_feedback_command, False)
                self.pending_feedback_command = None
            return

        # Study Mode Macro
        elif "start my study session" in query or "study mode" in query:
            self.voice.speak("Setting up your study environment right away, boss!")
            webbrowser.open("https://google.com")
            webbrowser.open("https://scholar.google.com")
            subprocess.Popen(["notepad.exe" if os.name == 'nt' else 'gedit'])
            self.log_execution(query, "Macro: Study Environment Launched")
            self.pending_feedback_command = query

        # Context Awareness
        elif "what am i doing" in query or "current context" in query:
            app = self.context["active_app"]
            self.voice.speak(f"You're currently working in {app}. Time is {self.context['current_time']}.")
            self.log_execution(query, "Provided Context Status")

        # Vector Memory Integration
        elif "remember that" in query:
            fact = query.replace("remember that", "").strip()
            self.vector_mem.add_memory(fact, category="user_preference")
            self.voice.speak(f"Locked into memory: {fact}")
            self.log_execution(query, "Stored in Vector Memory")
        elif "what do you remember about" in query or "recall" in query:
            search_term = query.replace("what do you remember about", "").replace("recall", "").strip()
            result = self.vector_mem.search_memory(search_term)
            if result:
                self.voice.speak(f"Here's what I found: {result}")
            else:
                self.voice.speak("I couldn't find any related memory fragments on that topic.")
            self.log_execution(query, "Queried Vector Memory")

        # Windows Settings
        elif "open settings" in query or "settings" in query:
            self.voice.speak("Opening Windows Settings for you, boss.")
            if os.name == 'nt':
                os.system("start ms-settings:")
            self.log_execution(query, "Opened Windows Settings")

        # Valorant Launcher
        elif "open val" in query or "open valorant" in query:
            self.voice.speak("Firing up Valorant! Good luck in your match, boss.")
            if os.name == 'nt':
                valorant_path = r"C:\Riot Games\Riot Client\RiotClientServices.exe"
                if os.path.exists(valorant_path):
                    subprocess.Popen([valorant_path, "--launch-product=valorant", "--launch-patchline=live"])
                else:
                    os.system("start valorant")
            self.log_execution(query, "Launched Valorant")

        # System File Search
        elif "find file" in query or "search file" in query:
            filename = query.replace("find file", "").replace("search file", "").strip()
            self.voice.speak(f"Searching your system for {filename}...")
            user_path = os.path.expanduser("~")
            found_files = glob.glob(f"{user_path}/**/*{filename}*", recursive=True)
            if found_files:
                target = found_files[0]
                self.voice.speak(f"Found it! Opening {os.path.basename(target)}")
                os.startfile(target)
                self.log_execution(query, f"Opened File: {target}")
            else:
                self.voice.speak(f"Sorry boss, couldn't locate any file named {filename}.")

        # CONTEXT-AWARE SMART CLOSING LOGIC (WITH TARGETED TAB CLOSING)
        elif query.startswith("close"):
            target_to_close = query.replace("close", "").strip().lower()
            active_app = self.detect_active_application().lower()

            if target_to_close and target_to_close not in ["tab", "app", "window"]:
                self.voice.speak(f"Closing {target_to_close}, boss.")
                if "chrome" in active_app or "edge" in active_app or "browser" in active_app:
                    pyautogui.hotkey("ctrl", "shift", "a")  # Open tab search dropdown
                    time.sleep(0.3)
                    pyautogui.write(target_to_close, interval=0.05)
                    time.sleep(0.4)
                    pyautogui.press("enter")
                    time.sleep(0.3)
                    pyautogui.hotkey("ctrl", "w")  # Close that specific tab
                else:
                    pyautogui.hotkey("alt", "f4")
                self.log_execution(query, f"Targeted Close: {target_to_close}")
            else:
                if "chrome" in active_app or "edge" in active_app or "browser" in active_app:
                    self.voice.speak("Closing current browser tab, boss.")
                    pyautogui.hotkey("ctrl", "w")
                    self.log_execution(query, "Closed Browser Tab (Ctrl+W)")
                else:
                    self.voice.speak("Closing application, boss.")
                    pyautogui.hotkey("alt", "f4")
                    self.log_execution(query, "Closed Desktop App (Alt+F4)")

        elif "switch window" in query or "next window" in query:
            pyautogui.hotkey("alt", "tab")
            self.log_execution(query, "Switched Window")

        elif "type " in query:
            text_to_type = query.replace("type ", "").strip()
            pyautogui.write(text_to_type, interval=0.05)
            self.log_execution(query, f"Typed text: {text_to_type}")

        # Hardware Volume Control
        elif "volume up" in query:
            pyautogui.press("volumeup", presses=5)
            self.voice.speak("Turned volume up, boss.")
            self.log_execution(query, "Volume Up")
        elif "volume down" in query:
            pyautogui.press("volumedown", presses=5)
            self.voice.speak("Turned volume down, boss.")
            self.log_execution(query, "Volume Down")
        elif "mute" in query:
            pyautogui.press("volumemute")
            self.voice.speak("Muted audio.")
            self.log_execution(query, "Muted Audio")

        # Terminal Commands
        elif "run command" in query or "terminal " in query:
            cmd = query.replace("run command", "").replace("terminal", "").strip()
            if self.confirm_action(f"Execute terminal command '{cmd}'"):
                self.voice.speak("Executing terminal command.")
                result = subprocess.getoutput(cmd)
                print(f"Command Output:\n{result}")
                self.log_execution(query, f"Executed CMD: {cmd}")

        elif "delete file" in query or "purge system" in query:
            if self.confirm_action("This involves deleting sensitive files"):
                self.voice.speak("Executing request under safety override.")
                self.log_execution(query, "File Action Executed (Confirmed)")

        # Conversational / Chit-Chat
        elif any(g in query for g in ["hello", "hi", "hey"]):
            self.voice.speak("Hey there! Ready to build something great today, boss?")
            self.log_execution(query, "Friendly Greeting")
        elif "how are you" in query:
            self.voice.speak("All systems running at peak efficiency! How are you doing today?")
            self.log_execution(query, "Chitchat Response")

        # ==========================================
        # INTENT-BASED OPEN HANDLER (App vs Tab/Web)
        # ==========================================
        elif "open " in query or any(site in query for site in ["w3schools", "classroom", "wiki", "youtube", "github", "stackoverflow", "spotify", "notepad", "chrome", "calendar", "comet", "chatgpt", "chat gpt", "gpt", "drive", "maps", "docs", "meet"]):
            if query.startswith("open "):
                target = query.replace("open ", "").strip()
            else:
                target = query.strip()

            wants_local_app = "app" in target
            wants_web_tab = "tab" in target or "website" in target or "site" in target

            target = target.replace(" app", "").replace(" tab", "").replace(" website", "").replace(" site", "").replace(" in google", "").replace(" on google", "").strip()

            WEB_ALIASES = {
                "chatgpt": "https://chatgpt.com",
                "chat gpt": "https://chatgpt.com",
                "gpt": "https://chatgpt.com",
                "openai": "https://chatgpt.com",
                "youtube": "https://www.youtube.com",
                "github": "https://www.github.com",
                "stackoverflow": "https://stackoverflow.com",
                "w3schools": "https://www.w3schools.com",
                "classroom": "https://classroom.google.com",
                "google classroom": "https://classroom.google.com",
                "gcr": "https://classroom.google.com",
                "drive": "https://drive.google.com",
                "google drive": "https://drive.google.com",
                "maps": "https://maps.google.com",
                "google maps": "https://maps.google.com",
                "docs": "https://docs.google.com",
                "google docs": "https://docs.google.com",
                "meet": "https://meet.google.com",
                "google meet": "https://meet.google.com",
                "wiki": "https://www.wikipedia.org",
                "wikipedia": "https://www.wikipedia.org"
            }

            if target in ["chrome", "google chrome"]:
                self.voice.speak("Opening Google Chrome, boss!")
                try:
                    AppOpener.open("google chrome", match_closest=True)
                except Exception:
                    webbrowser.open("https://www.google.com")
                self.log_execution(query, "Opened Chrome")

            elif target in WEB_ALIASES:
                self.voice.speak(f"Opening {target} in your browser, boss!")
                webbrowser.open(WEB_ALIASES[target])
                self.log_execution(query, f"Opened Web URL: {target}")

            elif wants_web_tab or ("." in target and " " not in target):
                self.voice.speak(f"Opening {target} in browser, boss!")
                if "." in target and " " not in target:
                    url = target if target.startswith("http") else f"https://{target}"
                    webbrowser.open(url)
                else:
                    webbrowser.open(f"https://www.google.com/search?q={target}")
                self.log_execution(query, f"Opened Web Tab: {target}")

            elif wants_local_app:
                self.voice.speak(f"Opening {target} application, boss!")
                try:
                    AppOpener.open(target, match_closest=True)
                    self.log_execution(query, f"Opened Local App: {target}")
                except Exception:
                    webbrowser.open(f"https://www.google.com/search?q={target}")
                    self.log_execution(query, f"Fallback Web Search: {target}")

            else:
                self.voice.speak(f"Opening {target} for you, boss!")
                try:
                    AppOpener.open(target, match_closest=True)
                    self.log_execution(query, f"Opened App (Default): {target}")
                except Exception:
                    webbrowser.open(f"https://www.google.com/search?q={target}")
                    self.log_execution(query, f"Fallback Web Search: {target}")

        else:
            self.voice.speak("I hear you, boss, but I'm not sure how to handle that command yet.")
            self.log_execution(query, "Unknown Command")

        self.context["active_task"] = "Idle"
        if self.ui_updater:
            self.ui_updater()

# ==========================================
# 5. PROACTIVE SCHEDULER
# ==========================================
class ProactiveScheduler(threading.Thread):
    def __init__(self, brain, voice):
        super().__init__()
        self.brain = brain
        self.voice = voice
        self.daemon = True

    def run(self):
        while True:
            now = datetime.datetime.now()
            if now.minute == 0:
                cpu = psutil.cpu_percent()
                if cpu > 80:
                    self.voice.speak(f"Proactive Alert: Hey boss, CPU usage is high at {cpu} percent. Want me to close background apps?")
                    self.brain.log_execution("PROACTIVE_CHECK", "High CPU Warning")
            time.sleep(45)

if __name__ == "__main__":
    print("Initializing JARVIS Core Backend...")
    voice_engine = VoiceEngine()
    brain = JarvisBrain(voice_engine)
    scheduler = ProactiveScheduler(brain, voice_engine)
    scheduler.start()
    
    voice_engine.speak("All systems online. Standing by for commands, boss.")
    while True:
        command = voice_engine.listen()
        if command:
            print(f"[Captured Voice]: '{command}'")
            brain.execute_command(command) 
            