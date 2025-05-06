# Part 1: Setup, DB, and Navigation
import streamlit as st
import sqlite3
import json
import re
import pandas as pd
from datetime import datetime

# --- Extract subtasks from description ---
def extract_subtasks(description_text):
    subtasks = []
    pattern = r"(\d{4}):\s*(.+)"
    matches = re.findall(pattern, description_text)

    for code, text in matches:
        month = int(code[:2])
        day = int(code[2:])
        try:
            date_obj = datetime.strptime(f"{month:02d}{day:02d}", "%m%d")
            date_str = date_obj.strftime("%B %d")
        except ValueError:
            date_str = f"Invalid date ({code})"
        subtasks.append({
            "date_code": code,
            "date_str": date_str,
            "title": text,
            "status": "Not Started"
        })
    return subtasks

# --- DB Setup ---
def init_db():
    conn = sqlite3.connect("tasks.db")
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project TEXT,
            task TEXT,
            description TEXT,
            status TEXT,
            subtasks TEXT
        )
    ''')
    conn.commit()
    conn.close()

def load_tasks_from_db():
    conn = sqlite3.connect("tasks.db")
    c = conn.cursor()
    c.execute("SELECT project, task, description, status, subtasks FROM tasks")
    rows = c.fetchall()
    conn.close()

    tasks = []
    for row in rows:
        project, task, description, status, subtasks_json = row
        subtasks = json.loads(subtasks_json)
        tasks.append({
            "project": project,
            "task": task,
            "description": description,
            "status": status,
            "subtasks": subtasks
        })
    return tasks

init_db()
if "tasks" not in st.session_state:
    st.session_state.tasks = load_tasks_from_db()
if "edit_mode" not in st.session_state:
    st.session_state.edit_mode = {}

# --- Read page from query params (default to Dashboard) ---
query_params = st.query_params
page = query_params.get("page", ["Dashboard"])[0]

# --- Manual navigation buttons in sidebar ---
st.sidebar.title("Navigation")
if st.sidebar.button("🏠 Dashboard"):
    st.query_params.update({"page": "1 Dashboard"})
    st.rerun()
if st.sidebar.button("➕ Create Task"):
    st.query_params.update({"page": "2 Create Task"})
    st.rerun()
if st.sidebar.button("📋 Current Tasks"):
    st.query_params.update({"page": "3 Current Tasks"})
    st.rerun()
if st.sidebar.button("📅 Daily Tasks"):
    st.query_params.update({"page": "4 Daily Tasks"})
    st.rerun()
if st.sidebar.button("📂 Project Overview"):
    st.query_params.update({"page": "5 Project Overview"})
    st.rerun()

# --- Export Button ---
def export_all_tasks_to_csv(filename="all_tasks_export.csv"):
    conn = sqlite3.connect("tasks.db")
    c = conn.cursor()
    c.execute("SELECT project, task, description, status, subtasks FROM tasks")
    rows = c.fetchall()
    conn.close()

    def format_subtasks(subtask_json):
        try:
            subtasks = json.loads(subtask_json)
            return "\n".join([f"{s.get('date_str', '?')}: {s.get('title', '?')} [{s.get('status', '?')}]" for s in subtasks])
        except:
            return "[Invalid subtasks]"

    data = [[p, t, d, s, format_subtasks(subs)] for p, t, d, s, subs in rows]
    df = pd.DataFrame(data, columns=["Project", "Task", "Description", "Status", "Subtasks"])
    df.to_csv(filename, index=False)
    return filename

st.markdown("---")
if st.button("⬅️ Back to Dashboard", key="back-dashboard"):
    st.query_params.update({"page": "1"})  # Assuming "1" maps to Dashboard
    st.rerun()


# --- Part 2: Create Task Page ---
if page == "2":
    st.title("➕ Create a New Task")

    project = st.text_input("Project Name")
    task = st.text_input("Task")
    description = st.text_area("Task Description (or steps)")
    status = st.selectbox("Status", ["Not Started", "In Progress", "Completed"])

    if st.button("Save Task"):
        if project and task:
            subtasks = extract_subtasks(description)
            conn = sqlite3.connect("tasks.db")
            c = conn.cursor()
            c.execute('''
                INSERT INTO tasks (project, task, description, status, subtasks)
                VALUES (?, ?, ?, ?, ?)''',
                (project, task, description, status, json.dumps(subtasks)))
            conn.commit()
            conn.close()

            st.session_state.tasks.append({
                "project": project,
                "task": task,
                "description": description,
                "status": status,
                "subtasks": subtasks
            })
            st.success(f"Task '{task}' under project '{project}' saved!")
            st.rerun()
        else:
            st.warning("Please fill in both Project and Task fields.")

# --- Part 3: Current Tasks Page ---
if page == "3":
    st.title("📋 Current Tasks")

    st.markdown("---")
    st.markdown("### 📤 Export All Tasks")
    if st.button("Export All Tasks to CSV", key="export-csv"):
        filename = export_all_tasks_to_csv()
        st.success(f"Tasks exported to `{filename}`")
        with open(filename, "rb") as f:
            st.download_button("⬇️ Download CSV", f, file_name=filename, mime="text/csv", key="download-csv")

    if st.session_state.tasks:
        projects = sorted(set(t["project"] for t in st.session_state.tasks))
        selected_project = st.selectbox("Filter by Project", ["All Projects"] + projects)

        filtered = [t for t in st.session_state.tasks if selected_project == "All Projects" or t["project"] == selected_project]
        tasks = sorted(t["task"] for t in filtered)
        selected_task = st.selectbox("Filter by Task", ["All Tasks"] + tasks)

        if selected_task != "All Tasks":
            filtered = [t for t in filtered if t["task"] == selected_task]

        for idx, task in enumerate(filtered):
            col_main, col_del, col_edit = st.columns([10, 1, 1])

            with col_main:
                st.markdown(f"### 🗂️ {task['task']} ({task['project']})")
                st.markdown(f"**Main Status:** {task['status']}")
                if task["subtasks"]:
                    st.markdown("**Subtasks:**")
                    for sub_idx, sub in enumerate(task["subtasks"]):
                        s1, s2 = st.columns([20, 1])
                        with s1:
                            st.markdown(f"- [{sub['status']}] **{sub['date_str']}**: {sub['title']}")
                        with s2:
                            if st.button("✅", key=f"complete-{idx}-{sub_idx}"):
                                task["subtasks"][sub_idx]["status"] = "Completed"
                                conn = sqlite3.connect("tasks.db")
                                c = conn.cursor()
                                c.execute("UPDATE tasks SET subtasks = ? WHERE project = ? AND task = ?", (json.dumps(task["subtasks"]), task["project"], task["task"]))
                                conn.commit()
                                conn.close()
                                st.rerun()

            with col_del:
                if st.button("🗑️", key=f"delete-{idx}"):
                    conn = sqlite3.connect("tasks.db")
                    c = conn.cursor()
                    c.execute("DELETE FROM tasks WHERE project = ? AND task = ?", (task["project"], task["task"]))
                    conn.commit()
                    conn.close()
                    st.session_state.tasks.pop(idx)
                    st.rerun()

            with col_edit:
                if st.button("✏️", key=f"edit-{idx}"):
                    st.session_state.edit_mode[idx] = True

            if st.session_state.edit_mode.get(idx, False):
                st.markdown("**Edit Task Description:**")
                new_desc = st.text_area("Description", value=task["description"], key=f"edit-desc-{idx}")
                if st.button("💾 Save Changes", key=f"save-{idx}"):
                    new_subtasks = extract_subtasks(new_desc)
                    task["description"] = new_desc
                    task["subtasks"] = new_subtasks
                    conn = sqlite3.connect("tasks.db")
                    c = conn.cursor()
                    c.execute("UPDATE tasks SET description = ?, subtasks = ? WHERE project = ? AND task = ?", (new_desc, json.dumps(new_subtasks), task["project"], task["task"]))
                    conn.commit()
                    conn.close()
                    st.success("✅ Task updated.")
                    st.session_state.edit_mode[idx] = False
                    st.rerun()
    else:
        st.info("No tasks available.")

# --- Part 4: Daily Tasks Page ---
if page == "4":
    st.title("📅 Today's Subtasks")
    
    from datetime import datetime
    from zoneinfo import ZoneInfo

    now_central = datetime.now(ZoneInfo("America/Chicago"))
    today_code = now_central.strftime("%m%d")
    today_num = int(today_code)

    grouped_tasks = {}  # {(task, project): [subtasks]}

    for idx, task in enumerate(st.session_state.tasks):
        for sub_idx, subtask in enumerate(task["subtasks"]):
            sub_num = int(subtask["date_code"])
            status = subtask["status"]

            # Show only tasks due today or overdue (and not yet completed)
            if sub_num <= today_num and not (status == "Completed" and sub_num < today_num):
                key = (task["task"], task["project"])
                if key not in grouped_tasks:
                    grouped_tasks[key] = []
                grouped_tasks[key].append((sub_idx, subtask, idx))  # (sub_idx, subtask, task_idx)

    if not grouped_tasks:
        st.info("No subtasks due today or earlier.")
    else:
        for (task_name, project_name), sublist in grouped_tasks.items():
            st.markdown(f"### 🔹 From Task: *{task_name}*, Project: *{project_name}*")
            for sub_idx, subtask, task_idx in sublist:
                col1, col2 = st.columns([6, 1])
                with col1:
                    status = subtask["status"]
                    title = subtask["title"]

                    if status == "Completed":
                        st.markdown(f"<span style='color:gray'><s>{title}</s></span>", unsafe_allow_html=True)
                    elif int(subtask["date_code"]) < today_num:
                        st.markdown(f"<span style='color:red'>[Overdue] {title}</span>", unsafe_allow_html=True)
                    else:
                        st.markdown(f"**{title}**")

                with col2:
                    if status != "Completed":
                        if st.button("✅", key=f"complete-today-{task_idx}-{sub_idx}"):
                            st.session_state.tasks[task_idx]["subtasks"][sub_idx]["status"] = "Completed"

                            # Update DB
                            conn = sqlite3.connect("tasks.db")
                            c = conn.cursor()
                            c.execute("UPDATE tasks SET subtasks = ? WHERE project = ? AND task = ?",
                                      (json.dumps(st.session_state.tasks[task_idx]["subtasks"]),
                                       project_name, task_name))
                            conn.commit()
                            conn.close()
                            st.rerun()

# --- Part 5: Project Overview Page ---
if page == "5":
    st.title("📂 Project Overview")

    if st.session_state.tasks:
        projects = {}
        for task in st.session_state.tasks:
            projects.setdefault(task["project"], []).append(task)

        cols = st.columns(len(projects))

        for col, (project, task_list) in zip(cols, sorted(projects.items())):
            with col:
                st.markdown(f"### {project}")
                for task in task_list:
                    with st.expander(f"📄 {task['task']}"):
                        if task["subtasks"]:
                            st.markdown("**Subtasks:**")
                            for sub in task["subtasks"]:
                                status = sub["status"]
                                if status == "Completed":
                                    color = "green"
                                elif status == "In Progress":
                                    color = "orange"
                                else:
                                    color = "red"
                                st.markdown(f"<span style='color:{color}'>[{status}] {sub['date_str']}: {sub['title']}</span>", unsafe_allow_html=True)
                        else:
                            st.markdown("_No subtasks found._")
    else:
        st.info("No projects or tasks yet.")

# --- Part 6: Dashboard Page ---
if page == "1":
    st.title("📊 Protocol Tracker Dashboard")

    total_projects = len(set(task["project"] for task in st.session_state.tasks))
    total_tasks = len(st.session_state.tasks)

    today = datetime.now()
    today_code = today.strftime("%m%d")
    today_num = int(today_code)

    overdue_count = 0
    today_count = 0

    for task in st.session_state.tasks:
        for sub in task.get("subtasks", []):
            sub_num = int(sub["date_code"])
            if sub["status"] != "Completed":
                if sub_num < today_num:
                    overdue_count += 1
                elif sub_num == today_num:
                    today_count += 1

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("🧪 Total Projects", total_projects)
    with col2:
        st.metric("📂 Total Tasks", total_tasks)
    with col3:
        st.metric("⚠️ Overdue Subtasks", overdue_count)
    with col4:
        st.metric("📅 Today's Subtasks", today_count)

    # Quick Navigation
    st.markdown("---")
    st.markdown("### Quick Navigation")
    col_nav1, col_nav2 = st.columns(2)

    with col_nav1:
        if st.button("➕ Create Task", key="nav-create-btn"):
            st.query_params.update({"page": "2"})
            st.rerun()
        if st.button("📋 View Tasks", key="nav-tasks-btn"):
            st.query_params.update({"page": "3"})
            st.rerun()

    with col_nav2:
        if st.button("📅 Daily Tasks", key="nav-daily-btn"):
            st.query_params.update({"page": "4"})
            st.rerun()
        if st.button("📂 Project Overview", key="nav-projects-btn"):
            st.query_params.update({"page": "5"})
            st.rerun()

