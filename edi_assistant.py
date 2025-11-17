"""
E.D.I - Enhanced Digital Intelligence Voice Assistant
Production-ready AI assistant with multilingual support
"""

import os
import sys
import json
import threading
import time
import webbrowser
import subprocess
import requests
from datetime import datetime
from pathlib import Path

# Disable DPI scaling issues on Windows
if sys.platform == 'win32':
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(0)
    except:
        pass

# Core imports
import speech_recognition as sr
import pyttsx3
from groq import Groq

# GUI imports
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QObject
from PyQt6.QtGui import QPainter, QColor, QRadialGradient, QFont
from PyQt6.QtWidgets import QApplication, QWidget

# Optional imports
try:
    from langdetect import detect, DetectorFactory
    DetectorFactory.seed = 0
    LANGDETECT_AVAILABLE = True
except:
    LANGDETECT_AVAILABLE = False

try:
    import wikipedia
    WIKIPEDIA_AVAILABLE = True
except:
    WIKIPEDIA_AVAILABLE = False

try:
    import pyautogui
    SCREENSHOT_AVAILABLE = True
except:
    SCREENSHOT_AVAILABLE = False


# ============================================================================
# CONFIGURATION
# ============================================================================
class Config:
    """Centralized configuration"""
    # API Keys - REPLACE THIS WITH YOUR KEY!
    GROQ_API_KEY = "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"
    
    # Paths
    BASE_DIR = Path.home() / ".edi_assistant"
    MEMORY_FILE = BASE_DIR / "memory.json"
    LOG_FILE = BASE_DIR / "assistant.log"
    
    # Speech settings
    SPEECH_RATE = 180
    SPEECH_VOLUME = 1.0
    LISTEN_TIMEOUT = 6
    PHRASE_TIME_LIMIT = 12
    
    # GUI settings
    ORB_DIAMETER = 180
    WINDOW_WIDTH = 480
    WINDOW_HEIGHT = 500
    
    # Model settings
    GROQ_MODEL = "llama-3.3-70b-versatile"
    
    @classmethod
    def ensure_dirs(cls):
        """Create necessary directories"""
        cls.BASE_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================================
# UTILITIES
# ============================================================================
class Logger:
    """Simple logging utility"""
    @staticmethod
    def log(message, level="INFO"):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_msg = f"[{timestamp}] [{level}] {message}"
        print(log_msg)
        try:
            with open(Config.LOG_FILE, 'a', encoding='utf-8') as f:
                f.write(log_msg + "\n")
        except:
            pass

    @staticmethod
    def error(message):
        Logger.log(message, "ERROR")

    @staticmethod
    def info(message):
        Logger.log(message, "INFO")


class Memory:
    """Persistent memory management"""
    def __init__(self):
        self.data = self.load()
    
    def load(self):
        """Load memory from disk"""
        try:
            if Config.MEMORY_FILE.exists():
                with open(Config.MEMORY_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            Logger.error(f"Failed to load memory: {e}")
        return {}
    
    def save(self):
        """Save memory to disk"""
        try:
            with open(Config.MEMORY_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            Logger.error(f"Failed to save memory: {e}")
    
    def get(self, key, default=None):
        return self.data.get(key, default)
    
    def set(self, key, value):
        self.data[key] = value
        self.save()


# ============================================================================
# TEXT-TO-SPEECH
# ============================================================================
class TTSEngine:
    """Thread-safe Text-to-Speech engine"""
    def __init__(self):
        self.engine = pyttsx3.init()
        self.engine.setProperty('rate', Config.SPEECH_RATE)
        self.engine.setProperty('volume', Config.SPEECH_VOLUME)
        self._setup_voice()
        self.lock = threading.Lock()
        self.is_speaking = False
    
    def _setup_voice(self):
        """Set up female voice if available"""
        try:
            voices = self.engine.getProperty('voices')
            for voice in voices:
                name = (voice.name or "").lower()
                if any(k in name for k in ['female', 'zira', 'hazel']):
                    self.engine.setProperty('voice', voice.id)
                    Logger.info(f"Using voice: {voice.name}")
                    return
        except Exception as e:
            Logger.error(f"Voice setup error: {e}")
    
    def speak(self, text):
        """Speak text in background thread"""
        def _speak():
            with self.lock:
                self.is_speaking = True
                try:
                    Logger.info(f"Speaking: {text}")
                    self.engine.say(text)
                    self.engine.runAndWait()
                except Exception as e:
                    Logger.error(f"TTS error: {e}")
                finally:
                    self.is_speaking = False
        
        threading.Thread(target=_speak, daemon=True).start()
    
    def stop(self):
        """Stop speaking"""
        try:
            self.engine.stop()
        except:
            pass


# ============================================================================
# SPEECH-TO-TEXT
# ============================================================================
class STTEngine:
    """Speech recognition engine with error handling"""
    def __init__(self):
        self.recognizer = sr.Recognizer()
        self.recognizer.pause_threshold = 1.0
        self.recognizer.energy_threshold = 4000
        self.recognizer.dynamic_energy_threshold = True
    
    def listen(self):
        """Listen and return (text, language)"""
        try:
            with sr.Microphone() as source:
                Logger.info("Adjusting for ambient noise...")
                self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
                
                Logger.info("Listening...")
                audio = self.recognizer.listen(
                    source,
                    timeout=Config.LISTEN_TIMEOUT,
                    phrase_time_limit=Config.PHRASE_TIME_LIMIT
                )
                
                Logger.info("Recognizing...")
                text = self.recognizer.recognize_google(audio)
                Logger.info(f"Recognized: {text}")
                
                # Detect language
                lang = self._detect_language(text)
                return text.strip(), lang
                
        except sr.WaitTimeoutError:
            Logger.info("No speech detected (timeout)")
            return "", "en"
        except sr.UnknownValueError:
            Logger.info("Could not understand audio")
            return "", "en"
        except sr.RequestError as e:
            Logger.error(f"Recognition service error: {e}")
            return "", "en"
        except Exception as e:
            Logger.error(f"Unexpected STT error: {e}")
            return "", "en"
    
    def _detect_language(self, text):
        """Detect language of text"""
        if not LANGDETECT_AVAILABLE or not text:
            return "en"
        
        try:
            detected = detect(text)
            lang_map = {
                'hi': 'hi',
                'mr': 'mr',
                'gu': 'gu',
                'pa': 'pa',
            }
            return lang_map.get(detected, 'en')
        except:
            return "en"


# ============================================================================
# AI ASSISTANT CORE
# ============================================================================
class AIAssistant:
    """Core AI assistant logic"""
    def __init__(self):
        self.groq_client = None
        self._init_groq()
        self.memory = Memory()
    
    def _init_groq(self):
        """Initialize Groq client"""
        try:
            self.groq_client = Groq(api_key=Config.GROQ_API_KEY)
            Logger.info("Groq API initialized")
        except Exception as e:
            Logger.error(f"Failed to initialize Groq: {e}")
            self.groq_client = None
    
    def get_intent(self, text):
        """Analyze user intent using AI"""
        if not self.groq_client:
            return self._fallback_intent(text)
        
        prompt = f"""Analyze this command and return JSON with intent and extracted info.
Possible intents: open_app, system_command, ask_info, set_name, weather, time, date, screenshot, unknown

User command: "{text}"

Return format:
{{"intent": "intent_name", "entity": "extracted_value", "query": "original_text"}}"""

        try:
            response = self.groq_client.chat.completions.create(
                model=Config.GROQ_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=200
            )
            result = json.loads(response.choices[0].message.content)
            Logger.info(f"Intent detected: {result}")
            return result
        except Exception as e:
            Logger.error(f"Intent detection error: {e}")
            return self._fallback_intent(text)
    
    def _fallback_intent(self, text):
        """Simple keyword-based intent detection"""
        text_lower = text.lower()
        
        if any(k in text_lower for k in ['shutdown', 'restart', 'sleep', 'lock']):
            return {"intent": "system_command", "query": text}
        
        if any(k in text_lower for k in ['open', 'start', 'launch', 'kholo']):
            return {"intent": "open_app", "query": text}
        
        if any(k in text_lower for k in ['my name is', 'call me', 'mera naam']):
            return {"intent": "set_name", "query": text}
        
        if any(k in text_lower for k in ['what', 'who', 'where', 'when', 'how', 'why', 'tell me']):
            return {"intent": "ask_info", "query": text}
        
        if any(k in text_lower for k in ['time', 'clock', 'samay']):
            return {"intent": "time", "query": text}
        if any(k in text_lower for k in ['date', 'today', 'tareekh']):
            return {"intent": "date", "query": text}
        
        if any(k in text_lower for k in ['weather', 'temperature', 'mausam']):
            return {"intent": "weather", "query": text}
        
        if 'screenshot' in text_lower:
            return {"intent": "screenshot", "query": text}
        
        return {"intent": "ask_info", "query": text}
    
    def get_ai_response(self, query, lang="en"):
        """Get AI response for information queries"""
        if not self.groq_client:
            return self._fallback_info(query)
        
        prompt = f"""Answer this question concisely in {lang} language. 
Be helpful, accurate, and conversational. Keep response under 50 words.

Question: {query}"""

        try:
            response = self.groq_client.chat.completions.create(
                model=Config.GROQ_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=150
            )
            answer = response.choices[0].message.content.strip()
            Logger.info(f"AI Response: {answer}")
            return answer
        except Exception as e:
            Logger.error(f"AI response error: {e}")
            return self._fallback_info(query)
    
    def _fallback_info(self, query):
        """Fallback to Wikipedia or web search"""
        if WIKIPEDIA_AVAILABLE:
            try:
                summary = wikipedia.summary(query, sentences=2)
                return summary
            except:
                pass
        return f"I'll search for information about {query}."


# ============================================================================
# COMMAND HANDLERS
# ============================================================================
class CommandHandler:
    """Handles various command types"""
    def __init__(self, ai_assistant, tts_engine):
        self.ai = ai_assistant
        self.tts = tts_engine
    
    def handle_system_command(self, text):
        """Handle system commands"""
        text_lower = text.lower()
        
        if any(k in text_lower for k in ['shutdown', 'band kar']):
            self.tts.speak("Shutting down your system in 5 seconds.")
            time.sleep(1)
            os.system("shutdown /s /t 5")
            return True
        
        if any(k in text_lower for k in ['restart', 'reboot']):
            self.tts.speak("Restarting your system in 5 seconds.")
            time.sleep(1)
            os.system("shutdown /r /t 5")
            return True
        
        if 'sleep' in text_lower:
            self.tts.speak("Putting system to sleep.")
            os.system("rundll32.exe powrprof.dll,SetSuspendState 0,1,0")
            return True
        
        if 'lock' in text_lower:
            self.tts.speak("Locking your device.")
            os.system("rundll32.exe user32.dll,LockWorkStation")
            return True
        
        return False
    
    def handle_open_app(self, text):
        """Handle opening applications"""
        text_lower = text.lower()
        
        if any(k in text_lower for k in ['youtube', 'youtube kholo']):
            self.tts.speak("Opening YouTube")
            webbrowser.open("https://www.youtube.com")
            return True
        
        if any(k in text_lower for k in ['google', 'google kholo']):
            self.tts.speak("Opening Google")
            webbrowser.open("https://www.google.com")
            return True
        
        apps = {
            'notepad': r'C:\Windows\System32\notepad.exe',
            'calculator': r'C:\Windows\System32\calc.exe',
            'paint': r'C:\Windows\System32\mspaint.exe',
            'chrome': r'C:\Program Files\Google\Chrome\Application\chrome.exe',
        }
        
        for app_name, app_path in apps.items():
            if app_name in text_lower:
                if os.path.exists(app_path):
                    self.tts.speak(f"Opening {app_name}")
                    subprocess.Popen(app_path)
                    return True
        
        return False
    
    def handle_name(self, text):
        """Handle name setting"""
        text_lower = text.lower()
        
        patterns = [
            r'my name is (\w+)',
            r'call me (\w+)',
            r'mera naam (\w+)',
        ]
        
        import re
        for pattern in patterns:
            match = re.search(pattern, text_lower)
            if match:
                name = match.group(1).capitalize()
                self.ai.memory.set('user_name', name)
                self.tts.speak(f"Nice to meet you, {name}. I'll remember your name.")
                return True
        
        return False
    
    def handle_time(self):
        """Get current time"""
        current_time = datetime.now().strftime("%I:%M %p")
        self.tts.speak(f"It's {current_time}")
        return True
    
    def handle_date(self):
        """Get current date"""
        current_date = datetime.now().strftime("%A, %B %d, %Y")
        self.tts.speak(f"Today is {current_date}")
        return True
    
    def handle_weather(self, text):
        """Get weather information"""
        try:
            city = "your location"
            
            import re
            match = re.search(r'in (\w+)', text.lower())
            if match:
                city = match.group(1)
            
            url = f"https://wttr.in/{city}?format=%C+%t"
            response = requests.get(url, timeout=5)
            weather = response.text.strip()
            
            self.tts.speak(f"The weather in {city} is {weather}")
            return True
        except Exception as e:
            Logger.error(f"Weather error: {e}")
            self.tts.speak("Sorry, I couldn't fetch the weather right now.")
            return False
    
    def handle_screenshot(self):
        """Take a screenshot"""
        if not SCREENSHOT_AVAILABLE:
            self.tts.speak("Screenshot feature is not available.")
            return False
        
        try:
            desktop = Path.home() / "Desktop"
            filename = f"screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            filepath = desktop / filename
            
            pyautogui.screenshot().save(str(filepath))
            self.tts.speak("Screenshot saved to desktop.")
            return True
        except Exception as e:
            Logger.error(f"Screenshot error: {e}")
            self.tts.speak("Failed to take screenshot.")
            return False


# ============================================================================
# MAIN ASSISTANT CONTROLLER
# ============================================================================
class AssistantController:
    """Main controller coordinating all components"""
    def __init__(self):
        Config.ensure_dirs()
        self.tts = TTSEngine()
        self.stt = STTEngine()
        self.ai = AIAssistant()
        self.handler = CommandHandler(self.ai, self.tts)
        Logger.info("Assistant initialized")
    
    def process_command(self, text, lang="en"):
        """Process user command"""
        if not text:
            self.tts.speak("I didn't hear anything. Please try again.")
            return
        
        Logger.info(f"Processing: {text} (lang: {lang})")
        
        intent_data = self.ai.get_intent(text)
        intent = intent_data.get("intent", "unknown")
        
        if intent == "system_command":
            self.handler.handle_system_command(text)
        
        elif intent == "open_app":
            if not self.handler.handle_open_app(text):
                self.tts.speak("I couldn't find that application.")
        
        elif intent == "set_name":
            self.handler.handle_name(text)
        
        elif intent == "time":
            self.handler.handle_time()
        
        elif intent == "date":
            self.handler.handle_date()
        
        elif intent == "weather":
            self.handler.handle_weather(text)
        
        elif intent == "screenshot":
            self.handler.handle_screenshot()
        
        elif intent == "ask_info":
            answer = self.ai.get_ai_response(text, lang)
            self.tts.speak(answer)
        
        else:
            answer = self.ai.get_ai_response(text, lang)
            self.tts.speak(answer)


# ============================================================================
# GUI
# ============================================================================
class OrbSignals(QObject):
    """Signals for thread-safe GUI updates"""
    status_changed = pyqtSignal(str)
    listening_changed = pyqtSignal(bool)


class OrbGUI(QWidget):
    """Modern orb-style GUI"""
    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        self.signals = OrbSignals()
        
        self.phase = 0.0
        self.pulse = 0.0
        self.is_listening = False
        self.status = "Tap the orb to speak"
        
        self._setup_window()
        self._setup_animation()
        
        self.signals.status_changed.connect(self._update_status)
        self.signals.listening_changed.connect(self._update_listening)
        
        Logger.info("GUI initialized")
    
    def _setup_window(self):
        """Setup window properties"""
        self.setWindowTitle("E.D.I Voice Assistant")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | 
            Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.resize(Config.WINDOW_WIDTH, Config.WINDOW_HEIGHT)
        
        screen = QApplication.primaryScreen().geometry()
        x = (screen.width() - self.width()) // 2
        y = (screen.height() - self.height()) // 2
        self.move(x, y)
    
    def _setup_animation(self):
        """Setup animation timer"""
        self.timer = QTimer()
        self.timer.timeout.connect(self._update_animation)
        self.timer.start(30)
    
    def _update_status(self, status):
        """Update status text"""
        self.status = status
        self.update()
    
    def _update_listening(self, listening):
        """Update listening state"""
        self.is_listening = listening
        self.update()
    
    def _update_animation(self):
        """Update animation frame"""
        self.phase += 0.15
        target_pulse = 1.0 if self.is_listening else 0.0
        self.pulse += (target_pulse - self.pulse) * 0.2
        self.update()
    
    def mousePressEvent(self, event):
        """Handle mouse click"""
        pos = event.position()
        x, y = float(pos.x()), float(pos.y())
        cx = float(self.width() // 2)
        cy = 220.0
        
        distance_sq = (x - cx) ** 2 + (y - cy) ** 2
        radius_sq = (Config.ORB_DIAMETER / 2.0) ** 2
        
        if distance_sq <= radius_sq and not self.is_listening:
            threading.Thread(target=self._voice_interaction, daemon=True).start()
    
    def paintEvent(self, event):
        """Draw the orb"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        cx = self.width() // 2
        cy = 220
        base_radius = Config.ORB_DIAMETER // 2
        current_radius = int(base_radius * (1.0 + 0.1 * self.pulse))
        
        for alpha in [140, 100, 60]:
            radius = int(current_radius * (alpha / 100.0))
            painter.setBrush(QColor(90, 170, 255, alpha))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(
                int(cx - radius),
                int(cy - radius),
                int(2 * radius),
                int(2 * radius)
            )
        
        gradient = QRadialGradient(cx, cy, current_radius, 
                                  cx - current_radius * 0.3, 
                                  cy - current_radius * 0.3)
        gradient.setColorAt(0, QColor(255, 255, 255))
        gradient.setColorAt(1, QColor(70, 150, 255))
        painter.setBrush(gradient)
        painter.drawEllipse(
            int(cx - current_radius),
            int(cy - current_radius),
            int(current_radius * 2),
            int(current_radius * 2)
        )
        
        painter.setPen(QColor(230, 240, 255))
        painter.setFont(QFont("Segoe UI", 13))
        text_y = int(cy + current_radius + 25)
        painter.drawText(
            0, text_y, self.width(), 40,
            Qt.AlignmentFlag.AlignHCenter,
            self.status
        )
        
        painter.end()
    
    def _voice_interaction(self):
        """Handle voice interaction"""
        try:
            self.signals.listening_changed.emit(True)
            self.signals.status_changed.emit("Listening...")
            
            self.controller.tts.speak("Yes?")
            time.sleep(0.5)
            
            text, lang = self.controller.stt.listen()
            
            if not text:
                self.controller.tts.speak("I didn't catch that. Please try again.")
                self.signals.status_changed.emit("Tap the orb to speak")
                self.signals.listening_changed.emit(False)
                return
            
            self.signals.status_changed.emit("Processing...")
            self.controller.process_command(text, lang)
            
        except Exception as e:
            Logger.error(f"Voice interaction error: {e}")
            self.controller.tts.speak("Sorry, something went wrong.")
        
        finally:
            self.signals.status_changed.emit("Tap the orb to speak")
            self.signals.listening_changed.emit(False)


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================
def main():
    """Main entry point"""
    Logger.info("Starting E.D.I Voice Assistant")
    
    app = QApplication(sys.argv)
    app.setApplicationName("E.D.I Voice Assistant")
    
    controller = AssistantController()
    gui = OrbGUI(controller)
    gui.show()
    
    controller.tts.speak("Hello, I'm E.D.I. Tap the orb to speak.")
    
    Logger.info("Application started successfully")
    sys.exit(app.exec())


if __name__ == "__main__":
    main()