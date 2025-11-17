"""
E.D.I - Smart Voice Assistant
Version: Human-like, Female Voice Edition
Multilanguage detection (English, Hindi, Marathi, Gujarati, Punjabi).
Keeps the original GUI & behavior, adds language detection and
multilingual phrase handling. Uses pyttsx3 for TTS.
"""

import os, sys, re, threading, time, json, webbrowser, requests, pyjokes, wikipedia, pyautogui, subprocess
from datetime import datetime

# STT / TTS
import speech_recognition as sr
import pyttsx3

# GUI
from PyQt6.QtCore import Qt, QTimer, QRectF
from PyQt6.QtGui import QPainter, QColor, QBrush, QRadialGradient, QFont, QPainterPath
from PyQt6.QtWidgets import QApplication, QWidget

# Brightness control (optional)
try:
    import screen_brightness_control as sbc
except Exception:
    sbc = None

# Language detection (optional, used if installed)
try:
    from langdetect import detect, DetectorFactory
    DetectorFactory.seed = 0
    LANGDET_AVAILABLE = True
except Exception:
    LANGDET_AVAILABLE = False

# ---------- SETTINGS ----------
# Default recognizer language remains English-India for STT (you can change)
LANGUAGE = "en-IN"
MAX_PHRASE_TIME = 10
ORB_DIAMETER = 140  # smaller orb
MEMORY_FILE = "edi_memory.json"
# ------------------------------

# ---------- TTS ----------
tts_engine = pyttsx3.init()
tts_engine.setProperty("rate", 165)
tts_engine.setProperty("volume", 1.0)

# Try setting female voice
voices = tts_engine.getProperty("voices")
for v in voices:
    try:
        name_lower = (v.name or "").lower()
        if "female" in name_lower or "zira" in name_lower or "microsoft sapi" in name_lower:
            tts_engine.setProperty("voice", v.id)
            break
    except Exception:
        continue

def speak(text):
    """Speak in background thread (non-blocking)."""
    def _run(s):
        print("E.D.I:", s)
        try:
            tts_engine.say(s)
            tts_engine.runAndWait()
        except Exception as e:
            print("TTS error:", e)
    threading.Thread(target=_run, args=(text,), daemon=True).start()


# ---------- Memory ----------
def load_memory():
    if os.path.exists(MEMORY_FILE):
        try:
            return json.load(open(MEMORY_FILE, "r", encoding="utf-8"))
        except:
            return {}
    return {}

def save_memory(mem):
    try:
        json.dump(mem, open(MEMORY_FILE, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    except Exception as e:
        print("Memory save error:", e)

memory = load_memory()


# ---------- Speech Recognition ----------
recognizer = sr.Recognizer()

def listen_and_recognize(timeout=5, phrase_time_limit=MAX_PHRASE_TIME):
    """
    Listen and return (text, lang_code).
    - text: recognized text (string, or "" if not recognized)
    - lang_code: 'en', 'hi', 'mr', 'gu', 'pa' where possible; fallback 'en'
    """
    mic = sr.Microphone()
    with mic as source:
        recognizer.adjust_for_ambient_noise(source, duration=0.6)
        try:
            audio = recognizer.listen(source, timeout=timeout, phrase_time_limit=phrase_time_limit)
        except sr.WaitTimeoutError:
            print("[TIMEOUT] No speech detected within timeout period")
            speak("I didn't hear anything. Please try again.")
            return "", "en"
    # try to recognize (default service: Google Web Speech)
    try:
        # We try without forcing language so Google may auto-detect -- but we keep fallback
        text = recognizer.recognize_google(audio)
        text = text.strip()
        print("User:", text)
    except sr.UnknownValueError:
        print("[RECOGNITION ERROR] Could not understand audio - please speak clearly")
        speak("Sorry, I didn't understand that. Can you repeat please?")
        return "", "en"
    except sr.RequestError as e:
        print(f"[REQUEST ERROR] {e}")
        speak("Speech recognition service is not reachable right now.")
        return "", "en"
    # detect language code using langdetect if available
    lang_code = "en"
    if LANGDET_AVAILABLE and text:
        try:
            detected = detect(text)
            # map to our short codes for supported Indian languages
            if detected.startswith("hi"):
                lang_code = "hi"
            elif detected.startswith("mr"):
                lang_code = "mr"
            elif detected.startswith("gu"):
                lang_code = "gu"
            elif detected.startswith("pa"):
                lang_code = "pa"
            else:
                lang_code = "en"
        except Exception:
            lang_code = "en"
    else:
        # Basic heuristic: check for common Devanagari characters (if user speaks in native script)
        if re.search(r"[\u0900-\u097F]", text):
            # Devanagari -> likely Hindi/Marathi; choose 'hi' unless Marathi-specific keywords appear
            if re.search(r"\b(पुणे|पुणे)\b", text, re.IGNORECASE):
                lang_code = "mr" if "पुणे" in text else "hi"
            else:
                lang_code = "hi"
        else:
            # also check for transliterated keywords that you used earlier (chalu, kara, vadhva, etc.)
            low = text.lower()
            if any(k in low for k in ["chalu", "chalu kar", "chalu kara", "chalu karo", "khol", "kholo", "kholoo"]):
                # could be Hindi/Marathi transliteration -> pick hi (works for processing)
                lang_code = "hi"
            elif any(k in low for k in ["vadhva", "vadhva", "vadhava", "vadhवा", "vadhav"]):
                lang_code = "mr"
            else:
                lang_code = "en"
    return text, lang_code


# ---------- Utility ----------
def word_to_number(text):
    words = {
        "zero":0,"one":1,"two":2,"three":3,"four":4,"five":5,"six":6,"seven":7,
        "eight":8,"nine":9,"ten":10,"twenty":20,"thirty":30,"forty":40,"fifty":50,
        "sixty":60,"seventy":70,"eighty":80,"ninety":90,"hundred":100,
        # Hindi/Marathi transliterations (common)
        "ek":1,"do":2,"teen":3,"char":4,"paanch":5,"chhe":6,"saat":7,"aath":8,"nau":9,"dus":10,
        "sattar":70,"sau":100,"sath":70,
        # Hindi words (Devanagari) — allow numeric regex anyway
    }
    # check numeric digits first
    m = re.search(r"\b(\d{1,3})\b", text)
    if m:
        return int(m.group(1))
    # fallback to word mapping
    total = None
    for w, n in words.items():
        if w in text.lower():
            total = n
    return total


# ---------- Multilingual response templates ----------
# Keep simple templates for common responses in each supported language.
TEMPLATES = {
    "en": {
        "greet": "Hey {name}, how are you doing?" ,
        "greet_no_name": "Hey there, how are you doing?",
        "remembered_name": "Nice to meet you, {name}. I'll remember your name.",
        "unknown_name": "I don't know your name yet.",
        "brightness_increased": "Brightness increased.",
        "brightness_decreased": "Brightness decreased.",
        "brightness_set": "Brightness set to {n} percent.",
        "brightness_no_support": "Brightness control isn’t supported on this system.",
        "listening_error": "I didn't catch that. Please tap and try again.",
        "weather_error": "Sorry, I couldn't fetch the weather right now.",
        "opening": "Opening {what}.",
        "time": "It's {time}.",
        "date": "Today is {date}.",
        "screenshot": "Screenshot saved to Desktop."
    },
    "hi": {
        "greet": "नमस्ते {name}, आप कैसे हैं?",
        "greet_no_name": "नमस्ते, मैं कैसे मदद कर सकती हूँ?",
        "remembered_name": "मिलकर अच्छा लगा, {name}. मैं याद रखूंगी।",
        "unknown_name": "मैं आपका नाम अभी तक नहीं जानती।",
        "brightness_increased": "ब्राइटनेस बढ़ा दी गई।",
        "brightness_decreased": "ब्राइटनेस घटा दी गई।",
        "brightness_set": "ब्राइटनेस {n} प्रतिशत पर सेट कर दी गई है।",
        "brightness_no_support": "इस सिस्टम पर ब्राइटनेस कंट्रोल उपलब्ध नहीं है।",
        "listening_error": "मैंने नहीं सुना। कृपया फिर से कोशिश करें।",
        "weather_error": "मौसम जानकारी नहीं मिल पाई।",
        "opening": "{what} खोल रहा/रही हूँ।",
        "time": "समय है {time}.",
        "date": "आज तारीख है {date}.",
        "screenshot": "स्क्रीनशॉट डेस्कटॉप पर सेव कर दिया गया है।"
    },
    "mr": {
        "greet": "हॅलो {name}, तुम्ही कसे आहात?",
        "greet_no_name": "हॅलो, मी कशी मदत करू शकते?",
        "remembered_name": "तुमची ओळख करून आनंद झाला, {name}. मी लक्षात ठेवेन.",
        "unknown_name": "मला तुमचे नाव अजून माहित नाही.",
        "brightness_increased": "प्रकाशमान वाढवले आहे.",
        "brightness_decreased": "प्रकाशमान घटवले आहे.",
        "brightness_set": "प्रकाशमान {n} टक्क्यावर सेट केले आहे.",
        "brightness_no_support": "या डिव्हाइसवर ब्राइटनेस कंट्रोल उपलब्ध नाही.",
        "listening_error": "मला ऐकू आले नाही. पुन्हा प्रयत्न करा.",
        "weather_error": "हवामान माहिती मिळाली नाही.",
        "opening": "{what} उघडत आहे.",
        "time": "वेळ आहे {time}.",
        "date": "आज तारीख आहे {date}.",
        "screenshot": "स्क्रीनशॉट डेस्कटॉपवर सेव्ह केला आहे."
    },
    "gu": {
        "greet": "હેલ્લો {name}, તમે કેમ છો?",
        "greet_no_name": "હાય, હું કેમ મદદ કરી શકું?",
        "remembered_name": "તમને મળીને આનંદ થયો, {name}. હું યાદ રાખીશ.",
        "unknown_name": "હું તમારું નામ હજુ નથી જાણતી.",
        "brightness_increased": "બ્રાઇટનેસ વધારી ગઇ છે.",
        "brightness_decreased": "બ્રાઇટનેસ ઘટાડી ગઇ છે.",
        "brightness_set": "બ્રાઇટનેસ {n} ટકા પર સેટ કરી છે.",
        "brightness_no_support": "આ ડિવાઇસ પર બ્રાઇટનેસ નિયંત્રણ ઉપલબ્ધ નથી.",
        "listening_error": "મને સાંભળાયો નહીં. ફરી પ્રયત્ન કરો.",
        "weather_error": "હવામાન માહિતી મેળવી શકાતી નથી.",
        "opening": "{what} ખોલી રહ્યો/રહી છું.",
        "time": "સમય છે {time}.",
        "date": "આજની તારીખ છે {date}.",
        "screenshot": "સ્ક્રીનશૉટ ડેસ્કટોપ પર સેઈવ થયું."
    },
    "pa": {
        "greet": "ਹੈਲੋ {name}, ਤੁਸੀਂ ਕਿਵੇਂ ਹੋ?",
        "greet_no_name": "ਸਤ ਸ੍ਰੀ ਅਕਾਲ, ਮੈਂ ਕਿਵੇਂ ਮਦਦ ਕਰ ਸਕਦੀ ਹਾਂ?",
        "remembered_name": "ਤੁਹਾਨੂੰ ਮਿਲ ਕੇ ਚੰਗਾ ਲੱਗਿਆ, {name}. ਮੈਂ یاد رکھਾਂ گی.",
        "unknown_name": "ਮੈਂ ਤੁਹਾਡਾ ਨਾਮ ਨਹੀਂ ਜਾਣਦੀ.",
        "brightness_increased": "ਚਮਕ ਵਧਾਈ ਗਈ।",
        "brightness_decreased": "ਚਮਕ ਘਟਾਈ ਗਈ।",
        "brightness_set": "ਚਮਕ {n} ਫੀਸਦ 'ਤੇ ਸੈਟ ਕੀਤੀ ਗਈ ਹੈ।",
        "brightness_no_support": "ਇਸ ਡਿਵਾਈਸ 'ਤੇ ਚਮਕ ਕੰਟਰੋਲ ਉਪਲਬਧ ਨਹੀਂ ਹੈ।",
        "listening_error": "ਮੈਂ ਨਹੀਂ ਸੁਣਿਆ। ਦੁਬਾਰਾ ਕੋਸ਼ਿਸ਼ ਕਰੋ।",
        "weather_error": "ਮੌਸਮ ਦੀ ਜਾਣਕਾਰੀ ਨਹੀਂ ਮਿਲੀ।",
        "opening": "{what} ਖੋਲ੍ਹ ਰਿਹਾ/ਰਹੀ ਹਾਂ।",
        "time": "ਸਮਾਂ ਹੈ {time}.",
        "date": "ਅੱਜ ਦੀ ਤਾਰੀਖ ਹੈ {date}.",
        "screenshot": "ਸਕਰੀਨਸ਼ਾਟ ਡੈਸਕਟਾਪ 'ਤੇ ਸੇਵ ਕੀਤਾ ਗਿਆ ਹੈ।"
    }
}

# helper to fetch template safely
def tpl(lang, key, **kwargs):
    if lang not in TEMPLATES:
        lang = "en"
    return TEMPLATES[lang].get(key, TEMPLATES["en"].get(key,"")).format(**kwargs)


# ---------- Multilingual keyword maps ----------
# Each intent maps to lists of keywords/phrases (in lower-case/transliterated)
INTENTS = {
    "greet": [
        "hello","hi","hey","namaste","namaskar","hey edi","hello edi"
    ],
    "name_set": [
        "my name is", "mera naam", "mera naam hai", "my name's", "मेरा नाम", "माझं नाव", "माझं नाव आहे"
    ],
    "what_is_my_name": [
        "what is my name", "who am i", "tumhara naam", "mera naam kya", "माझे नाव काय", "माझं नाव काय"
    ],
    "brightness_up": [
        "increase brightness", "brightness up", "brightness increase",
        "brightness badhao", "brightness vadhva", "brightness वाढवा", "ujala badhao", "brightness वाढवा",
        "brightness वाढवा", "brightness वाढवा", "brightness वाढवा"
    ],
    "brightness_down": [
        "decrease brightness", "brightness down", "brightness decrease",
        "brightness ghatado", "brightness kami kara", "brightness कमी करा"
    ],
    "brightness_set": [
        "set brightness to", "set brightness", "brightness to", "set brightness", "brightness set",
        "brightness ko", "brightness ko", "brightness %", "brightness percent", "brightness पर"
    ],
    "open_youtube": [
        "open youtube","youtube","youtube chalu","youtube chalu kar","youtube chalu kara","youtube kholo","youtube kholo"
    ],
    "open_google": [
        "open google","google kholo","google open","open google"
    ],
    "open_notepad": [
        "open notepad","notepad kholo","open notepad","notepad open"
    ],
    "open_calculator": [
        "open calculator","calculator kholo","open calc","open calculator"
    ],
    "open_whatsapp": [
        "open whatsapp","whatsapp kholo","whatsapp open","whatsapp chalu","whatsapp","message"
    ],
    "open_spotify": [
        "open spotify","spotify kholo","spotify open","spotify chalu","spotify","music","play music"
    ],
    "send_whatsapp": [
        "send message","send whatsapp","message to","send to","whatsapp message","send whatsapp message"
    ],
    "time": ["time","what time","samay","kitne baje","وقت"],
    "date": ["date","today","aaj ki tareekh","aaj"],
    "joke": ["joke","chutkula","mazak"],
    "screenshot": ["screenshot","take screenshot","screen shot","स्क्रीनशॉट"]
}


# ---------- Info Helpers ----------
def get_weather(city="your location"):
    try:
        url = f"https://wttr.in/{city}?format=%C+%t"
        res = requests.get(url, timeout=5).text
        return res if res else tpl("en","weather_error")
    except:
        return tpl("en","weather_error")


def quick_search(query):
    try:
        summary = wikipedia.summary(query, sentences=2)
        return summary
    except:
        return None


# ---------- WhatsApp Helper Functions ----------
def load_contacts():
    """Load contacts from contacts.json file"""
    try:
        contacts_file = os.path.join(os.path.dirname(__file__), "contacts.json")
        if os.path.exists(contacts_file):
            with open(contacts_file, 'r', encoding='utf-8') as f:
                return json.load(f)
    except:
        pass
    return {}


def send_whatsapp_message(contact_name, message):
    """Send WhatsApp message to a contact"""
    try:
        contacts = load_contacts()
        contact_name_lower = contact_name.lower().strip()
        
        # Find contact (case-insensitive)
        phone_number = None
        for name, number in contacts.items():
            if name.lower() == contact_name_lower:
                phone_number = number
                break
        
        if not phone_number:
            return f"Contact {contact_name} not found. Please add it to contacts.json"
        
        # Format the URL for WhatsApp Web
        # WhatsApp Web URL format: https://web.whatsapp.com/send?phone=PHONENUMBER&text=MESSAGE
        phone_number = phone_number.replace("+", "").replace(" ", "").replace("-", "")
        
        # Ensure it starts with country code (default: +91 for India)
        if not phone_number.startswith("91") and not phone_number.startswith("+"):
            phone_number = "91" + phone_number
        
        message_encoded = requests.utils.quote(message)
        whatsapp_url = f"https://web.whatsapp.com/send?phone={phone_number}&text={message_encoded}"
        
        webbrowser.open(whatsapp_url)
        return f"Opening WhatsApp to send message to {contact_name}"
    
    except Exception as e:
        return f"Error sending WhatsApp message: {str(e)}"


# ---------- Core Logic ----------
def process_command(txt, lang="en"):
    low = txt.lower().strip()
    print("Processing:", low, "lang:", lang)

    # GREET
    if any(k in low for k in INTENTS["greet"]):
        name = memory.get("user_name", "")
        if name:
            speak(tpl(lang, "greet", name=name) if tpl(lang,"greet") else tpl("en","greet").format(name=name))
        else:
            speak(tpl(lang, "greet_no_name"))
        return

    # NAME SET
    if any(k in low for k in INTENTS["name_set"]):
        # try to extract the name after the phrase
        m = re.search(r"(?:my name is|mera naam hai|mera naam|मेरा नाम|माझं नाव|माझं नाव आहे)\s+(.+)", low)
        if m:
            name = m.group(1).strip().split()[0].capitalize()
        else:
            # fallback: last word
            name = low.split()[-1].capitalize()
        memory["user_name"] = name
        save_memory(memory)
        speak(tpl(lang, "remembered_name", name=name))
        return

    if any(k in low for k in INTENTS["what_is_my_name"]):
        name = memory.get("user_name")
        if name:
            speak(tpl(lang, "unknown_name").replace("I don't know your name yet.", f"Your name is {name}.") if lang=="en" and name else tpl(lang,"unknown_name"))
        else:
            speak(tpl(lang, "unknown_name"))
        return

    # BRIGHTNESS - set/increase/decrease
    if "brightness" in low or any(term in low for term in ["chamak","ujala","brightness","प्रकाश","प्रकाशमान","चमक"]):
        # try exact number
        n = word_to_number(low)
        if n is not None and 0 <= n <= 100:
            try:
                if sbc:
                    sbc.set_brightness(n)
                else:
                    # windows fallback using powershell (best-effort)
                    if os.name == "nt":
                        ps = f"(Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightnessMethods).WmiSetBrightness(1,{n})"
                        os.system(f"powershell -Command \"{ps}\"")
                speak(tpl(lang, "brightness_set", n=n))
            except Exception:
                speak(tpl(lang, "brightness_no_support"))
            return
        # increase
        if any(kw in low for kw in INTENTS["brightness_up"]):
            try:
                if sbc:
                    cur = sbc.get_brightness()[0]
                    new = min(100, cur + 20)
                    sbc.set_brightness(new)
                else:
                    new = None
                speak(tpl(lang, "brightness_increased"))
            except Exception:
                speak(tpl(lang, "brightness_no_support"))
            return
        # decrease
        if any(kw in low for kw in INTENTS["brightness_down"]):
            try:
                if sbc:
                    cur = sbc.get_brightness()[0]
                    new = max(0, cur - 20)
                    sbc.set_brightness(new)
                else:
                    new = None
                speak(tpl(lang, "brightness_decreased"))
            except Exception:
                speak(tpl(lang, "brightness_no_support"))
            return
        # not enough info
        speak(tpl(lang, "brightness_no_support"))
        return

    # WEATHER
    if "weather" in low or "temperature" in low or "mausam" in low or "hava" in low or "hawaa" in low:
        # extract city: look for "in X" (English) or "mein X" (Hindi) or "मध्ये X" (Marathi)
        city = None
        m_en = re.search(r"in ([a-zA-Z ]+)", low)
        m_hi = re.search(r"mein\s+([a-zA-Z\u0900-\u097F ]+)", low)
        if m_en:
            city = m_en.group(1).strip()
        elif m_hi:
            city = m_hi.group(1).strip()
        else:
            city = "your location"
        res = get_weather(city)
        speak(res if lang == "en" else (res))  # templates are not localized for wttr.in
        return

    # OPEN APPS / WEBSITES
    if any(k in low for k in INTENTS["open_youtube"]):
        speak(tpl(lang, "opening", what="YouTube"))
        webbrowser.open("https://youtube.com")
        return

    if any(k in low for k in INTENTS["open_google"]):
        speak(tpl(lang, "opening", what="Google"))
        webbrowser.open("https://google.com")
        return

    if any(k in low for k in INTENTS["open_notepad"]):
        speak(tpl(lang, "opening", what="Notepad"))
        os.system("notepad")
        return

    if any(k in low for k in INTENTS["open_calculator"]):
        speak(tpl(lang, "opening", what="Calculator"))
        os.system("calc")
        return

    if any(k in low for k in INTENTS["open_whatsapp"]):
        speak(tpl(lang, "opening", what="WhatsApp"))
        username = os.getenv('USERNAME', 'ASUS')
        whatsapp_path = fr"C:\Users\{username}\AppData\Local\WhatsApp\WhatsApp.exe"
        if os.path.exists(whatsapp_path):
            subprocess.Popen(whatsapp_path)
        else:
            webbrowser.open("https://web.whatsapp.com")
        return

    if any(k in low for k in INTENTS["open_spotify"]):
        speak(tpl(lang, "opening", what="Spotify"))
        username = os.getenv('USERNAME', 'ASUS')
        spotify_path = fr"C:\Users\{username}\AppData\Roaming\Spotify\spotify.exe"
        if os.path.exists(spotify_path):
            subprocess.Popen(spotify_path)
        else:
            webbrowser.open("https://open.spotify.com")
        return

    if any(k in low for k in INTENTS["send_whatsapp"]):
        speak(tpl(lang, "processing", action="WhatsApp message"))
        speak("Please say the contact name followed by the message.")
        
        # Listen for contact name
        contact_name = listen_and_recognize()
        if not contact_name:
            speak("Sorry, I couldn't hear the contact name.")
            return
        
        speak(f"Sending message to {contact_name}. Please say your message.")
        
        # Listen for message
        message = listen_and_recognize()
        if not message:
            speak("Sorry, I couldn't hear the message.")
            return
        
        result = send_whatsapp_message(contact_name, message)
        speak(result)
        return

    # TIME / DATE
    if any(k in low for k in INTENTS["time"]):
        speak(tpl(lang, "time", time=datetime.now().strftime("%I:%M %p")))
        return
    if any(k in low for k in INTENTS["date"]):
        speak(tpl(lang, "date", date=datetime.now().strftime("%A, %B %d, %Y")))
        return

    # JOKE
    if any(k in low for k in INTENTS["joke"]):
        # pyjokes only supports English jokes; keep it English or map a simple localized joke
        joke = pyjokes.get_joke()
        if lang == "en":
            speak(joke)
        else:
            # simple fallback phrase in local language then English joke
            speak(joke)
        return

    # SCREENSHOT
    if any(k in low for k in INTENTS["screenshot"]):
        try:
            path = os.path.join(os.path.expanduser("~"), "Desktop", f"screenshot_{datetime.now().strftime('%H%M%S')}.png")
            pyautogui.screenshot().save(path)
            speak(tpl(lang, "screenshot"))
        except Exception:
            speak(tpl(lang, "screenshot"))
        return

    # SEARCH / PLAY
    if low.startswith("search ") or "search " in low or low.startswith("google "):
        # extract query
        q = re.sub(r"^(search|google)\s+", "", low).strip()
        if not q:
            speak(tpl(lang, "listening_error"))
            return
        speak(tpl(lang, "opening", what=f"search for {q}"))
        webbrowser.open(f"https://google.com/search?q={requests.utils.quote(q)}")
        return

    if low.startswith("play "):
        q = low.replace("play ", "").strip()
        if q:
            speak(tpl(lang, "opening", what=f"playing {q}"))
            webbrowser.open(f"https://www.youtube.com/results?search_query={requests.utils.quote(q)}")
            return

    # fallback: quick search (wikipedia) or web search
    ans = quick_search(low)
    if ans:
        speak(ans)
    else:
        speak(tpl(lang, "opening", what="web results"))
        webbrowser.open(f"https://google.com/search?q={requests.utils.quote(low)}")


# ---------- GUI ----------
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
        # note: PyQt6 returns QPointF for position() - convert to floats safely
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
            # compute rad as integer
            rad = int(curR * (a/100.0))
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
            max_retries = 2  # Try up to 2 times if speech not recognized
            retry_count = 0
            
            while retry_count < max_retries:
                self.is_listening = True
                self.status = "Listening..."
                self.update()
                speak("Yes?")
                
                txt, lang = listen_and_recognize()
                
                if txt:  # Successfully recognized text
                    self.status = "Processing..."
                    self.update()
                    process_command(txt, lang=lang)
                    break  # Exit loop after successful command
                else:
                    retry_count += 1
                    if retry_count < max_retries:
                        speak("Let me try again...")
                    else:
                        speak("Unable to recognize your speech. Please try again.")
                        break
            
            self.status = "Tap the orb to speak"
            self.is_listening = False
            
        except Exception as e:
            print(f"Voice flow error: {e}")
            import traceback
            traceback.print_exc()
            speak("Something went wrong.")
            self.status = "Tap the orb to speak"
            self.is_listening = False


# ---------- MAIN ----------
if __name__ == "__main__":
    app = QApplication(sys.argv)
    gui = OrbGUI()
    gui.show()
    speak("Hello, I'm E.D.I. Tap the orb to speak.")
    sys.exit(app.exec())
