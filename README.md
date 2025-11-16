# 🎤 E.D.I - Smart Voice Assistant

A production-ready multilingual voice assistant powered by **Groq AI** with real-time speech recognition, intelligent command processing, and an elegant PyQt6 GUI.

## ✨ Features

### 🎯 Core Capabilities
- **Voice Recognition**: Real-time speech-to-text using Google Web Speech API
- **Multilingual Support**: Automatic language detection (English, Hindi, Marathi, Gujarati, Punjabi)
- **AI-Powered Responses**: Groq LLM integration for intelligent Q&A
- **OS Commands**: System control (shutdown, restart, sleep, lock, sign-out)
- **Application Launcher**: Quick access to YouTube, Google, Chrome, Calculator, Notepad
- **Web Search**: Integrated Wikipedia and Google Search
- **Beautiful GUI**: Frameless animated orb interface with PyQt6

### 🎨 User Interface
- Animated blue radial gradient orb
- Real-time status feedback
- Always-on-top window
- Click-to-speak interaction
- Smooth pulse animations during listening

## 📋 Prerequisites

- **Python**: 3.10 or higher
- **Windows**: 10 or later (for OS command integration)
- **Microphone**: Required for speech input
- **Groq API Key**: [Get it free here](https://console.groq.com)

## 🚀 Installation

### 1. Clone the Repository
```bash
cd c:\Users\ASUS\Desktop\desktop-ai-agent-vynce
```

### 2. Create Virtual Environment
```bash
python -m venv venv
venv\Scripts\activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure API Key
Edit `Vynce/app.py` line 20 and replace the GROQ_API_KEY:
```python
GROQ_API_KEY = "your-api-key-here"
```

## 🎮 Usage

### Run the Assistant
```bash
python Vynce/app.py
```

### Voice Commands

#### Information Queries
- "Tell me about Python"
- "What is machine learning?"
- "Who is Elon Musk?"

#### Application Control
- "Open YouTube"
- "Launch Chrome"
- "Open calculator"

#### OS Commands
- "Shutdown"
- "Restart"
- "Sleep mode"
- "Lock screen"

#### Multilingual (Hindi/Marathi)
- "YouTube kholo" (Open YouTube)
- "band kar" (Shutdown)

## 📁 Project Structure

```
desktop-ai-agent-vynce/
├── Vynce/
│   ├── __init__.py
│   ├── app.py                 # Main application entry point
│   ├── config/
│   │   ├── settings.json
│   │   └── .env.example
│   ├── core/
│   │   ├── audio.py
│   │   ├── router.py
│   │   ├── stt_vosk.py
│   │   ├── tts_local.py
│   │   └── skills/
│   │       ├── file_ops.py
│   │       ├── messaging.py
│   │       ├── system_control.py
│   │       └── web_actions.py
│   ├── logs/
│   │   └── agent.log
│   └── ui/
│       ├── panel.py
│       └── finale.py          # Alternative UI version
├── venv/                       # Virtual environment
├── requirements.txt            # Python dependencies
├── qt.config                   # Qt platform configuration
└── README.md                   # This file
```

## 🔧 Configuration

### Qt Configuration
The `qt.config` file disables Windows DPI warnings:
```ini
[Platforms]
WindowsArguments = dpiawareness=0
```

### Environment Variables (Optional)
Create `Vynce/config/.env`:
```
GROQ_API_KEY=your-api-key-here
MICROPHONE_DEVICE=default
```

## 🎓 Architecture

### Speech Pipeline
1. **Listener**: Captures audio from microphone
2. **Recognition**: Google Web Speech API
3. **Detection**: Auto-detects language using langdetect
4. **Processing**: Routes to appropriate handler

### Intent Classification
- **OS Commands**: Regex pattern matching
- **App Open**: Synonym-based matching (multilingual)
- **Information Query**: Keyword detection + Groq AI
- **Unknown**: Fallback to AI knowledge retrieval

### Response Generation
- **TTS**: pyttsx3 (offline, female voice)
- **AI Responses**: Groq llama-3.3-70b-versatile
- **Wikipedia Fallback**: When API unavailable

## 🛠️ Dependencies

| Package | Purpose | Version |
|---------|---------|---------|
| PyQt6 | GUI Framework | >=6.4.0 |
| groq | AI LLM API | >=0.4.0 |
| SpeechRecognition | Voice-to-text | >=3.10.0 |
| pyttsx3 | Text-to-speech | >=2.90 |
| langdetect | Language detection | >=1.0.9 |
| requests | HTTP client | >=2.31.0 |
| wikipedia | Knowledge base | >=1.4.0 |
| pyjokes | Utility jokes | >=0.6.0 |
| Pillow | Image handling | >=9.0.0 |
| pyaudio | Audio I/O | >=0.2.11 |
| screen-brightness-control | Display control | >=0.19.0 |

## ⚙️ Troubleshooting

### "Microphone not found"
- Check system audio settings
- Ensure microphone is connected
- Test with Windows Sound Recorder

### "No module named 'PyQt6'"
```bash
pip install PyQt6 --upgrade
```

### API Key Issues
- Verify Groq API key is valid
- Check internet connection
- Fallback to Wikipedia enabled automatically

### Audio playback issues
- Install PortAudio: `pip install --upgrade pyaudio`
- Windows users: Ensure speakers are connected
- Check system volume levels

## 🔐 Security Notes

⚠️ **IMPORTANT**: The Groq API key is hardcoded for demo purposes.

For production deployment:
1. Remove API key from source code
2. Use environment variables:
   ```python
   import os
   GROQ_API_KEY = os.getenv("GROQ_API_KEY")
   ```
3. Use `.env` file with python-dotenv
4. Deploy with secrets management (AWS Secrets Manager, Azure Key Vault, etc.)

## 📦 Building Executable

### Using PyInstaller
```bash
pip install pyinstaller

pyinstaller --onefile \
  --windowed \
  --icon=icon.ico \
  --add-data "qt.config:." \
  Vynce/app.py
```

## 🤝 Contributing

To extend E.D.I:

1. Add new skills in `Vynce/core/skills/`
2. Register in `process_command()` function
3. Add language variants to `APP_SYNONYMS`
4. Test with multilingual inputs

## 📝 License

This project is open-source and available under the MIT License.

## 🚀 Deployment Checklist

- [ ] Python 3.10+ installed
- [ ] Virtual environment created and activated
- [ ] All dependencies installed (`pip install -r requirements.txt`)
- [ ] Groq API key configured in `Vynce/app.py`
- [ ] Microphone tested and working
- [ ] Qt configuration in place (`qt.config`)
- [ ] Application launches without errors
- [ ] Voice recognition working
- [ ] Commands executing properly
- [ ] GUI rendering smoothly

## 📞 Support

For issues or questions:
1. Check troubleshooting section above
2. Review requirements.txt for missing packages
3. Verify Groq API key validity
4. Check microphone/audio device settings

---

**Made with ❤️ for intelligent voice interaction**
