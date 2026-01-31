# Lists

A Cozi-inspired family list app with AI-powered item parsing, voice input, and image scanning.

## Features

### Four Views

**1. All Lists View**
- Filter by type: Shopping, To Do, Chores
- List cards with item previews
- Create and delete lists

**2. Single List View**
- Add items with text input
- Check off items (strikethrough when complete)
- Delete individual items
- Completed items grouped at bottom

**3. Bruno (AI Assistant)**
- Voice recording with Whisper transcription
- Paste messy natural language text
- AI extracts individual items using Ollama (qwen2.5:7b-instruct)
- Checkbox preview to select items
- Add to existing list or create a new one

**4. Smart Scan (Vision AI)**
- Upload photos of recipes, handwritten notes, whiteboards, or screenshots
- Select item type to extract (Shopping, To Do, or Chores)
- Vision AI extracts items using Ollama (qwen3-vl:8b)
- Checkbox preview to select items
- Add to existing list or create a new one

## Tech Stack

- **Backend**: Python with Gradio
- **Database**: SQLite with aiosqlite (async)
- **AI (Text)**: Ollama with qwen2.5:7b-instruct
- **AI (Vision)**: Ollama with qwen3-vl:8b
- **Voice**: OpenAI Whisper (base.en)
- **Styling**: Custom CSS, mobile-friendly

## Setup

1. Create virtual environment:
```bash
python -m venv venv
source venv/bin/activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Install Ollama models for AI features:
```bash
# Install Ollama from https://ollama.ai
ollama pull qwen2.5:7b-instruct  # For Bruno text parsing
ollama pull qwen3-vl:8b          # For Smart Scan image extraction
```

4. Run the app:
```bash
python app.py
```

5. Open http://localhost:7862

## Production Deployment

A systemd service file is included for 24/7 operation:

```bash
sudo cp lists.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable lists
sudo systemctl start lists
```

## Screenshots

The app features a teal/cyan color scheme (#0097A7) with:
- Clean card-based list display
- Custom checkbox styling
- Mobile-responsive design (max-width 500px)

## License

MIT
