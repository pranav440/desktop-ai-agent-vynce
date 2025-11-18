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
import urllib.parse
import imaplib
import email
from email.header import decode_header
from email.utils import parseaddr
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
    EMAIL_SETTINGS_FILE = BASE_DIR / "email_settings.json"
    MESSAGES_FILE = BASE_DIR / "messages.json"
    
    # Speech settings
    SPEECH_RATE = 180
    SPEECH_VOLUME = 1.0
    LISTEN_TIMEOUT = 6
    PHRASE_TIME_LIMIT = 12
    CONTINUOUS_SESSION_ENABLED = True
    CONTINUOUS_SESSION_STOP_WORDS = [
        "stop listening",
        "stop session",
        "that's all",
        "nothing else",
        "cancel",
        "exit",
        "bye",
        "goodbye",
        "thank you",
        "thanks"
    ]
    
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
        """Speak text synchronously (main thread)"""
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
Possible intents: open_app, system_command, ask_info, set_name, weather, time, date, screenshot, send_email, file_search, read_messages, music_control, email_check, unknown

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
        
        if any(k in text_lower for k in ['send email', 'write email', 'email bhejo']):
            return {"intent": "send_email", "query": text}
        
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
        
        if any(k in text_lower for k in ['search files', 'find file', 'locate file', 'file search']):
            return {"intent": "file_search", "query": text}
        
        if any(k in text_lower for k in ['read my messages', 'read messages', 'message reader', 'check messages']):
            return {"intent": "read_messages", "query": text}
        
        if any(k in text_lower for k in ['turn on music', 'play music', 'pause music', 'resume music', 'next song', 'previous song']):
            return {"intent": "music_control", "query": text}
        
        if any(k in text_lower for k in ['run email check', 'check my email', 'email status', 'check emails']):
            return {"intent": "email_check", "query": text}
        
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
    
    def compose_email_body(self, subject):
        """Generate a short, properly formatted email body from the subject"""
        default_body = "\n".join([
            "Hello,",
            "",
            f"I'm reaching out regarding \"{subject}\" and wanted to share some context for you to review. "
            f"This note covers the background, current status, and the next steps I'm proposing. "
            "Please take a moment to read through the details below so we can stay aligned.",
            "",
            "First, here is the latest summary of events and relevant information. "
            "I've outlined the key motivations for the change, the progress we've made, "
            "the roadblocks that surfaced, the timelines we are targeting, "
            "and any dependencies we should watch. "
            "Each point reflects what we gathered in the most recent discussions.",
            "",
            "Second, I'd love your perspective on how we should approach the next phase. "
            "I'm proposing that we finalize the requirements, assign owners for the remaining deliverables, "
            "set check-in milestones, identify the support you might need, "
            "track any risks that emerge, and capture feedback after each milestone. "
            "Your approval on this plan would help us move forward smoothly.",
            "",
            "Thanks in advance for your time and guidance.",
            f"{self.memory.get('user_name', 'Your Name')}"
        ])
        
        if not self.groq_client:
            return default_body
        
        prompt = f"""You are an AI email writer. Draft a formal Gmail-ready email about "{subject}" with this exact format:
1. Proper greeting line (e.g., Hello Team,).
2. Paragraph 1: at least 6 sentences (each on its own line) explaining the background/context in a professional tone.
3. Blank line.
4. Paragraph 2: at least 6 sentences (each on its own line) covering next steps, requests, or actions needed.
5. Blank line.
6. Closing line with a professional sign-off (e.g., Thanks, Best regards) followed by a name (no placeholders).

Additional rules:
- Each sentence must be on its own line (no bullet points).
- Total length should be roughly 180-240 words.
- Keep the language clear, polite, and actionable.
- Do not include quoted subject text or placeholders like [Name]."""
        
        try:
            response = self.groq_client.chat.completions.create(
                model=Config.GROQ_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=220
            )
            body = response.choices[0].message.content.strip()
            return body or default_body
        except Exception as e:
            Logger.error(f"AI email compose error: {e}")
            return default_body
    
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
        
        if any(k in text_lower for k in ['gmail', 'email']):
            self.tts.speak("Opening Gmail in your browser.")
            webbrowser.open("https://mail.google.com/mail/u/0/#inbox")
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
    
    def handle_music_control(self, text):
        """Control music playback or launch music service"""
        text_lower = text.lower()
        
        if any(k in text_lower for k in ['turn on music', 'play music', 'start music', 'music on']):
            self.tts.speak("Turning on music in your browser.")
            webbrowser.open("https://music.youtube.com/")
            return True
        
        if any(k in text_lower for k in ['pause music', 'stop music', 'music pause']):
            if self._press_media_key('PLAY_PAUSE'):
                self.tts.speak("Paused music.")
            else:
                self.tts.speak("I tried to pause the music, but I couldn't control playback on this device.")
            return True
        
        if any(k in text_lower for k in ['resume music', 'continue music']):
            if self._press_media_key('PLAY_PAUSE'):
                self.tts.speak("Resuming music.")
            else:
                self.tts.speak("I tried to resume the music, but I couldn't control playback on this device.")
            return True
        
        if any(k in text_lower for k in ['next song', 'next track']):
            if self._press_media_key('NEXT'):
                self.tts.speak("Skipping to the next track.")
            else:
                self.tts.speak("I couldn't skip the track on this device.")
            return True
        
        if any(k in text_lower for k in ['previous song', 'previous track', 'back song']):
            if self._press_media_key('PREV'):
                self.tts.speak("Going back to the previous track.")
            else:
                self.tts.speak("I couldn't go to the previous track on this device.")
            return True
        
        self.tts.speak("Tell me to play music, pause, resume, next or previous track.")
        return False
    
    def _press_media_key(self, key):
        """Simulate media key presses on Windows"""
        if sys.platform != "win32":
            return False
        
        key_map = {
            'PLAY_PAUSE': 0xB3,
            'NEXT': 0xB0,
            'PREV': 0xB1,
        }
        vk_code = key_map.get(key)
        if not vk_code:
            return False
        
        try:
            import ctypes
            user32 = ctypes.windll.user32
            user32.keybd_event(vk_code, 0, 0, 0)
            user32.keybd_event(vk_code, 0, 2, 0)
            return True
        except Exception as e:
            Logger.error(f"Media key error: {e}")
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
        self._stop_keywords = [kw.lower() for kw in Config.CONTINUOUS_SESSION_STOP_WORDS]
        Logger.info("Assistant initialized")
    
    def _prompt_for_input(self, prompt_text, max_retries=2):
        """Speak a prompt and capture voice input with retry logic"""
        for attempt in range(max_retries + 1):
            self.tts.speak(prompt_text)
            time.sleep(0.8)  # Give more time for TTS to finish
            Logger.info(f"Listening for input (attempt {attempt + 1})...")
            text, _ = self.stt.listen()
            text = text.strip()
            if text:
                Logger.info(f"Captured input: {text}")
                return text
            else:
                if attempt < max_retries:
                    self.tts.speak("I didn't catch that. Please repeat.")
                    time.sleep(0.5)
        return ""
    
    def _handle_send_email(self):
        """Voice-guided Gmail compose that auto-writes body from AI"""
        Logger.info("Starting AI email composition flow")
        self.tts.speak("Sure. Tell me the subject for your email.")
        time.sleep(0.4)
        
        # Only capture subject; user will enter recipient later in Gmail
        subject = self._prompt_for_input("What should be the subject of the email?")
        if not subject:
            self.tts.speak("I couldn't get the subject. Email composition cancelled.")
            Logger.error("Failed to get email subject")
            return
        
        Logger.info(f"Email subject: {subject}")
        self.tts.speak(f"Subject is {subject}.")
        self.tts.speak("Great. Let me draft the email for you.")
        body = self.ai.compose_email_body(subject)
        Logger.info("Generated AI email body.")
        
        # Build Gmail compose URL (recipient left blank for user to fill)
        params = {
            "view": "cm",
            "fs": "1",
            "su": subject,
            "body": body
        }
        query = urllib.parse.urlencode(params, doseq=True, quote_via=urllib.parse.quote)
        compose_url = f"https://mail.google.com/mail/?{query}"
        
        # Open in default browser
        try:
            webbrowser.open(compose_url)
            Logger.info(f"Opened Gmail compose URL: {compose_url}")
            self.tts.speak("All set. I've opened Gmail with your subject and a drafted email. Just enter the recipient and hit send when you're ready.")
        except Exception as e:
            Logger.error(f"Failed to open Gmail: {e}")
            self.tts.speak("I drafted your email but couldn't open Gmail automatically. Please try again.")
    
    def _handle_file_search(self, text):
        """Search common directories for files matching a keyword"""
        import re
        term = ""
        if text:
            match = re.search(r'(?:for|named)\s+([A-Za-z0-9_. -]+)', text.lower())
            if match:
                term = match.group(1).strip()
        if not term:
            term = self._prompt_for_input("What file name should I search for? You can say part of the name.")
        if not term:
            self.tts.speak("I couldn't get a file name. Cancelling search.")
            return
        
        self.tts.speak(f"Searching for files containing {term}.")
        matches = self._search_directories(term.lower())
        if not matches:
            self.tts.speak(f"I couldn't find any files matching {term} on your Desktop, Documents, or Downloads.")
            return
        
        max_report = min(len(matches), 3)
        self.tts.speak(f"I found {len(matches)} matching files. Here are the first {max_report}.")
        for idx, path in enumerate(matches[:max_report], start=1):
            self.tts.speak(f"{idx}. {path.name} in {path.parent.name}.")
        if len(matches) > max_report:
            self.tts.speak("Ask me to search again if you'd like me to open one of them.")
    
    def _search_directories(self, term, max_results=5):
        """Search desktop, documents, and downloads for matches"""
        search_dirs = [
            Path.home() / "Desktop",
            Path.home() / "Documents",
            Path.home() / "Downloads",
        ]
        matches = []
        for base in search_dirs:
            if not base.exists():
                continue
            try:
                for root, _, files in os.walk(base):
                    for filename in files:
                        if term in filename.lower():
                            matches.append(Path(root) / filename)
                            if len(matches) >= max_results:
                                return matches
                    if len(matches) >= max_results:
                        break
            except Exception as e:
                Logger.error(f"File search error in {base}: {e}")
        return matches
    
    def _handle_read_messages(self):
        """Read stored messages aloud"""
        messages = self._load_messages()
        if not messages:
            self.tts.speak(f"I don't have any saved messages yet. Add them to {Config.MESSAGES_FILE} and ask me again.")
            return
        
        count = min(len(messages), 3)
        self.tts.speak(f"Reading the latest {count} messages.")
        for message in messages[:count]:
            sender = message.get("from", "Unknown")
            timestamp = message.get("time", "")
            body = message.get("text", "")
            if timestamp:
                self.tts.speak(f"From {sender} at {timestamp}. {body}")
            else:
                self.tts.speak(f"From {sender}. {body}")
    
    def _load_messages(self):
        """Load messages from disk"""
        if Config.MESSAGES_FILE.exists():
            try:
                with open(Config.MESSAGES_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        return data
            except Exception as e:
                Logger.error(f"Failed to load messages: {e}")
        return []
    
    def _handle_email_check(self):
        """Check for unread emails via IMAP or open Gmail"""
        settings = self._load_email_settings()
        if not settings:
            self.tts.speak("Email check isn't configured yet. I've opened Gmail with unread emails so you can review them.")
            webbrowser.open("https://mail.google.com/mail/u/0/#search/is%3Aunread")
            return
        
        try:
            host = settings.get("imap_host")
            email_addr = settings.get("email")
            password = settings.get("password")
            if not all([host, email_addr, password]):
                raise ValueError("Missing email settings.")
            
            port = settings.get("imap_port", 993)
            folder = settings.get("folder", "INBOX")
            
            imap = imaplib.IMAP4_SSL(host, port)
            imap.login(email_addr, password)
            imap.select(folder)
            
            status, data = imap.search(None, "UNSEEN")
            if status != "OK":
                raise ValueError("Unable to search mailbox.")
            
            ids = data[0].split()
            unread_count = len(ids)
            if unread_count == 0:
                self.tts.speak("You have no unread emails.")
            else:
                self.tts.speak(f"You have {unread_count} unread emails. Here are the latest {min(3, unread_count)}.")
                for msg_id in ids[-3:]:
                    status, msg_data = imap.fetch(msg_id, "(BODY.PEEK[HEADER])")
                    if status != "OK":
                        continue
                    raw_email = msg_data[0][1]
                    msg = email.message_from_bytes(raw_email)
                    subject = self._decode_header_value(msg.get("Subject", "No subject"))
                    sender_name = parseaddr(msg.get("From", "Unknown"))[0] or "Unknown sender"
                    self.tts.speak(f"From {sender_name}. Subject: {subject}.")
            imap.close()
            imap.logout()
        except Exception as e:
            Logger.error(f"Email check failed: {e}")
            self.tts.speak("I couldn't check your email automatically, so I opened Gmail for you.")
            webbrowser.open("https://mail.google.com/mail/u/0/#search/is%3Aunread")
    
    def _load_email_settings(self):
        """Load email configuration for IMAP access"""
        if Config.EMAIL_SETTINGS_FILE.exists():
            try:
                with open(Config.EMAIL_SETTINGS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        return data
            except Exception as e:
                Logger.error(f"Failed to load email settings: {e}")
        return None
    
    def _decode_header_value(self, value):
        """Decode MIME-encoded email headers"""
        if not value:
            return ""
        parts = decode_header(value)
        decoded_segments = []
        for segment, charset in parts:
            if isinstance(segment, bytes):
                try:
                    decoded_segments.append(segment.decode(charset or "utf-8", errors="ignore"))
                except Exception:
                    decoded_segments.append(segment.decode("utf-8", errors="ignore"))
            else:
                decoded_segments.append(segment)
        return " ".join(decoded_segments).strip()
    
    def start_voice_session(self, initial_text, initial_lang):
        """Process first command and optionally stay in continuous voice mode"""
        if not Config.CONTINUOUS_SESSION_ENABLED:
            self.process_command(initial_text, initial_lang)
            return
        self._run_continuous_session(initial_text, initial_lang)
    
    def _run_continuous_session(self, initial_text, initial_lang):
        """Keep listening for follow-up commands until user says stop"""
        text = initial_text
        lang = initial_lang
        first_turn = True
        
        while True:
            if not text:
                break
            self.process_command(text, lang)
            if not Config.CONTINUOUS_SESSION_ENABLED:
                break
            
            if first_turn:
                prompt = "Voice session is active. Speak your next command or say stop to finish."
                first_turn = False
            else:
                prompt = "I'm still listening. Say stop if you're done."
            self.tts.speak(prompt)
            time.sleep(0.4)
            
            text, lang = self.stt.listen()
            text = text.strip()
            if not text:
                self.tts.speak("Okay, ending voice session. Tap the orb again when you need me.")
                break
            if self._is_stop_command(text):
                self.tts.speak("All set. Just tap the orb when you need me again.")
                break
    
    def _is_stop_command(self, text):
        """Check if user requested to end the continuous session"""
        lowered = (text or "").lower().strip()
        if not lowered:
            return False
        if lowered in {"stop", "exit", "quit"}:
            return True
        for phrase in self._stop_keywords:
            if phrase in lowered:
                return True
        return False
    
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
        
        elif intent == "send_email":
            self._handle_send_email()
        
        elif intent == "file_search":
            self._handle_file_search(text)
        
        elif intent == "read_messages":
            self._handle_read_messages()
        
        elif intent == "music_control":
            self.handler.handle_music_control(text)
        
        elif intent == "email_check":
            self._handle_email_check()
        
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
            self.controller.start_voice_session(text, lang)
            
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
    
    controller.tts.speak("Hello, I'm E.D.I. Tap the orb once to start and keep talking until you say stop.")
    
    Logger.info("Application started successfully")
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
