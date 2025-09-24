import datetime
import pandas as pd
import streamlit as st
import altair as alt
import base64
import requests
import io

# ----------------------------
# GitHub API Helpers
# ----------------------------
TOKEN = st.secrets["GITHUB_TOKEN"]
REPO = st.secrets["GITHUB_REPO"]  # e.g. "username/reponame"
FILEPATH = st.secrets["GITHUB_FILEPATH"]  # e.g. "tickets.csv"
BRANCH = "main"  # change if your repo uses "master"

def get_file_info():
    url = f"https://api.github.com/repos/{REPO}/contents/{FILEPATH}?ref={BRANCH}"
    headers = {"Authorization": f"token {TOKEN}"}
    r = requests.get(url, headers=headers)
    if r.status_code == 200:
        return r.json()  # contains sha + content
    elif r.status_code == 404:
        return None
    else:
        st.error(f"GitHub error: {r.json()}")
        return None

def load_tickets():
    info = get_file_info()
    if info and "content" in info:
        content = base64.b64decode(info["content"]).decode("utf-8")
        return pd.read_csv(io.StringIO(content))
    # fallback empty DataFrame
    return pd.DataFrame(columns=["ID","Issue","Status","Priority","Date Submitted"])

def save_tickets(df):
    csv_bytes = df.to_csv(index=False).encode("utf-8")
    b64 = base64.b64encode(csv_bytes).decode("utf-8")
    info = get_file_info()
    sha = info["sha"] if info else None

    url = f"https://api.github.com/repos/{REPO}/contents/{FILEPATH}"
    headers = {"Authorization": f"token {TOKEN}"}
    data = {
        "message": "Update tickets.csv from Streamlit app",
        "content": b64,
        "branch": BRANCH,
    }
    if sha:
        data["sha"] = sha

    r = requests.put(url, headers=headers, json=data)
    if r.status_code not in (200,201):
        st.error(f"GitHub save failed: {r.json()}")
    else:
        st.success("Tickets saved to GitHub 🚀")


# ----------------------------
# Streamlit UI
# ----------------------------
st.set_page_config(page_title="Tasks", page_icon="🎫")
st.title("Tasks")
st.write("Matt's Task Ticketing")

# Load tickets from GitHub into session state
if "df" not in st.session_state:
    st.session_state.df = load_tickets()

# ----------------------------
# Add ticket form
# ----------------------------
st.header("Add a ticket")
with st.form("add_ticket_form"):
    issue = st.text_area("Describe the tasks")
    priority = st.selectbox("Priority", ["High", "Medium", "Low"])
    submitted = st.form_submit_button("Submit")

if submitted:
    if len(st.session_state.df) > 0:
        recent_ticket_number = int(max(st.session_state.df.ID).split("-")[1])
    else:
        recent_ticket_number = 1000

    today = datetime.datetime.now().strftime("%m-%d-%Y")
    df_new = pd.DataFrame(
        [
            {
                "ID": f"TICKET-{recent_ticket_number+1}",
                "Issue": issue,
                "Status": "Open",
                "Priority": priority,
                "Date Submitted": today,
            }
        ]
    )

    st.write("Ticket submitted! Here are the ticket details:")
    st.dataframe(df_new, use_container_width=True, hide_index=True)
    st.session_state.df = pd.concat([df_new, st.session_state.df], axis=0)

    # Save to GitHub
    save_tickets(st.session_state.df)

# ----------------------------
# Existing tickets
# ----------------------------
st.header("Existing tickets")
st.write(f"Number of tickets: `{len(st.session_state.df)}`")

st.info(
    "You can edit the tickets by double clicking on a cell, or delete rows directly. "
    "After editing/deleting, press **Save Tickets** to persist changes back to GitHub.",
    icon="✍️",
)

edited_df = st.data_editor(
    st.session_state.df,
    use_container_width=True,
    hide_index=True,
    num_rows="dynamic",  # 👈 allows adding/removing rows
    column_config={
        "Status": st.column_config.SelectboxColumn(
            "Status", options=["Open", "In Progress", "Closed"], required=True
        ),
        "Priority": st.column_config.SelectboxColumn(
            "Priority", options=["High", "Medium", "Low"], required=True
        ),
    },
    disabled=["ID", "Date Submitted"],
)

# Button to persist edits (including deletions)
if st.button("Save Tickets"):
    st.session_state.df = edited_df
    save_tickets(st.session_state.df)
    st.success("Changes saved to GitHub ✅")

# ----------------------------
# Stats
# ----------------------------
st.header("Statistics")
col1, col2, col3 = st.columns(3)
num_open_tickets = len(st.session_state.df[st.session_state.df.Status == "Open"])
col1.metric("Number of open tickets", num_open_tickets, delta=0)
col2.metric("First response time (hours)", 0, delta=0)
col3.metric("Average resolution time (hours)", 0, delta=0)

if len(st.session_state.df) > 0:
    st.write("##### Ticket status per month")
    status_plot = (
        alt.Chart(st.session_state.df)
        .mark_bar()
        .encode(
            x="month(Date Submitted):O",
            y="count():Q",
            xOffset="Status:N",
            color="Status:N",
        )
    )
    st.altair_chart(status_plot, use_container_width=True, theme="streamlit")

    st.write("##### Current ticket priorities")
    priority_plot = (
        alt.Chart(st.session_state.df)
        .mark_arc()
        .encode(theta="count():Q", color="Priority:N")
        .properties(height=300)
    )
    st.altair_chart(priority_plot, use_container_width=True, theme="streamlit")
