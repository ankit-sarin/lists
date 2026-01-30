# Lists

Family list app inspired by Cozi.

## Tech Stack

- Python
- Gradio
- SQLite with aiosqlite (async)
- Ollama (qwen2.5:7b-instruct)
- OpenAI Whisper (base.en) for voice transcription

## Configuration

- Port: 7862
- Database: lists.db
- Service: lists.service (systemd)

## Views

1. **All Lists** - Filter tabs (Shopping/To Do/Chores), list cards with previews, create/delete lists
2. **Single List** - Add items, checkboxes with strikethrough, delete items, back navigation
3. **Bruno** - Voice recording with Whisper transcription, natural language input, Ollama parsing, bulk add to selected list

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

## Future Plans

- **VIEW 4: Recipe Scanner** - Use vision model (qwen2.5-vl) to extract ingredients from recipe images/screenshots
