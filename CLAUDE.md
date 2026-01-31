# Lists

Family list app inspired by Cozi.

## Tech Stack

- Python
- Gradio
- SQLite with aiosqlite (async)
- Ollama (qwen2.5:7b-instruct for text, qwen3-vl:8b for vision)
- OpenAI Whisper (base.en) for voice transcription

## Configuration

- Port: 7862
- Database: lists.db
- Service: lists.service (systemd)
- Ollama endpoint: localhost:11434

## Views

1. **All Lists** - Filter tabs (Shopping/To Do/Chores), list cards with previews, create/delete lists
2. **Single List** - Add items, checkboxes with strikethrough, delete items, back navigation
3. **Bruno** - Voice recording with Whisper transcription, natural language input, Ollama parsing, checkbox preview, then select list (existing or new) to add items
4. **Smart Scan** - Upload images (recipes, handwritten notes, whiteboards, screenshots), vision model extraction with qwen3-vl:8b, checkbox preview, add to existing or new list (filtered by type)

## Database Schema

```sql
lists (id, name, list_type, created_at)
items (id, list_id, name, purchased, added_at)
```

## Running

```bash
# Development
python app.py

# Production (systemd)
sudo systemctl start lists
```

