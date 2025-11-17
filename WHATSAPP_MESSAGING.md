# WhatsApp Messaging Feature

## Overview
The E.D.I voice assistant now supports sending WhatsApp messages to your saved contacts using voice commands.

## Setup

### 1. Add Contacts
Edit `contacts.json` and add your contacts with their phone numbers:

```json
{
  "john": "919876543210",
  "mom": "919876543211",
  "office": "911122223333",
  "friend": "918765432109"
}
```

**Phone Number Format:**
- Include country code (e.g., 91 for India)
- Remove spaces, hyphens, or + symbols
- Example: `919876543210` (not +91 9876 543210)

### 2. Voice Command
Simply say: **"Send WhatsApp message"** or any keyword from the `send_whatsapp` intent

## How It Works

1. **Command Recognition:** You say "Send WhatsApp message"
2. **Contact Input:** E.D.I asks you to say the contact name
3. **Message Input:** E.D.I asks you to say the message
4. **Message Sending:** Opens WhatsApp Web with pre-filled message

## Supported Keywords (Multilingual)

**English:**
- "send whatsapp message"
- "whatsapp message"
- "send message on whatsapp"

**Hindi:**
- "व्हाट्सएप संदेश भेजें"
- "whatsapp message"

**Marathi:**
- "व्हाट्सअँप संदेश पाठवा"

**Gujarati:**
- "વોટ્સએપ સંદેશ"

**Punjabi:**
- "ਵਾਟਸ ਐਪ ਸੁਨੇਹਾ"

## Example Usage

```
You: "Send WhatsApp message"
E.D.I: "Please say the contact name"
You: "John"
E.D.I: "Sending message to John. Please say your message."
You: "Hello John, how are you?"
E.D.I: "Opening WhatsApp to send message to John"
```

## Technical Details

- **Backend:** WhatsApp Web API (opens in default browser)
- **Contact Lookup:** Case-insensitive name matching from `contacts.json`
- **Message Encoding:** URL-encoded for safe transmission
- **Default Country Code:** 91 (India) - can be modified in `send_whatsapp_message()` function

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "Contact not found" | Ensure contact name in `contacts.json` matches exactly (case-insensitive) |
| WhatsApp Web doesn't open | Ensure you have internet connection and WhatsApp Web is accessible |
| Message not sending | After WhatsApp Web opens, manually confirm sending (some messages need user confirmation) |
| Contact name not recognized | Speak clearly and slowly; ensure the speech recognition captures the name correctly |

## Security Notes

- Phone numbers are stored locally in `contacts.json` (not sent to cloud)
- Messages are sent via WhatsApp's official web interface
- Never share `contacts.json` with untrusted parties
- Add `.gitignore` entry if file contains sensitive personal data

## Future Enhancements

- [ ] Desktop WhatsApp app integration (direct message sending without web)
- [ ] Contact import from phone contacts
- [ ] Message templates (greetings, common messages)
- [ ] Group messaging support
- [ ] Message scheduling
