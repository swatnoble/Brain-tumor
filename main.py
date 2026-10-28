import sys
import time
import threading
from PyQt5.QtWidgets import QApplication
from brain import VoiceEngine, JarvisBrain, ProactiveScheduler
from gui import JarvisDashboard

class JarvisApp:
    def __init__(self):
        self.qt_app = QApplication(sys.argv)
        self.voice = VoiceEngine()
        self.brain = JarvisBrain(self.voice)
        self.gui = JarvisDashboard(self.brain)
        
        self.brain.ui_updater = self.gui.trigger_ui_update
        self.is_active = True  # Tracks wake/sleep state
        
        self.proactive_thread = ProactiveScheduler(self.brain, self.voice)
        self.proactive_thread.start()

        self.listen_thread = threading.Thread(target=self.voice_loop, daemon=True)
        self.listen_thread.start()

    def voice_loop(self):
        self.voice.speak("JARVIS system active, boss! I'm listening. What are we doing today?")
        
        while True:
            try:
                query = self.voice.listen()
                
                if not query or query.strip() == "":
                    time.sleep(0.1)
                    continue

                print(f"\n[Captured Voice]: '{query}'")

                # If sleeping, check for wake words
                if not self.is_active:
                    if any(wake in query for wake in ["wake up", "hey jarvis", "jarvis"]):
                        self.is_active = True
                        self.voice.speak("I'm awake and ready, boss!")
                        if self.gui:
                            self.gui.set_status("Available...")
                        
                        clean_query = query.replace("hey jarvis", "").replace("wake up", "").replace("jarvis", "").strip()
                        if clean_query:
                            self.brain.execute_command(clean_query)
                    continue

                # Check for sleep / standby command
                if any(stop_word in query for stop_word in ["stop listening", "go to sleep", "shut down jarvis", "bye jarvis"]):
                    self.voice.speak("Going on standby. Say 'Wake up' or 'Hey Jarvis' whenever you need me.")
                    self.is_active = False
                    if self.gui:
                        self.gui.set_status("On Standby (Say 'Wake up')")
                    continue

                # Execute active command normally
                self.brain.execute_command(query)

            except Exception as e:
                print(f"[Recovered Loop Error]: {e}")
                time.sleep(0.5)

    def run(self):
        self.gui.show()
        sys.exit(self.qt_app.exec_())

if __name__ == "__main__":
    app = JarvisApp()
    app.run()