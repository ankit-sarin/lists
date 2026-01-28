# Smart Grocery

A Cozi-inspired grocery and task list app with AI-powered item parsing.

## Features

### Three Views

**1. All Lists View**
- Filter by type: Shopping, To Do, Chores
- List cards with item previews
- Create and delete lists

**2. Single List View**
- Add items with text input
- Check off items (strikethrough when complete)
- Delete individual items
- Completed items grouped at bottom

**3. AI Helper**
- Paste messy natural language text
- AI extracts individual items using Ollama
- Select which list to add parsed items to

## Tech Stack

- **Backend**: Python with Gradio
- **Database**: SQLite with aiosqlite (async)
- **AI**: Ollama with qwen2.5:7b-instruct
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

3. (Optional) Install Ollama for AI features:
```bash
# Install Ollama from https://ollama.ai
ollama pull qwen2.5:7b-instruct
```

4. Run the app:
```bash
python app.py
```

5. Open http://localhost:7862

## Screenshots

The app features a teal/cyan color scheme (#0097A7) with:
- Clean card-based list display
- Custom checkbox styling
- Mobile-responsive design (max-width 500px)

## License

MIT
