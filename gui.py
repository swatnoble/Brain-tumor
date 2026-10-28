import sys
import sqlite3
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QTextEdit, QListWidget, QPushButton, QStackedWidget)
from PyQt5.QtCore import QTimer, Qt, pyqtSignal, QObject
from PyQt5.QtGui import QFont

class GuiSignalBridge(QObject):
    update_signal = pyqtSignal()

class JarvisDashboard(QMainWindow):
    def __init__(self, brain):
        super().__init__()
        self.brain = brain
        self.bridge = GuiSignalBridge()
        self.bridge.update_signal.connect(self.refresh_dashboard)
        
        self.initUI()
        self.timer = QTimer()
        self.timer.timeout.connect(self.refresh_dashboard)
        self.timer.start(1000)

    def initUI(self):
        self.setWindowTitle("Jarvis AI")
        self.setGeometry(100, 100, 950, 600)
        self.setStyleSheet("""
            QMainWindow { background-color: #05070a; }
            QLabel { color: #d0e0f0; font-family: Segoe UI; }
            QPushButton { 
                background-color: #0d1522; 
                color: #00f0ff; 
                border: 1px solid #1a3550; 
                border-radius: 6px; 
                padding: 6px 14px; 
                font-weight: bold;
                font-family: Segoe UI;
            }
            QPushButton:hover { background-color: #142238; border: 1px solid #00f0ff; }
            QTextEdit, QListWidget { 
                background-color: #030508; 
                color: #00ffaa; 
                border: 1px solid #142840; 
                border-radius: 6px;
                font-family: Consolas, Monospace;
            }
        """)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(15, 15, 15, 15)

        # Top Navigation Bar
        top_bar = QHBoxLayout()
        title_lbl = QLabel("Jarvis AI")
        title_lbl.setFont(QFont("Segoe UI", 12, QFont.Bold))
        title_lbl.setStyleSheet("color: #ffffff;")
        top_bar.addWidget(title_lbl)

        top_bar.addStretch()

        self.btn_home = QPushButton("🏠 Home")
        self.btn_home.clicked.connect(lambda: self.switch_page(0))
        top_bar.addWidget(self.btn_home)

        self.btn_logs = QPushButton("💬 Logs & Memory")
        self.btn_logs.clicked.connect(lambda: self.switch_page(1))
        top_bar.addWidget(self.btn_logs)

        main_layout.addLayout(top_bar)

        # Stacked Pages
        self.stack = QStackedWidget()
        
        # --- PAGE 0: Clean Home Screen ---
        home_page = QWidget()
        home_layout = QVBoxLayout(home_page)
        home_layout.setAlignment(Qt.AlignCenter)

        self.orb_lbl = QLabel("🔵")
        self.orb_lbl.setFont(QFont("Segoe UI", 60))
        self.orb_lbl.setAlignment(Qt.AlignCenter)
        home_layout.addWidget(self.orb_lbl)

        self.status_lbl = QLabel("Available...")
        self.status_lbl.setFont(QFont("Segoe UI", 12))
        self.status_lbl.setStyleSheet("color: #00f0ff;")
        self.status_lbl.setAlignment(Qt.AlignCenter)
        home_layout.addWidget(self.status_lbl)

        # Interactive Mic Button
        mic_btn = QPushButton("🎙️")
        mic_btn.setFixedSize(55, 55)
        mic_btn.setStyleSheet("""
            QPushButton { 
                background-color: #007acc; 
                color: white; 
                border-radius: 27px; 
                font-size: 20px;
                border: none;
            }
            QPushButton:hover { background-color: #0098ff; }
        """)
        mic_btn.clicked.connect(self.trigger_manual_listen)
        
        mic_container = QHBoxLayout()
        mic_container.setAlignment(Qt.AlignCenter)
        mic_container.addWidget(mic_btn)
        home_layout.addLayout(mic_container)

        self.stack.addWidget(home_page)

        # --- PAGE 1: Simple Logs & Memory View ---
        logs_page = QWidget()
        logs_layout = QHBoxLayout(logs_page)

        left_pane = QVBoxLayout()
        lbl_prefs_title = QLabel("Learned Preferences")
        lbl_prefs_title.setStyleSheet("color: #00f0ff; font-weight: bold;")
        left_pane.addWidget(lbl_prefs_title)
        
        self.lst_prefs = QListWidget()
        left_pane.addWidget(self.lst_prefs)
        logs_layout.addLayout(left_pane, stretch=1)

        right_pane = QVBoxLayout()
        lbl_logs_title = QLabel("System Audit Trail")
        lbl_logs_title.setStyleSheet("color: #00f0ff; font-weight: bold;")
        right_pane.addWidget(lbl_logs_title)

        self.txt_logs = QTextEdit()
        self.txt_logs.setReadOnly(True)
        right_pane.addWidget(self.txt_logs)
        logs_layout.addLayout(right_pane, stretch=2)

        self.stack.addWidget(logs_page)
        main_layout.addWidget(self.stack)

    def switch_page(self, index):
        self.stack.setCurrentIndex(index)

    def set_status(self, text):
        self.status_lbl.setText(text)

    def trigger_manual_listen(self):
        self.set_status("Listening...")
        self.brain.voice.speak("I'm listening, boss!")
        self.set_status("Available...")

    def trigger_ui_update(self):
        self.bridge.update_signal.emit()

    def refresh_dashboard(self):
        self.lst_prefs.clear()
        try:
            conn = sqlite3.connect("memory.db")
            cursor = conn.cursor()
            cursor.execute("SELECT pref_key, frequency FROM user_preferences ORDER BY frequency DESC LIMIT 15")
            for key, freq in cursor.fetchall():
                self.lst_prefs.addItem(f"{key} (Uses: {freq})")
            conn.close()
        except Exception:
            pass

        try:
            with open("logs.txt", "r") as f:
                lines = f.readlines()[-25:]
                self.txt_logs.setText("".join(lines))
        except FileNotFoundError:
            self.txt_logs.setText("System initializing...")