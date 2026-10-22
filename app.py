import streamlit as st
import xml.etree.ElementTree as ET
import json
import os
import io
from datetime import datetime
import pandas as pd

st.set_page_config(page_title="Ticket Agent Continuity", page_icon="🎫", layout="wide")

NS = {'ss': 'urn:schemas-microsoft-com:office:spreadsheet'}
SS = '{urn:schemas-microsoft-com:office:spreadsheet}'
HISTORY_FILE = 'history.json'
OPEN_STATUSES = {'Open', 'Pending', 'Waiting on Brands', 'Waiting on Vendor', 'Waiting on Customer'}

def parse_xls(uploaded_file):
    """Parse SpreadsheetML .xls (Freshdesk export) from uploaded bytes."""
    tree = ET.parse(uploaded_file)
    root = tree.getroot()
    rows = root.findall('.//ss:Worksheet/ss:Table/ss:Row', NS)

    def parse_row(row):
        cells = {}
        idx = 0
        for cell in row.findall('ss:Cell', NS):
            merge = cell.get(SS + 'Index')
            if merge:
                idx = int(merge)
            data = cell.find('ss:Data', NS)
            cells[idx] = str(data.text or '') if data is not None else ''
            idx += 1
        return cells

    header = parse_row(rows[0])
    name_to_idx = {v: k for k, v in header.items()}
    tickets = []
    for row in rows[1:]:
        cells = parse_row(row)
        t = {name: cells.get(name_to_idx[name], '') for name in name_to_idx}
        tickets.append(t)
    return tickets

def load_history():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_history(history):
    with open(HISTORY_FILE, 'w') as f:
        json.dump(history, f, indent=2, default=str)

# --- UI ---
st.title("🎫 Ticket Agent Continuity")
st.markdown("Upload today's Freshdesk export. We'll flag re-opened tickets and show you **who had them before** so you assign the same agent.")

uploaded = st.file_uploader("Drop your Freshdesk .xls export here", type=['xls', 'xlsx'])

if uploaded is not None:
    today = datetime.now().strftime('%Y-%m-%d')
    tickets = parse_xls(uploaded)
    history = load_history()

    # Build today's snapshot
    today_map = {}
    for t in tickets:
        tid = t.get('Ticket ID', '')
        if not tid:
            continue
        today_map[tid] = {
            'ticket_id': tid,
            'subject': t.get('Subject', '')[:120],
            'status': t.get('Status', ''),
            'agent': t.get('Agent', ''),
            'group': t.get('Group', ''),
            'created': t.get('Created time', ''),
            'last_update': t.get('Last update time', ''),
        }

    reopen = []
    unchanged_open = []
    new_open = []
    newly_closed = []
    total_open = 0

    for tid, cur in today_map.items():
        prev = history.get(tid)
        if cur['status'] in OPEN_STATUSES:
            total_open += 1
        if prev is None:
            if cur['status'] in OPEN_STATUSES:
                new_open.append(cur)
        else:
            prev_agent = prev.get('agent', '')
            prev_status = prev.get('status', '')
            if cur['status'] in OPEN_STATUSES:
                if prev_agent and prev_agent != 'No Agent' and prev_agent != cur['agent']:
                    reopen.append({**cur, 'previous_agent': prev_agent, 'previous_date': prev.get('last_seen', '')})
                elif prev_agent and prev_agent == cur['agent']:
                    unchanged_open.append(cur)
                else:
                    new_open.append(cur)
            else:
                if prev_status in OPEN_STATUSES:
                    newly_closed.append(cur)

    # --- Summary cards ---
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Total tickets", len(tickets))
    col2.metric("Currently open", total_open)
    col3.metric("⚠️ Re-opened", len(reopen))
    col4.metric("Same agent, still open", len(unchanged_open))
    col5.metric("🆕 New open", len(new_open))

    st.divider()

    # --- Re-opened tickets (the main value) ---
    if reopen:
        st.error(f"⚠️ **{len(reopen)} re-opened / pending tickets — previous agent known**", icon="⚠️")
        st.markdown("💡 **Assign these back to the previous agent.** They already have context.")
        df_reopen = pd.DataFrame([{
            'Ticket ID': t['ticket_id'],
            'Status': t['status'],
            'Previous Agent': t['previous_agent'],
            'Assigned On': t['previous_date'],
            'Subject': t['subject'],
            'Group': t['group'],
        } for t in sorted(reopen, key=lambda x: x['ticket_id'])])
        st.dataframe(df_reopen, use_container_width=True, hide_index=True)

        # Download CSV
        csv_data = df_reopen.to_csv(index=False)
        st.download_button("📄 Download re-open report (CSV)", csv_data, f"reopen_report_{today}.csv", "text/csv")
    else:
        st.success("✅ No re-opened tickets found. All open tickets are either new or already with the same agent.", icon="✅")

    st.divider()

    # --- Still open, same agent ---
    if unchanged_open:
        with st.expander(f"📋 Still open — SAME agent as before ({len(unchanged_open)})"):
            df_same = pd.DataFrame([{
                'Ticket ID': t['ticket_id'],
                'Status': t['status'],
                'Agent': t['agent'],
                'Last Update': t['last_update'][:10],
                'Subject': t['subject'],
            } for t in sorted(unchanged_open, key=lambda x: x['ticket_id'])])
            st.dataframe(df_same, use_container_width=True, hide_index=True)

    # --- New open tickets ---
    if new_open:
        with st.expander(f"🆕 New open tickets — never seen before ({len(new_open)})"):
            df_new = pd.DataFrame([{
                'Ticket ID': t['ticket_id'],
                'Status': t['status'],
                'Agent': t['agent'] if t['agent'] != 'No Agent' else '—',
                'Created': t['created'][:10],
                'Subject': t['subject'],
            } for t in sorted(new_open, key=lambda x: x['ticket_id'])])
            st.dataframe(df_new, use_container_width=True, hide_index=True)

    # --- Newly closed ---
    if newly_closed:
        with st.expander(f"✅ Newly closed since last upload ({len(newly_closed)})"):
            df_closed = pd.DataFrame([{
                'Ticket ID': t['ticket_id'],
                'Agent': t['agent'],
                'Closed': t['last_update'][:10],
                'Subject': t['subject'],
            } for t in sorted(newly_closed, key=lambda x: x['ticket_id'])])
            st.dataframe(df_closed, use_container_width=True, hide_index=True)

    # --- Update history ---
    for tid, cur in today_map.items():
        prev = history.get(tid, {})
        history[tid] = {
            'ticket_id': tid,
            'subject': cur['subject'],
            'status': cur['status'],
            'agent': cur['agent'],
            'group': cur['group'],
            'created': cur['created'],
            'last_update': cur['last_update'],
            'last_seen': today,
            'first_agent': prev.get('first_agent', cur['agent']),
            'agent_history': prev.get('agent_history', []) + ([cur['agent']] if cur['agent'] != prev.get('agent', '') else []),
        }
    # Prune: keep active tickets only
    active = set(today_map.keys())
    history = {tid: v for tid, v in history.items() if tid in active}
    save_history(history)

    st.sidebar.success(f"✅ History updated ({len(history)} tickets tracked)")

# --- Sidebar info ---
with st.sidebar:
    st.header("How it works")
    st.markdown("""
    1. **Upload** today's Freshdesk export (.xls)
    2. We compare every ticket against stored history
    3. Re-opened tickets show the **previous agent** — assign them back
    4. History updates automatically for tomorrow
    """)
    st.divider()
    if os.path.exists(HISTORY_FILE):
        h = load_history()
        st.metric("Tickets in history", len(h))
        st.caption(f"Last updated: {max((v.get('last_seen','') for v in h.values()), default='—')}")
    else:
        st.caption("No history yet — upload a file to start tracking.")
