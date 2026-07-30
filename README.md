# 📋 PlannerPro - Productivity & Task Management System

A responsive Python Flask web application designed for personal and team productivity, allowing users to manage Kanban tasks, schedule events, keep track of quick notes, utilize a Pomodoro focus timer, and handle administrative user control.

---

## 🚀 Live Access & Local Deployment

**Live Application URL:** [https://hluvuko.pythonanywhere.com](https://hluvuko.pythonanywhere.com)  
**Local Development URL:** [http://127.0.0.1:5000](http://127.0.0.1:5000)

To explore the application without creating a new account, feel free to log in using the pre-configured test credentials below:

### 👑 Administrator Portal
* **Username:** `admin`
* **Password:** `admin123`
* **Role:** Administrator (Access to user management panel, global task metrics, and system oversight)

### 👤 Standard User Portal (Demo Accounts)
You can register these users manually via the `/register` page and add their sample tasks and events to test functionality:

* **User 1:** 
  * **Username:** `Thabo` | **Password:** `Thabo123!` | **Email:** `thabo@planner.com`
  * **Sample Test Data:** *Task:* Finalize quarterly financial report (High Priority, In Progress) | *Event:* Budget Review Sync (Public)
* **User 2:** 
  * **Username:** `Lerato` | **Password:** `Lerato456!` | **Email:** `lerato@planner.com`
  * **Sample Test Data:** *Task:* Design new mobile app onboarding screens (High Priority, To Do) | *Event:* UI/UX Design Critique (Private)
* **User 3:** 
  * **Username:** `Sipho` | **Password:** `Sipho789!` | **Email:** `sipho@planner.com`
  * **Sample Test Data:** *Task:* Set up CI/CD deployment pipeline (High Priority, In Progress) | *Event:* DevOps Weekly Standup (Public)

---

## ✨ Features
* **Role-Based Access Control:** Distinct workflows and security checks separating standard users from system administrators.
* **Kanban Task Boards:** Interactive columns (*To Do*, *In Progress*, *Completed*) equipped with subtask tracking and priority management.
* **Event Calendar & Public Events:** Coordinate schedules, track personal events, and copy public events directly into your calendar.
* **Pomodoro Focus Timer:** Integrated focus session timer to optimize daily workflow and productivity.
* **Admin Control Panel:** Dedicated dashboard to edit users, toggle admin privileges, delete accounts, and view global platform activity.
* **Responsive Design:** Clean, modern interface optimized for desktop, tablet, and mobile displays.

---

## 🛠️ Tech Stack
* **Backend:** Python 3.x, Flask, Werkzeug Security (Password Hashing)
* **Database:** SQLite (`sqlite3`)
* **Frontend:** HTML5, CSS3, JavaScript, Jinja2 Templates, Lucide Icons
* **Server Environment:** PythonAnywhere / Flask Development Server

---

## 📦 Installation & Setup Instructions

### 1. Clone the Repository
```bash
git clone [https://github.com/Hluvuko2004/planner-app.git](https://github.com/Hluvuko2004/planner-app.git)
cd planner-app