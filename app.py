import gradio as gr
import aiosqlite
import asyncio
import httpx
import json
import whisper

# Load Whisper model for speech recognition
print("Loading Whisper model...")
whisper_model = whisper.load_model("base.en", device="cpu")
print("Whisper model loaded!")

DATABASE = "lists.db"

# ============== Database Setup ==============
async def init_db():
    async with aiosqlite.connect(DATABASE) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS lists (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                list_type TEXT DEFAULT 'Shopping',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                list_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                purchased INTEGER DEFAULT 0,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (list_id) REFERENCES lists(id) ON DELETE CASCADE
            )
        """)
        await db.commit()

        # Sample data if empty
        cursor = await db.execute("SELECT COUNT(*) FROM lists")
        count = (await cursor.fetchone())[0]
        if count == 0:
            sample_lists = [
                ("Groceries", "Shopping"),
                ("Trader Joe's", "Shopping"),
                ("Costco Run", "Shopping"),
                ("Weekly Tasks", "To Do"),
                ("Work Projects", "To Do"),
                ("House Chores", "Chores"),
            ]
            for name, list_type in sample_lists:
                await db.execute("INSERT INTO lists (name, list_type) VALUES (?, ?)", (name, list_type))
            await db.commit()

            sample_items = [
                (1, "Milk"), (1, "Bread"), (1, "Eggs"), (1, "Butter"), (1, "Apples"), (1, "Bananas"), (1, "Chicken"),
                (2, "Dark Chocolate"), (2, "Orange Chicken"), (2, "Cookie Butter"), (2, "Everything Bagel Seasoning"),
                (3, "Paper Towels"), (3, "Toilet Paper"), (3, "Olive Oil"), (3, "Almonds"),
                (4, "Pay bills"), (4, "Schedule dentist"), (4, "Call mom"),
                (5, "Finish report"), (5, "Email client"), (5, "Review PR"),
                (6, "Vacuum living room"), (6, "Do laundry"), (6, "Clean bathroom"),
            ]
            for list_id, name in sample_items:
                await db.execute("INSERT INTO items (list_id, name) VALUES (?, ?)", (list_id, name))
            await db.commit()

# ============== Database Operations ==============
async def get_lists(list_type=None):
    async with aiosqlite.connect(DATABASE) as db:
        db.row_factory = aiosqlite.Row
        if list_type and list_type != "All":
            cursor = await db.execute("SELECT * FROM lists WHERE list_type = ? ORDER BY created_at DESC", (list_type,))
        else:
            cursor = await db.execute("SELECT * FROM lists ORDER BY created_at DESC")
        return await cursor.fetchall()

async def get_list_by_id(list_id):
    async with aiosqlite.connect(DATABASE) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM lists WHERE id = ?", (list_id,))
        return await cursor.fetchone()

async def get_list_items(list_id):
    async with aiosqlite.connect(DATABASE) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM items WHERE list_id = ? ORDER BY purchased ASC, added_at DESC", (list_id,))
        return await cursor.fetchall()

async def get_items_preview(list_id):
    async with aiosqlite.connect(DATABASE) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM items WHERE list_id = ? AND purchased = 0 ORDER BY added_at DESC", (list_id,))
        return await cursor.fetchall()

async def create_list(name, list_type):
    async with aiosqlite.connect(DATABASE) as db:
        cursor = await db.execute("INSERT INTO lists (name, list_type) VALUES (?, ?)", (name, list_type))
        await db.commit()
        return cursor.lastrowid

async def delete_list(list_id):
    async with aiosqlite.connect(DATABASE) as db:
        await db.execute("DELETE FROM items WHERE list_id = ?", (list_id,))
        await db.execute("DELETE FROM lists WHERE id = ?", (list_id,))
        await db.commit()

async def add_item(list_id, name):
    async with aiosqlite.connect(DATABASE) as db:
        await db.execute("INSERT INTO items (list_id, name) VALUES (?, ?)", (list_id, name))
        await db.commit()

async def add_items_bulk(list_id, names):
    async with aiosqlite.connect(DATABASE) as db:
        for name in names:
            await db.execute("INSERT INTO items (list_id, name) VALUES (?, ?)", (list_id, name.strip()))
        await db.commit()

async def toggle_item(item_id):
    async with aiosqlite.connect(DATABASE) as db:
        await db.execute("UPDATE items SET purchased = NOT purchased WHERE id = ?", (item_id,))
        await db.commit()

async def delete_item(item_id):
    async with aiosqlite.connect(DATABASE) as db:
        await db.execute("DELETE FROM items WHERE id = ?", (item_id,))
        await db.commit()

# ============== Ollama AI Integration ==============
async def parse_items_with_ai(text):
    """Use Ollama to parse natural language into individual items."""
    if not text.strip():
        return []

    prompt = f"""Extract individual grocery/task items from this text. Return ONLY a JSON array of strings, nothing else.

Text: "{text}"

Rules:
- Extract each distinct item as a separate string
- Clean up the text (proper capitalization, remove filler words)
- If quantities are mentioned, include them with the item
- Return valid JSON array only, no explanation

Example input: "need milk eggs and oh yeah we're out of bread also bananas"
Example output: ["Milk", "Eggs", "Bread", "Bananas"]

Your response (JSON array only):"""

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "http://localhost:11434/api/generate",
                json={"model": "qwen2.5:7b-instruct", "prompt": prompt, "stream": False}
            )
            if response.status_code == 200:
                result = response.json().get("response", "").strip()
                # Try to extract JSON array from response
                start = result.find("[")
                end = result.rfind("]") + 1
                if start != -1 and end > start:
                    json_str = result[start:end]
                    items = json.loads(json_str)
                    return [str(item).strip() for item in items if item]
    except Exception as e:
        print(f"Ollama error: {e}")

    # Fallback: simple split on common delimiters
    fallback_items = []
    for delimiter in [",", " and ", "\n"]:
        if delimiter in text:
            parts = text.split(delimiter)
            fallback_items = [p.strip() for p in parts if p.strip()]
            break
    if not fallback_items:
        fallback_items = [text.strip()]
    return fallback_items

# ============== Audio Transcription ==============
def transcribe_audio(audio_path):
    """Transcribe audio file using Whisper model."""
    if audio_path is None:
        return "", '<div class="status-msg status-error">No audio recorded.</div>'

    print(f"Transcribing file: {audio_path}")
    try:
        result = whisper_model.transcribe(audio_path)
        text = result["text"].strip()
        print(f"Transcription result: {text}")

        if text:
            return text, '<div class="status-msg status-success">✓ Transcription complete!</div>'
        else:
            return "", '<div class="status-msg status-error">No speech detected.</div>'
    except Exception as e:
        print(f"Error: {e}")
        return "", f'<div class="status-msg status-error">Error: {str(e)}</div>'

# ============== HTML Generators ==============
def generate_all_lists_html(lists, items_dict):
    if not lists:
        return """
        <div style="text-align: center; padding: 60px 20px; color: #666;">
            <div style="font-size: 48px; margin-bottom: 16px;">📝</div>
            <p style="font-size: 18px; margin: 0;">No lists yet!</p>
            <p style="font-size: 14px; color: #999;">Create your first list below.</p>
        </div>
        """

    html = '<div style="display: flex; flex-direction: column; gap: 12px; padding: 16px;">'

    for lst in lists:
        list_id = lst['id']
        list_name = lst['name']
        list_type = lst['list_type']
        items = items_dict.get(list_id, [])

        type_icons = {"Shopping": "🛒", "To Do": "✅", "Chores": "🏠"}
        icon = type_icons.get(list_type, "📋")

        preview_html = ""
        unpurchased = [i for i in items if not i['purchased']]

        for item in unpurchased[:4]:
            preview_html += f'''<div style="display: flex; align-items: center; padding: 3px 0; color: #555; font-size: 14px;">
                <span style="color: #0097A7; margin-right: 8px; font-size: 8px;">●</span>
                <span>{item['name']}</span>
            </div>'''

        remaining = len(unpurchased) - 4
        if remaining > 0:
            preview_html += f'<div style="color: #0097A7; font-size: 13px; padding-top: 4px;">+ {remaining} more items</div>'

        if not unpurchased:
            if items:
                preview_html = '<div style="color: #4CAF50; font-size: 14px; padding: 4px 0;">✓ All items completed!</div>'
            else:
                preview_html = '<div style="color: #999; font-size: 14px; font-style: italic; padding: 4px 0;">No items yet</div>'

        html += f'''
        <div style="background: white; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.08); overflow: hidden; border: 1px solid #e8e8e8;">
            <div style="display: flex; align-items: center; justify-content: space-between; padding: 14px 16px; border-bottom: 1px solid #f0f0f0;">
                <div style="display: flex; align-items: center; gap: 10px; cursor: pointer; flex: 1;" onclick="selectList({list_id})">
                    <span style="font-size: 20px;">{icon}</span>
                    <span style="color: #0097A7; font-size: 17px; font-weight: 600;">{list_name}</span>
                </div>
                <button onclick="deleteList({list_id})" style="background: none; border: none; color: #999; font-size: 20px; cursor: pointer; padding: 4px 8px; border-radius: 4px;" onmouseover="this.style.color='#f44336'" onmouseout="this.style.color='#999'">×</button>
            </div>
            <div style="padding: 12px 16px; cursor: pointer;" onclick="selectList({list_id})">
                {preview_html}
            </div>
        </div>'''

    html += '</div>'
    return html

def generate_single_list_html(list_info, items):
    if not list_info:
        return ""

    items_html = ""
    unpurchased = [i for i in items if not i['purchased']]
    purchased = [i for i in items if i['purchased']]

    for item in unpurchased:
        items_html += f'''
        <div style="display: flex; align-items: center; padding: 14px 16px; background: white; border-bottom: 1px solid #f0f0f0;">
            <input type="checkbox" id="item-{item['id']}" onchange="toggleItem({item['id']})"
                style="width: 22px; height: 22px; margin-right: 14px; accent-color: #0097A7; cursor: pointer; flex-shrink: 0;">
            <label for="item-{item['id']}" style="flex: 1; color: #333; font-size: 16px; cursor: pointer;">{item['name']}</label>
            <button onclick="deleteItem({item['id']})" style="background: none; border: none; color: #ccc; font-size: 18px; cursor: pointer; padding: 4px 8px;" onmouseover="this.style.color='#f44336'" onmouseout="this.style.color='#ccc'">×</button>
        </div>'''

    if purchased:
        items_html += f'''<div style="padding: 12px 16px; background: #f9f9f9; color: #999; font-size: 13px; font-weight: 500; text-transform: uppercase; letter-spacing: 0.5px;">
            Completed ({len(purchased)})
        </div>'''
        for item in purchased:
            items_html += f'''
            <div style="display: flex; align-items: center; padding: 14px 16px; background: #fafafa; border-bottom: 1px solid #f0f0f0;">
                <input type="checkbox" id="item-{item['id']}" checked onchange="toggleItem({item['id']})"
                    style="width: 22px; height: 22px; margin-right: 14px; accent-color: #0097A7; cursor: pointer; flex-shrink: 0;">
                <label for="item-{item['id']}" style="flex: 1; color: #999; font-size: 16px; text-decoration: line-through; cursor: pointer;">{item['name']}</label>
                <button onclick="deleteItem({item['id']})" style="background: none; border: none; color: #ccc; font-size: 18px; cursor: pointer; padding: 4px 8px;" onmouseover="this.style.color='#f44336'" onmouseout="this.style.color='#ccc'">×</button>
            </div>'''

    if not items:
        items_html = '''
        <div style="text-align: center; padding: 60px 20px; color: #999;">
            <div style="font-size: 48px; margin-bottom: 16px;">📝</div>
            <p style="font-size: 16px; margin: 0;">This list is empty</p>
            <p style="font-size: 14px;">Add your first item above!</p>
        </div>'''

    return f'''<div style="background: white; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.08); overflow: hidden;">{items_html}</div>'''

def generate_parsed_items_html(items):
    if not items:
        return '<div style="color: #999; padding: 20px; text-align: center;">No items parsed yet</div>'

    html = '<div style="background: white; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.08); overflow: hidden;">'
    for i, item in enumerate(items):
        html += f'''
        <div style="display: flex; align-items: center; padding: 14px 16px; border-bottom: 1px solid #f0f0f0;">
            <input type="checkbox" id="parsed-{i}" checked class="parsed-item-cb" data-item="{item}"
                style="width: 22px; height: 22px; margin-right: 14px; accent-color: #0097A7; cursor: pointer;">
            <label for="parsed-{i}" style="flex: 1; color: #333; font-size: 16px; cursor: pointer;">{item}</label>
        </div>'''
    html += '</div>'
    return html

# ============== CSS ==============
custom_css = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

* { font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important; }

.gradio-container {
    max-width: 500px !important;
    margin: 0 auto !important;
    padding: 0 !important;
    background: #f5f5f5 !important;
    min-height: 100vh !important;
}

.main-header {
    background: linear-gradient(135deg, #0097A7 0%, #00838F 100%) !important;
    padding: 16px 20px !important;
    color: white !important;
    font-size: 22px !important;
    font-weight: 700 !important;
    box-shadow: 0 2px 8px rgba(0,0,0,0.15) !important;
    display: flex !important;
    align-items: center !important;
    gap: 12px !important;
}

.back-btn {
    background: rgba(255,255,255,0.2) !important;
    border: none !important;
    color: white !important;
    padding: 6px 12px !important;
    border-radius: 6px !important;
    cursor: pointer !important;
    font-size: 14px !important;
}

.back-btn:hover { background: rgba(255,255,255,0.3) !important; }

.nav-tabs {
    display: flex !important;
    background: white !important;
    border-bottom: 2px solid #e0e0e0 !important;
    position: sticky !important;
    top: 0 !important;
    z-index: 50 !important;
}

.nav-tab {
    flex: 1 !important;
    padding: 14px !important;
    text-align: center !important;
    cursor: pointer !important;
    font-weight: 600 !important;
    color: #666 !important;
    border-bottom: 3px solid transparent !important;
    transition: all 0.2s !important;
}

.nav-tab:hover { color: #0097A7 !important; }
.nav-tab.active { color: #0097A7 !important; border-bottom-color: #0097A7 !important; }

.filter-pills {
    display: flex !important;
    gap: 8px !important;
    padding: 12px 16px !important;
    background: white !important;
    overflow-x: auto !important;
}

.filter-pill {
    padding: 8px 16px !important;
    border-radius: 20px !important;
    border: 2px solid #0097A7 !important;
    background: white !important;
    color: #0097A7 !important;
    font-size: 14px !important;
    font-weight: 500 !important;
    cursor: pointer !important;
    white-space: nowrap !important;
}

.filter-pill:hover, .filter-pill.active { background: #0097A7 !important; color: white !important; }

.action-btn {
    background: linear-gradient(135deg, #0097A7 0%, #00838F 100%) !important;
    color: white !important;
    border: none !important;
    border-radius: 10px !important;
    padding: 14px 24px !important;
    font-size: 15px !important;
    font-weight: 600 !important;
    cursor: pointer !important;
    width: 100% !important;
    transition: transform 0.2s, box-shadow 0.2s !important;
}

.action-btn:hover {
    transform: translateY(-1px) !important;
    box-shadow: 0 4px 12px rgba(0, 151, 167, 0.3) !important;
}

.secondary-btn {
    background: white !important;
    color: #0097A7 !important;
    border: 2px solid #0097A7 !important;
}

.secondary-btn:hover {
    background: #e0f7fa !important;
}

input[type="text"], textarea {
    border: 2px solid #e0e0e0 !important;
    border-radius: 10px !important;
    padding: 12px 14px !important;
    font-size: 15px !important;
}

input[type="text"]:focus, textarea:focus {
    border-color: #0097A7 !important;
    outline: none !important;
}

footer { display: none !important; }

@media (max-width: 768px) {
    .gradio-container { max-width: 100% !important; }
}

.hidden-trigger {
    position: absolute !important;
    left: -9999px !important;
    width: 1px !important;
    height: 1px !important;
    overflow: hidden !important;
}

input[type="checkbox"] {
    -webkit-appearance: none;
    appearance: none;
    width: 22px;
    height: 22px;
    border: 2px solid #ccc;
    border-radius: 6px;
    cursor: pointer;
    position: relative;
}

input[type="checkbox"]:checked {
    background: #0097A7;
    border-color: #0097A7;
}

input[type="checkbox"]:checked::after {
    content: '✓';
    position: absolute;
    color: white;
    font-size: 14px;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
}

.ai-input-area {
    background: white !important;
    border-radius: 12px !important;
    padding: 16px !important;
    margin: 16px !important;
    box-shadow: 0 2px 8px rgba(0,0,0,0.08) !important;
}

.status-msg {
    padding: 12px 16px;
    border-radius: 8px;
    margin: 8px 0;
    font-size: 14px;
}

.status-success { background: #e8f5e9; color: #2e7d32; }
.status-error { background: #ffebee; color: #c62828; }
.status-info { background: #e3f2fd; color: #1565c0; }
"""

# ============== Event Handlers ==============
async def load_all_lists(filter_type):
    lists = await get_lists(filter_type if filter_type != "All" else None)
    items_dict = {}
    for lst in lists:
        items_dict[lst['id']] = await get_items_preview(lst['id'])
    return generate_all_lists_html(lists, items_dict)

async def get_list_choices():
    lists = await get_lists()
    return [(f"{lst['name']} ({lst['list_type']})", lst['id']) for lst in lists]

async def handle_select_list(list_id):
    if not list_id:
        return "", gr.update(visible=True), gr.update(visible=False), None, "Lists"

    list_info = await get_list_by_id(int(list_id))
    items = await get_list_items(int(list_id))
    return (
        generate_single_list_html(list_info, items),
        gr.update(visible=False),
        gr.update(visible=True),
        int(list_id),
        list_info['name']
    )

async def handle_back_to_lists(filter_type):
    html = await load_all_lists(filter_type)
    return html, gr.update(visible=True), gr.update(visible=False), None, "Lists"

async def handle_create_list(name, list_type, filter_type):
    if not name.strip():
        return await load_all_lists(filter_type), "", gr.update()
    await create_list(name.strip(), list_type)
    html = await load_all_lists(filter_type)
    choices = await get_list_choices()
    return html, "", gr.update(choices=choices)

async def handle_delete_list(list_id, filter_type):
    if list_id:
        await delete_list(int(list_id))
    html = await load_all_lists(filter_type)
    choices = await get_list_choices()
    return html, gr.update(choices=choices)

async def handle_add_item(list_id, item_name):
    if not list_id or not item_name.strip():
        return "", ""
    await add_item(int(list_id), item_name.strip())
    list_info = await get_list_by_id(int(list_id))
    items = await get_list_items(int(list_id))
    return generate_single_list_html(list_info, items), ""

async def handle_toggle_item(item_id, list_id):
    if item_id and list_id:
        await toggle_item(int(item_id))
        list_info = await get_list_by_id(int(list_id))
        items = await get_list_items(int(list_id))
        return generate_single_list_html(list_info, items)
    return ""

async def handle_delete_item(item_id, list_id):
    if item_id and list_id:
        await delete_item(int(item_id))
        list_info = await get_list_by_id(int(list_id))
        items = await get_list_items(int(list_id))
        return generate_single_list_html(list_info, items)
    return ""

async def handle_parse_items(text):
    if not text.strip():
        return "", [], '<div class="status-msg status-error">Please enter some text to parse</div>'
    items = await parse_items_with_ai(text)
    if items:
        html = generate_parsed_items_html(items)
        status = f'<div class="status-msg status-success">Found {len(items)} items! Select the ones you want to add.</div>'
        return html, items, status
    return "", [], '<div class="status-msg status-error">Could not parse any items</div>'

async def handle_add_parsed_items(list_id, parsed_items, selected_indices):
    if not list_id:
        return '<div class="status-msg status-error">Please select a list first</div>'
    if not parsed_items:
        return '<div class="status-msg status-error">No items to add</div>'

    # Add all parsed items (in real app, would filter by checkboxes)
    items_to_add = parsed_items if isinstance(parsed_items, list) else []
    if items_to_add:
        await add_items_bulk(int(list_id), items_to_add)
        return f'<div class="status-msg status-success">Added {len(items_to_add)} items to your list!</div>'
    return '<div class="status-msg status-error">No items selected</div>'

# ============== Build App ==============
# JavaScript for interactivity - Gradio 6.x compatible
app_js = """
function getGradioInput(elemId) {
    const container = document.getElementById(elemId);
    if (!container) {
        console.error('Container not found:', elemId);
        return null;
    }
    const input = container.querySelector('input') || container.querySelector('textarea');
    if (!input) {
        console.error('Input not found in container:', elemId);
    }
    return input;
}

function clickGradioButton(elemId) {
    const container = document.getElementById(elemId);
    if (!container) {
        console.error('Button container not found:', elemId);
        return;
    }

    // Debug: show what's in the container
    console.log('Container innerHTML for', elemId, ':', container.innerHTML.substring(0, 200));

    // Try multiple selectors - Gradio 6.x might use different structures
    let btn = container.querySelector('button');
    if (!btn) {
        btn = container.querySelector('[role="button"]');
    }
    if (!btn) {
        btn = container.querySelector('.gr-button');
    }

    if (btn) {
        console.log('Clicking button:', elemId);
        btn.click();
    } else {
        // Fallback: click the container itself and dispatch a click event
        console.log('No button found, clicking container directly:', elemId);
        container.click();
        container.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }));
    }
}

function setInputValue(elemId, value) {
    const input = getGradioInput(elemId);
    if (input) {
        console.log('Setting input value:', elemId, '=', value);

        // Simple direct assignment
        input.value = value;

        // Trigger Svelte/Gradio reactive update with InputEvent
        const inputEvent = new InputEvent('input', {
            bubbles: true,
            cancelable: true,
            inputType: 'insertText',
            data: value
        });
        input.dispatchEvent(inputEvent);

        // Also trigger change event
        input.dispatchEvent(new Event('change', { bubbles: true }));

        console.log('Input value after set:', input.value);
    }
}

function selectList(id) {
    console.log('selectList called with id:', id);
    setInputValue('selected-list-id', String(id));
    setTimeout(() => clickGradioButton('select-btn'), 200);
}

function toggleItem(id) {
    console.log('toggleItem called with id:', id);
    setInputValue('action-item-id', String(id));
    setTimeout(() => clickGradioButton('toggle-btn'), 200);
}

function deleteItem(id) {
    console.log('deleteItem called with id:', id);
    setInputValue('action-item-id', String(id));
    setTimeout(() => clickGradioButton('delete-btn'), 200);
}

function deleteList(id) {
    if (confirm('Delete this list and all its items?')) {
        console.log('deleteList confirmed with id:', id);
        setInputValue('delete-list-id', String(id));
        setTimeout(() => clickGradioButton('delete-list-btn'), 200);
    }
}

function goBack() {
    console.log('goBack called');
    clickGradioButton('back-btn');
}

function switchTab(tab) {
    console.log('switchTab called with tab:', tab);
    document.querySelectorAll('.nav-tab').forEach(t => t.classList.remove('active'));
    document.getElementById('nav-' + tab)?.classList.add('active');
    setInputValue('tab-switch-input', tab);
    setTimeout(() => clickGradioButton('tab-trigger'), 200);
}
"""

def create_app():
    with gr.Blocks(title="Lists") as app:
        # State
        current_list_id = gr.State(None)
        current_view = gr.State("lists")  # lists, single, ai
        parsed_items_state = gr.State([])

        # Header
        header_text = gr.State("Lists")

        def make_header(title, show_back=False):
            back_btn = '<button class="back-btn" onclick="goBack()">← Back</button>' if show_back else ''
            return f'<div class="main-header">{back_btn}<span>{title}</span></div>'

        header_html = gr.HTML(value=make_header("Lists"))

        # Navigation Tabs
        gr.HTML("""
        <div class="nav-tabs">
            <div class="nav-tab active" id="nav-lists" onclick="switchTab('lists')">📋 Lists</div>
            <div class="nav-tab" id="nav-ai" onclick="switchTab('ai')">🤖 Bruno</div>
        </div>
        """)

        # ========== VIEW 1: All Lists ==========
        with gr.Column(visible=True) as all_lists_view:
            filter_type = gr.Radio(
                choices=["All", "Shopping", "To Do", "Chores"],
                value="All",
                label="",
                container=False
            )
            all_lists_html = gr.HTML()

            gr.HTML('<div style="padding: 16px;"><div style="font-weight: 600; color: #333; margin-bottom: 8px;">Create New List</div></div>')
            with gr.Row():
                new_list_name = gr.Textbox(placeholder="List name...", label="", container=False, scale=2)
                new_list_type = gr.Dropdown(choices=["Shopping", "To Do", "Chores"], value="Shopping", label="", container=False, scale=1)
            create_list_btn = gr.Button("Create List", elem_classes=["action-btn"])

        # ========== VIEW 2: Single List ==========
        with gr.Column(visible=False) as single_list_view:
            with gr.Row():
                new_item_name = gr.Textbox(placeholder="+ Add new item...", label="", container=False, scale=4)
                add_item_btn = gr.Button("Add", variant="primary", scale=1)
            single_list_html = gr.HTML()
            back_btn = gr.Button("← Back to Lists", elem_classes=["action-btn", "secondary-btn"])

        # ========== VIEW 3: Bruno ==========
        with gr.Column(visible=False) as ai_helper_view:
            gr.HTML('''
            <div class="ai-input-area">
                <h3 style="color: #0097A7; margin: 0 0 8px 0;">🤖 Bruno</h3>
                <p style="color: #666; font-size: 14px; margin: 0;">
                    Type or paste your messy shopping list and let AI extract the items for you!
                </p>
            </div>
            ''')

            with gr.Row():
                audio_input = gr.Audio(
                    sources=["microphone"],
                    type="filepath",
                    label="🎤 Record your list"
                )
            transcribe_btn = gr.Button("🎤 Transcribe Recording", elem_classes=["action-btn", "secondary-btn"])
            transcribe_status = gr.HTML()

            ai_text_input = gr.Textbox(
                placeholder="e.g., need milk eggs and oh yeah we're out of bread also bananas for smoothies...",
                label="Your messy list",
                lines=4
            )
            parse_btn = gr.Button("🔍 Parse Items", elem_classes=["action-btn"])

            ai_status = gr.HTML()
            parsed_items_html = gr.HTML()

            ai_list_dropdown = gr.Dropdown(label="Add to list", choices=[], interactive=True)
            add_to_list_btn = gr.Button("Add Selected Items to List", elem_classes=["action-btn"])
            add_result = gr.HTML()

        # Hidden elements for JS interactions (use CSS hiding so they remain in DOM)
        # interactive=True is required for Gradio 6.x to accept programmatic value changes
        selected_list_id = gr.Textbox(elem_id="selected-list-id", elem_classes=["hidden-trigger"], interactive=True)
        action_item_id = gr.Textbox(elem_id="action-item-id", elem_classes=["hidden-trigger"], interactive=True)
        delete_list_id = gr.Textbox(elem_id="delete-list-id", elem_classes=["hidden-trigger"], interactive=True)
        tab_switch = gr.Textbox(elem_id="tab-switch-input", elem_classes=["hidden-trigger"], interactive=True)

        toggle_trigger = gr.Button("T", elem_id="toggle-btn", elem_classes=["hidden-trigger"])
        delete_trigger = gr.Button("D", elem_id="delete-btn", elem_classes=["hidden-trigger"])
        select_trigger = gr.Button("S", elem_id="select-btn", elem_classes=["hidden-trigger"])
        delete_list_trigger = gr.Button("X", elem_id="delete-list-btn", elem_classes=["hidden-trigger"])
        back_trigger = gr.Button("B", elem_id="back-btn", elem_classes=["hidden-trigger"])
        tab_trigger = gr.Button("A", elem_id="tab-trigger", elem_classes=["hidden-trigger"])


        # Tab switching handler
        def handle_tab_switch(tab, filter_type):
            if tab == "lists":
                return (
                    gr.update(visible=True),
                    gr.update(visible=False),
                    gr.update(visible=False),
                    make_header("Lists")
                )
            elif tab == "ai":
                return (
                    gr.update(visible=False),
                    gr.update(visible=False),
                    gr.update(visible=True),
                    make_header("Bruno")
                )
            return gr.update(), gr.update(), gr.update(), gr.update()

        tab_trigger.click(
            fn=handle_tab_switch,
            inputs=[tab_switch, filter_type],
            outputs=[all_lists_view, single_list_view, ai_helper_view, header_html]
        )

        # Event bindings
        filter_type.change(fn=load_all_lists, inputs=[filter_type], outputs=[all_lists_html])

        create_list_btn.click(
            fn=handle_create_list,
            inputs=[new_list_name, new_list_type, filter_type],
            outputs=[all_lists_html, new_list_name, ai_list_dropdown]
        )

        new_list_name.submit(
            fn=handle_create_list,
            inputs=[new_list_name, new_list_type, filter_type],
            outputs=[all_lists_html, new_list_name, ai_list_dropdown]
        )

        async def select_and_update_header(list_id):
            result = await handle_select_list(list_id)
            return result[0], result[1], result[2], result[3], make_header(result[4], show_back=True)

        select_trigger.click(
            fn=select_and_update_header,
            inputs=[selected_list_id],
            outputs=[single_list_html, all_lists_view, single_list_view, current_list_id, header_html]
        )

        async def delete_and_update(list_id, filter_type):
            result = await handle_delete_list(list_id, filter_type)
            return result

        delete_list_trigger.click(
            fn=delete_and_update,
            inputs=[delete_list_id, filter_type],
            outputs=[all_lists_html, ai_list_dropdown]
        )

        async def back_and_update_header(filter_type):
            result = await handle_back_to_lists(filter_type)
            return result[0], result[1], result[2], result[3], make_header("Lists")

        back_btn.click(
            fn=back_and_update_header,
            inputs=[filter_type],
            outputs=[all_lists_html, all_lists_view, single_list_view, current_list_id, header_html]
        )

        back_trigger.click(
            fn=back_and_update_header,
            inputs=[filter_type],
            outputs=[all_lists_html, all_lists_view, single_list_view, current_list_id, header_html]
        )

        add_item_btn.click(fn=handle_add_item, inputs=[current_list_id, new_item_name], outputs=[single_list_html, new_item_name])
        new_item_name.submit(fn=handle_add_item, inputs=[current_list_id, new_item_name], outputs=[single_list_html, new_item_name])

        toggle_trigger.click(fn=handle_toggle_item, inputs=[action_item_id, current_list_id], outputs=[single_list_html])
        delete_trigger.click(fn=handle_delete_item, inputs=[action_item_id, current_list_id], outputs=[single_list_html])

        # Bruno handlers
        # Audio transcription - button click to transcribe
        transcribe_btn.click(
            fn=transcribe_audio,
            inputs=[audio_input],
            outputs=[ai_text_input, transcribe_status]
        )

        async def parse_and_store(text):
            html, items, status = await handle_parse_items(text)
            return html, items, status

        parse_btn.click(
            fn=parse_and_store,
            inputs=[ai_text_input],
            outputs=[parsed_items_html, parsed_items_state, ai_status]
        )

        add_to_list_btn.click(
            fn=handle_add_parsed_items,
            inputs=[ai_list_dropdown, parsed_items_state, gr.State([])],
            outputs=[add_result]
        )

        # Initial load
        async def init_load(filter_type):
            html = await load_all_lists(filter_type)
            choices = await get_list_choices()
            return html, gr.update(choices=choices)

        app.load(fn=init_load, inputs=[filter_type], outputs=[all_lists_html, ai_list_dropdown])

    return app

# ============== Main ==============
if __name__ == "__main__":
    asyncio.run(init_db())
    app = create_app()
    app.launch(server_port=7862, server_name="0.0.0.0", share=False, show_error=True, css=custom_css, js=app_js)
