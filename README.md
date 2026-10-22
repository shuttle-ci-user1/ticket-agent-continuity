# 🎫 Ticket Agent Continuity

Prevents the daily "wrong re-assignment" problem:

> Yesterday Ali was working on a ticket. Today it's still open. You accidentally assign it to Ahmad. Ahmad starts from zero.

**This app fixes that.** Upload today's Freshdesk export and instantly see:

| What you see | What it means |
|---|---|
| ⚠️ Re-opened tickets | Still open + had a previous agent → **assign the same person** |
| 📋 Same agent, still open | No change needed — agent already has it |
| 🆕 New open tickets | Brand new, no history — normal assignment |
| ✅ Newly closed | Since your last upload |

## How it works

```
Upload today's .xls
        ↓
App compares every ticket against stored history (history.json)
        ↓
Re-opened? → Shows previous agent's name → you reassign the same person
New?       → Shows as new ticket
Closed?    → Marks as completed
        ↓
History updated for tomorrow's comparison
```

## Quick start (local)

```bash
git clone https://github.com/YOUR_USERNAME/ticket-agent-continuity.git
cd ticket-agent-continuity
pip install -r requirements.txt
streamlit run app.py
```

## Deploy to Streamlit Cloud (free)

1. Fork or push this repo to your GitHub
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. Sign in with GitHub → **New app** → select this repo → main branch → `app.py`
4. Click **Deploy**

You get a permanent URL like: `https://ticket-agent-continuity.streamlit.app`

## Input format

Any Freshdesk export in SpreadsheetML `.xls` format with these columns:
- `Ticket ID`
- `Status`
- `Agent`
- `Subject`
- `Created time`
- `Last update time`
- `Group`

Other columns are ignored gracefully.

## License

MIT
