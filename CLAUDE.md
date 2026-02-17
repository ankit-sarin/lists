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
- Brand CSS: gradio-theme.css (Digital Surgeon theme, loaded and appended to custom_css in gr.Blocks)

## Views

1. **All Lists** - Filter tabs (Shopping/To Do/Chores), list cards with previews, create/delete lists
2. **Single List** - Add items, checkboxes with strikethrough, delete items, "Delete Checked" bulk action (appears when checked items exist), back navigation
3. **Bruno** - Voice recording with Whisper transcription, natural language input, Ollama parsing, checkbox preview, then select list (existing or new) to add items
4. **Smart Scan** - Upload images (recipes, handwritten notes, whiteboards, screenshots), vision model extraction with qwen3-vl:8b, checkbox preview, add to existing or new list (filtered by type)

## Database Schema

```sql
lists (id, name, list_type, created_at)
items (id, list_id, name, purchased, added_at)
```

- `purchased` column (INTEGER 0/1) is the "checked" state in the UI
- Toggle and delete operations use the item's database `id`, never list index position

## Architecture Notes

### JS ↔ Python Bridge (Gradio 6)

All interactive actions in rendered HTML (check, delete, select list) use a hidden-trigger pattern:

1. HTML `onclick` calls a JS function (e.g., `toggleItem(id)`)
2. JS sets a hidden `gr.Textbox` value via `setInputValue()` (dispatches InputEvent for Svelte reactivity)
3. JS clicks a hidden `gr.Button` via `clickGradioButton()` after 200ms delay
4. Gradio fires the Python handler bound to that button

**Gradio 6 critical detail:** `elem_id` is placed directly on the `<button>` element (no wrapper div). `clickGradioButton()` uses `btn || container` to handle both Gradio 5 (wrapper div) and Gradio 6 (direct element) structures. Must fire `.click()` exactly once — double-firing causes toggles to cancel out (0→1→0).

### Checkbox Rendering

Checkboxes are rendered as `<button>` elements with inline styles (not `<input type="checkbox">`). This prevents Gradio/browser from carrying stale checked state by index position after deletes. Visual state is a pure function of the DB `purchased` field.

## Running

```bash
# Development
python app.py

# Production (systemd)
sudo systemctl start lists
```

