# --- Streamlit Protocol Tracker with Dropbox Persistence ---
import streamlit as st
import json
import re
import pandas as pd
from datetime import datetime
from io import StringIO
import dropbox

# --- Dropbox Setup ---
DROPBOX_ACCESS_TOKEN = st.secrets["dropbox"]["access_token"]
DROPBOX_FILE_PATH = "/protocol_tracker/protocol_log.csv"
dbx = dropbox.Dropbox(DROPBOX_ACCESS_TOKEN)

def append_to_dropbox_csv(project, task, description, status, subtasks):
    new_data = pd.DataFrame([{
        "Timestamp": datetime.now().isoformat(),
        "Project": project,
        "Task": task,
        "Description": description,
        "Status": status,
        "Subtasks": json.dumps(subtasks)
    }])
    try:
        _, res = dbx.files_download(DROPBOX_FILE_PATH)
        existing = pd.read_csv(StringIO(res.content.decode()))
    except dropbox.exceptions.ApiError:
        existing = pd.DataFrame(columns=["Timestamp", "Project", "Task", "Description", "Status", "Subtasks"])

    updated = pd.concat([existing, new_data], ignore_index=True)
    buffer = StringIO()
    updated.to_csv(buffer, index=False)
    dbx.files_upload(buffer.getvalue().encode(), DROPBOX_FILE_PATH, mode=dropbox.files.WriteMode.overwrite)

def load_tasks_from_dropbox():
    try:
        _, res = dbx.files_download(DROPBOX_FILE_PATH)
        df = pd.read_csv(StringIO(res.content.decode()))
    except dropbox.exceptions.ApiError:
        df = pd.DataFrame(columns=["Timestamp", "Project", "Task", "Description", "Status", "Subtasks"])

    latest_tasks = {}
    for _, row in df.iterrows():
        key = (row["Project"], row["Task"])
        latest_tasks[key] = row

    tasks = []
    for (project, task), row in latest_tasks.items():
        tasks.append({
            "project": project,
            "task": task,
            "description": row["Description"],
            "status": row["Status"],
            "subtasks": json.loads(row["Subtasks"]) if pd.notna(row["Subtasks"]) else []
        })
    return tasks

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

# --- Session Initialization ---
if "tasks" not in st.session_state:
    st.session_state.tasks = load_tasks_from_dropbox()
if "edit_mode" not in st.session_state:
    st.session_state.edit_mode = {}

# --- Page Router ---
st.set_page_config(page_title="Protocol Tracker", layout="wide")
query_params = st.query_params
page = query_params.get("page", ["1 Dashboard"])[0]

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
if st.sidebar.button("📅 Today's Subtasks"):
    st.query_params.update({"page": "4 Daily Tasks"})
    st.rerun()
if st.sidebar.button("📂 Project Overview"):
    st.query_params.update({"page": "5 Project Overview"})
    st.rerun()

# --- Create Task Page ---
if page == "2":
    st.title("➕ Create a New Task")
    project = st.text_input("Project Name")
    task = st.text_input("Task")
    description = st.text_area("Task Description (or steps)")
    status = st.selectbox("Status", ["Not Started", "In Progress", "Completed"])

    if st.button("Save Task"):
        if project and task:
            subtasks = extract_subtasks(description)
            st.session_state.tasks.append({
                "project": project,
                "task": task,
                "description": description,
                "status": status,
                "subtasks": subtasks
            })
            append_to_dropbox_csv(project, task, description, status, subtasks)
            st.success(f"Task '{task}' under project '{project}' saved!")
            st.rerun()
        else:
            st.warning("Please fill in both Project and Task fields.")

# --- Current Tasks Page ---
if page == "3":
    st.title("📋 Current Tasks")

    filtered_tasks = [t for t in st.session_state.tasks if t["status"] != "Deleted"]

    projects = sorted(set(t["project"] for t in filtered_tasks))
    selected_project = st.selectbox("Filter by Project", ["All Projects"] + projects)

    if selected_project != "All Projects":
        project_tasks = [t for t in filtered_tasks if t["project"] == selected_project]
        task_names = sorted(set(t["task"] for t in project_tasks))
        selected_task = st.selectbox("Filter by Task", ["All Tasks"] + task_names)
    else:
        project_tasks = filtered_tasks
        selected_task = "All Tasks"

    for idx, task in enumerate(project_tasks):
        if selected_task != "All Tasks" and task["task"] != selected_task:
            continue

        st.markdown(f"### 🗂️ {task['task']} ({task['project']})")
        if task["subtasks"]:
            st.markdown("**Subtasks:**")
            for sub_idx, sub in enumerate(task["subtasks"]):
                s1, s2 = st.columns([10, 1])
                with s1:
                    st.markdown(f"- [{sub['status']}] **{sub['date_str']}**: {sub['title']}")
                with s2:
                    if st.button("✅", key=f"complete-{idx}-{sub_idx}"):
                        sub["status"] = "Completed"
                        append_to_dropbox_csv(task["project"], task["task"], task["description"], task["status"], task["subtasks"])
                        st.rerun()

        col1, col2 = st.columns([1, 1])
        with col1:
            if st.button("✏️ Edit", key=f"edit-{idx}"):
                st.session_state.edit_mode[idx] = True
        with col2:
            if st.button("🗑️ Delete", key=f"delete-{idx}"):
                append_to_dropbox_csv(task["project"], task["task"], task["description"], "Deleted", task["subtasks"])
                st.session_state.tasks.pop(idx)
                st.rerun()

        if st.session_state.edit_mode.get(idx, False):
            new_desc = st.text_area("Edit Description", value=task["description"], key=f"desc-edit-{idx}")
            if st.button("💾 Save", key=f"save-{idx}"):
                new_subtasks = extract_subtasks(new_desc)
                task["description"] = new_desc
                task["subtasks"] = new_subtasks
                append_to_dropbox_csv(task["project"], task["task"], new_desc, task["status"], new_subtasks)
                st.session_state.edit_mode[idx] = False
                st.rerun()

# --- Daily Tasks Page ---
if page == "4":
    st.title("📅 Today's Subtasks")
    
    from zoneinfo import ZoneInfo
    now_central = datetime.now(ZoneInfo("America/Chicago"))
    today_code = now_central.strftime("%m%d")
    today_num = int(today_code)

    grouped_tasks = {}

    for idx, task in enumerate(st.session_state.tasks):
        if task["status"] == "Deleted":
            continue

        for sub_idx, subtask in enumerate(task["subtasks"]):
            sub_num = int(subtask["date_code"])
            status = subtask["status"]

            # Show only if due today or overdue
            if sub_num <= today_num:
                key = (task["task"], task["project"])
                grouped_tasks.setdefault(key, []).append((sub_idx, subtask, idx))

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
                            append_to_dropbox_csv(
                                st.session_state.tasks[task_idx]["project"],
                                st.session_state.tasks[task_idx]["task"],
                                st.session_state.tasks[task_idx]["description"],
                                st.session_state.tasks[task_idx]["status"],
                                st.session_state.tasks[task_idx]["subtasks"]
                            )
                            st.rerun()
                            
# --- Part 5: Project Overview Page ---
if page == "5":
    st.title("📂 Project Overview")

    filtered_tasks = [t for t in st.session_state.tasks if t["status"] != "Deleted"]

    if filtered_tasks:
        projects = {}
        for task in filtered_tasks:
            projects.setdefault(task["project"], []).append(task)

        cols = st.columns(len(projects)) if len(projects) <= 4 else st.columns(4)

        for col, (project, task_list) in zip(cols * (len(projects) // len(cols) + 1), sorted(projects.items())):
            with col:
                st.markdown(f"### {project}")
                for task in task_list:
                    with st.expander(f"📄 {task['task']}"):
                        st.markdown(f"**Status:** {task['status']}")
                        st.markdown(f"**Description:** {task['description']}")
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
                                st.markdown(
                                    f"<span style='color:{color}'>[{status}] {sub['date_str']}: {sub['title']}</span>",
                                    unsafe_allow_html=True,
                                )
                        else:
                            st.markdown("_No subtasks found._")
    else:
        st.info("No projects or tasks available.")


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

