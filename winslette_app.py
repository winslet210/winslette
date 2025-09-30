# hoscon_app.py
import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime
import json, os

DB_PATH = "hoscon_demo.db"

# --- DB utilities ---
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("""CREATE TABLE IF NOT EXISTS departments (
        id INTEGER PRIMARY KEY,
        name TEXT UNIQUE,
        status TEXT,
        notes TEXT
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS staff (
        id INTEGER PRIMARY KEY,
        name TEXT,
        role TEXT,
        department_id INTEGER,
        present INTEGER DEFAULT 0
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS incidents (
        id INTEGER PRIMARY KEY,
        type TEXT,
        description TEXT,
        timestamp TEXT,
        priority TEXT,
        status TEXT DEFAULT 'Open'
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY,
        incident_id INTEGER,
        title TEXT,
        assigned_to INTEGER,
        status TEXT,
        timestamp TEXT,
        resource_id INTEGER
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS resources (
        id INTEGER PRIMARY KEY,
        name TEXT UNIQUE,
        quantity INTEGER,
        unit TEXT
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS communication_logs (
        id INTEGER PRIMARY KEY,
        timestamp TEXT,
        sender TEXT,
        recipient TEXT,
        message TEXT,
        incident_id INTEGER
    )""")


    conn.commit()
    return conn

conn = init_db()

def query_df(query, params=()):
    return pd.read_sql_query(query, conn, params=params)

# --- Export ---
def export_all():
    os.makedirs("exports", exist_ok=True)
    bundle = {}
    for t in ["departments","staff","incidents","tasks", "resources", "communication_logs"]:
        df = query_df(f"SELECT * FROM {t}")
        df.to_csv(f"exports/{t}.csv", index=False)
        bundle[t] = df.to_dict(orient="records")
    with open("exports/bundle.json","w") as f:
        json.dump(bundle, f, indent=2)
    return os.listdir("exports")

# --- UI ---
st.title("🏥 HOSCON – Hospital Situational Control")
st.write("""
HOSCON is a Hospital Situational Control application designed to enhance awareness and management during critical situations.
Key Features:
- **Department Status Monitoring**: Track the operational status (Green, Yellow, Red) and add notes for each hospital department.
- **Staff Muster**: Manage staff details, roles, and check-in status to monitor personnel availability.
- **Incident Logging & Tracking**: Record and track incidents with details including type, description, timestamp, priority level, and status (Open, In Progress, Resolved).
- **Task Assignment & Follow-up**: Assign tasks related to incidents to staff members and monitor their progress.
- **Resource Availability Dashboard**: Monitor the availability of critical resources such as beds, medical supplies, and equipment.
- **Data Export**: Export all application data to CSV and JSON formats for reporting and analysis.
""") # Updated with a more detailed description
st.write("Author: Kate Abonyo (winsletkate210@gmail.com)")

# Removed "Staff Muster" from the tabs list and added "Resources" and "Export"
tab1, tab2, tab3, tab4, tab5 = st.tabs(["Dashboard", "Role & Tasks", "Incidents", "Resources", "Export"])

with tab1:
    st.subheader("Department Status")
    df = query_df("SELECT * FROM departments")
    st.dataframe(df)

    dept = st.selectbox("Select Department", df["name"])
    status = st.radio("Status", ["Green","Yellow","Red"])
    notes = st.text_area("Notes")
    if st.button("Update Department Status"): # Changed button label for clarity
        conn.execute("UPDATE departments SET status=?, notes=? WHERE name=?",
                     (status, notes, dept))
        conn.commit()
        st.success("Updated!")
        st.dataframe(query_df("SELECT * FROM departments"))

with tab2:
    st.subheader("Assign Roles / Create Tasks")
    staff = query_df("SELECT * FROM staff")
    staff_name = st.selectbox("Assign To", staff["name"] if not staff.empty else [])
    inc_type = st.text_input("Incident Type")
    inc_desc = st.text_area("Incident Description")
    inc_priority = st.selectbox("Priority", ["Low", "Medium", "High", "Critical"]) # Added priority selectbox
    inc_status = st.selectbox("Status", ["Open", "In Progress", "Resolved"]) # Added status selectbox
    initial_task_title = st.text_input("Initial Task Title", value="Initial Response") # Added input for initial task title


    if st.button("Log Incident and Assign Task"): # Changed button label
        ts = datetime.utcnow().isoformat()
        conn.execute("INSERT INTO incidents(type,description,timestamp,priority,status) VALUES (?,?,?,?,?)", # Updated insert statement
                     (inc_type, inc_desc, ts, inc_priority, inc_status)) # Updated values
        inc_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.execute("INSERT INTO tasks(incident_id,title,assigned_to,status,timestamp) VALUES (?,?,?,?,?)",
                     (inc_id,initial_task_title, # Used the input task title
                      staff[staff["name"]==staff_name]["id"].values[0] if not staff.empty else None,
                      "Open", ts))
        conn.commit()
        st.success("Incident logged and initial task assigned.") # Updated success message

with tab3:
    st.subheader("Incidents & Tasks")
    st.dataframe(query_df("SELECT * FROM incidents"))
    tasks = query_df("SELECT * FROM tasks")
    st.dataframe(tasks)
    if not tasks.empty:
        task_id = st.selectbox("Select Task", tasks["id"])
        new_status = st.radio("Update Status", ["Open","In Progress","Completed"])
        if st.button("Update Task"):
            conn.execute("UPDATE tasks SET status=?, timestamp=? WHERE id=?",
                         (new_status, datetime.utcnow().isoformat(), task_id))
            conn.commit()
            st.success("Task updated.")
            st.dataframe(query_df("SELECT * FROM tasks"))

# Removed the entire elif block for "Staff Muster"


with tab4: # This is now the "Resources" tab
    st.subheader("Resource Availability")

    st.subheader("Add New Resource")
    new_resource_name = st.text_input("Resource Name")
    new_resource_quantity = st.number_input("Quantity", min_value=0, step=1)
    new_resource_unit = st.text_input("Unit (e.g., beds, cylinders)")
    if st.button("Add Resource"):
        if new_resource_name and new_resource_quantity is not None and new_resource_unit:
            try:
                conn.execute("INSERT INTO resources(name, quantity, unit) VALUES (?, ?, ?)",
                             (new_resource_name, new_resource_quantity, new_resource_unit))
                conn.commit()
                st.success(f"Resource '{new_resource_name}' added.")
            except sqlite3.IntegrityError:
                st.error(f"Resource '{new_resource_name}' already exists.")
        else:
            st.warning("Please fill in all fields to add a new resource.")

    st.subheader("Update Resource Quantity")
    resources_df = query_df("SELECT * FROM resources")
    resource_to_update_name = st.selectbox("Select Resource to Update", resources_df["name"] if not resources_df.empty else [])
    if resource_to_update_name:
        current_resource_info = resources_df[resources_df["name"] == resource_to_update_name].iloc[0]
        updated_quantity = st.number_input("New Quantity", min_value=0, step=1, value=int(current_resource_info["quantity"]))
        if st.button("Update Quantity"):
            resource_id_to_update = current_resource_info["id"]
            conn.execute("UPDATE resources SET quantity=? WHERE id=?",
                         (updated_quantity, resource_id_to_update))
            conn.commit()
            st.success(f"Quantity for '{resource_to_update_name}' updated.")

    st.subheader("Current Resource Levels")
    st.dataframe(query_df("SELECT * FROM resources"))


with tab5: # This is now the "Export" tab
    st.subheader("Export Data")
    if st.button("Export to CSV + JSON"):
        files = export_all()
        st.write("Exported files:", files)
        st.info("Use the file browser to download from the `exports/` folder.")