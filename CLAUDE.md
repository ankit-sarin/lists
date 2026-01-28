# Smart Grocery

Family grocery list app inspired by Cozi.

## Tech Stack

- Python
- Gradio
- SQLite with aiosqlite (async)
- Ollama (qwen2.5:7b-instruct)

## Configuration

- Port: 7862
- Database: grocery.db

## Views

1. **All Lists** - Filter tabs (Shopping/To Do/Chores), list cards with previews, create/delete lists
2. **Single List** - Add items, checkboxes with strikethrough, delete items, back navigation
3. **AI Helper** - Natural language input, Ollama parsing, bulk add to selected list

## Database Schema

```sql
lists (id, name, list_type, created_at)
items (id, list_id, name, purchased, added_at)
```

## Future Plans

- **VIEW 4: Recipe Scanner** - Use vision model (qwen2.5-vl) to extract ingredients from recipe images/screenshots
