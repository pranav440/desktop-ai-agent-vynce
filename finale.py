"""
E.D.I - Smart Voice Assistant  (Groq + Multilanguage)
Updated: better info-detection (fixes "tell me about vit pune")
Added OS commands
GUI unchanged
"""

# ---------- FIX: Disable DPI Warning ----------
import ctypes
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(0)
except:
    pass
# ----------------------------------------------------
import requests
import os, sys, json, threading, subprocess, time, webbrowser, wikipedia
from langdetect import detect
import speech_recognition as sr
import pyttsx3
from groq import Groq

# PyQt6 - GUI
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QPainter, QColor, QRadialGradient, QFont
from PyQt6.QtWidgets import QApplication, QWidget

# -------------------------------
# IMPORTANT GLOBALS
# -------------------------------
ORB_DIAMETER = 180

# -------------------------------
#  YOUR GROQ API KEY
# -------------------------------
GROQ_API_KEY = "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"
client = None
try:
    client = Groq(api_key=GROQ_API_KEY)
except:
    client = None

# -------------------------------
#  SPEECH (STT/TTS)
# -------------------------------
engine = pyttsx3.init()
engine.setProperty("rate", 180)

def speak(text):
    try:
        engine.say(text)
        engine.runAndWait()
    except:
        pass

def listen_and_recognize():
    r = sr.Recognizer()
    with sr.Microphone() as source:
        r.pause_threshold = 1
        try:
            audio = r.listen(source, timeout=6, phrase_time_limit=12)
        except:
            return "", "en"
    try:
        text = r.recognize_google(audio)
        lang = "en"
        try:
            lang = detect(text)
        except:
            lang = "en"
        return text.lower(), lang
    except:
        return "", "en"


# -------------------------------
# OS COMMANDS (NEW)
# -------------------------------
def execute_os_command(text):
    t = text.lower()

    if "shutdown" in t or "band kar" in t:
        os.system("shutdown /s /t 3")
        speak("Shutting down your system.")
        return True

    if "restart" in t or "reboot" in t:
        os.system("shutdown /r /t 3")
        speak("Restarting your system.")
        return True

    if "sleep" in t:
        speak("Putting the system to sleep.")
        os.system("rundll32.exe powrprof.dll,SetSuspendState Sleep")
        return True

    if "lock" in t or "screen lock" in t:
        speak("Locking your device.")
        os.system("rundll32.exe user32.dll,LockWorkStation")
        return True

    if "sign out" in t or "log out" in t:
        speak("Signing out.")
        os.system("shutdown /l")
        return True

    return False


# -------------------------------
# INTENT DETECTION FIX
# -------------------------------
# Always treat these as info questions
INFO_KEYWORDS = [
    "tell me about", "kya hai", "kaun hai", "what is", "who is",
    "details", "summary", "information", "info", "explain"
]

def is_info_question(text):
    t = text.lower()
    return any(k in t for k in INFO_KEYWORDS)


def get_intent(user_text):
    if client is None:
        return {"intent": "unknown", "query": user_text}

    # If info question → do not ask AI for intent
    if is_info_question(user_text):
        return {"intent": "ask_info", "query": user_text}

    prompt = f"""
Classify the text into: open_app, ask_info, unknown
Return JSON only.
User: "{user_text}"
"""
    try:
        res = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}]
        )
        return json.loads(res.choices[0].message.content)
    except:
        return {"intent": "unknown", "query": user_text}


# -------------------------------
# MULTILANGUAGE APP OPEN
# -------------------------------
APP_SYNONYMS = {
    "youtube": ["youtube", "youtube kholo", "open youtube", "youtube chalu"],
    "google": ["google", "google kholo", "open google", "google chrome"],
    "calculator": ["calculator", "calculator kholo", "open calculator"],
    "notepad": ["notepad", "notepad kholo", "open notepad"],
    "chrome": ["chrome", "open chrome", "chrome kholo"],
}

APP_PATHS = {
    "calculator": r"C:\Windows\System32\calc.exe",
    "notepad": r"C:\Windows\System32\notepad.exe",
    "chrome": r"C:\Program Files\Google\Chrome\Application\chrome.exe",
}

def match_app(text):
    t = text.lower()
    for app, syns in APP_SYNONYMS.items():
        for s in syns:
            if s in t:
                return app
    return None

def open_application(app_name):
    app = app_name.lower()

    # youtube / google always open browser
    if app == "youtube":
        webbrowser.open("https://youtube.com")
        return "Opening YouTube."

    if app == "google":
        webbrowser.open("https://google.com")
        return "Opening Google."

    if app in APP_PATHS and os.path.exists(APP_PATHS[app]):
        subprocess.Popen(APP_PATHS[app])
        return f"Opening {app}."

    # fallback → search
    webbrowser.open(f"https://www.google.com/search?q={requests.utils.quote(app_name)}")
    return f"Searching for {app_name}."


# -------------------------------
#  AI KNOWLEDGE (Groq)
# -------------------------------
def ai_info(query, lang="en"):
    if client is None:
        try:
            return wikipedia.summary(query, sentences=2)
        except:
            return f"I couldn't find information on {query}."

    prompt = f"Give a short answer in {lang}. User: {query}"

    try:
        res = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}]
        )
        return res.choices[0].message.content
    except:
        return f"Couldn't answer that."


# -------------------------------
# MAIN PROCESSING
# -------------------------------
def process_command(text, lang="en"):

    # 1) OS Commands
    if execute_os_command(text):
        return

    # 2) App Opening
    app = match_app(text)
    if app:
        speak(open_application(app))
        return

    # 3) Info Question (fixed)
    if is_info_question(text):
        speak(ai_info(text, lang))
        return

    # 4) Intent detection
    intent = get_intent(text)

    if intent["intent"] == "ask_info":
        speak(ai_info(text, lang))
        return

    if intent["intent"] == "open_app":
        app2 = match_app(intent["query"])
        if app2:
            speak(open_application(app2))
            return

    # fallback
    speak(ai_info(text, lang))


# =================================================================
# GUI (UNCHANGED)
# =================================================================
class OrbGUI(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("E.D.I - Voice Assistant")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.resize(480, 500)
        self.phase, self.pulse, self.is_listening = 0.0, 0.0, False
        self.status = "Tap the orb to speak"
        self.timer = QTimer(); self.timer.timeout.connect(self.update_animation); self.timer.start(30)

    def mousePressEvent(self, e):
        pos = e.position()
        x, y = float(pos.x()), float(pos.y())
        cx, cy = float(self.width()//2), 220.0
        if (x-cx)**2 + (y-cy)**2 <= (ORB_DIAMETER/2.0)**2:
            if not self.is_listening:
                threading.Thread(target=self._voice_flow, daemon=True).start()

    def update_animation(self):
        self.phase += 0.15
        self.pulse += ((1 if self.is_listening else 0) - self.pulse) * 0.2
        self.update()

    def paintEvent(self, ev):
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        cx, cy, R = self.width()//2, 220, ORB_DIAMETER//2
        curR = int(R*(1.0+0.1*self.pulse))
        for a in [140, 100, 60]:
            rad = int(curR*(a/100.0))
            p.setBrush(QColor(90,170,255,a))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(int(cx-rad), int(cy-rad), int(2*rad), int(2*rad))
        grad = QRadialGradient(cx, cy, curR, cx-curR*0.3, cy-curR*0.3)
        grad.setColorAt(0, QColor(255,255,255))
        grad.setColorAt(1, QColor(70,150,255))
        p.setBrush(grad)
        p.drawEllipse(int(cx-curR), int(cy-curR), int(curR*2), int(curR*2))
        p.setPen(QColor(230,240,255))
        p.setFont(QFont("Segoe UI", 13))
        p.drawText(0, int(cy+curR+25), self.width(), 40, Qt.AlignmentFlag.AlignHCenter, self.status)
        p.end()

    def _voice_flow(self):
        try:
            self.is_listening = True
            self.status = "Listening..."
            speak("Yes?")
            txt, lang = listen_and_recognize()
            if not txt:
                speak("I didn't hear anything.")
                self.is_listening = False
                return
            self.status = "Processing..."
            process_command(txt, lang)
            self.status = "Tap the orb to speak"
            self.is_listening = False
        except Exception as e:
            print(e)
            speak("Error.")
            self.is_listening = False


# ---------- MAIN ----------
if __name__ == "__main__":
    app = QApplication(sys.argv)
    gui = OrbGUI()
    gui.show()
    speak("Hello, I'm E.D.I. Tap the orb to speak.")
    sys.exit(app.exec())
