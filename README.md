# 🛡️ Command Gateway

**Unbound Hackathon Submission**  
**Role:** Backend / Full Stack  
**Deadline:** Dec 11, 2025

A centralized Command Gateway system that acts as a firewall for shell command execution. It allows administrators to configure security rules, manage user credits, and audit all system activity. Risky commands (like `sudo`) require manual admin approval before execution.

---

## 🚀 Features

### 🔐 Security & Rules
*   **Regex-Based Rule Engine:** Admins define patterns (e.g., `^rm.*`) to `AUTO_ACCEPT`, `AUTO_REJECT`, or `REQUIRE_APPROVAL`.
*   **Approval Workflow:** Risky commands enter a "Pending" state and must be approved by an Admin before the user can execute them.
*   **Input Validation:** Strict validation for command syntax and regex patterns.

### 👥 User Management
*   **Role-Based Access:** Distinct `Admin` and `Member` roles.
*   **API Key Authentication:** Stateless authentication using secure, random API keys.
*   **Credit System:** Users spend credits to execute commands. Commands are blocked if credits run out.

### 📊 Observability
*   **Global Audit Trail:** Admins can view a real-time log of every action taken by every user.
*   **Personal History:** Members can view their own execution history and status.
*   **Transaction Integrity:** Database operations (credits + logging) use atomic transactions to ensure data consistency.

---

## 🛠️ Tech Stack

*   **Backend:** Python 3.9+, FastAPI
*   **Database:** SQLite (via SQLModel / SQLAlchemy)
*   **Frontend:** HTML5, Tailwind CSS, Alpine.js (No build step required)
*   **Tools:** Uvicorn (ASGI Server)

---

## 📂 Project Structure

```text
command_gateway/
├── backend/
│   ├── main.py        # API Routes, Logic, and Auth
│   └── models.py      # Database Schema & Pydantic Models
├── frontend/
│   ├── index.html     # Main Dashboard (Admin + Member view)
│   ├── login.html     # Authentication Page
│   ├── style.css      # Custom styles
│   └── app.js         # Frontend Logic (Alpine.js)
├── gateway.db         # Auto-generated SQLite Database
└── requirements.txt   # Python Dependencies
```
## ⚡ Getting Started

### 1. Prerequisites
*   Python 3.8 or higher installed.

### 2. Installation
Clone the repository and install dependencies:

```bash
# Clone the repo
git clone https://github.com/yourusername/command-gateway.git
cd command_gateway
```
# Install dependencies
```bash
pip install -r requirements.txt
```

###command to run
```bash
uvicorn backend.main:app --reload
```

Here is the content formatted using Markdown for clarity and hierarchy.

---

## 🔑 Application Access and Workflow

### 🗝️ Default Admin Login

When the app starts for the first time, it seeds a default admin user:

| Field | Value |
| :--- | :--- |
| **API Key** | `admin-secret-key` |

---

### 👮 For Admins

#### Dashboard
* **Log in** to see the **Admin Control Panel**.

#### Manage Rules
* **Add regex patterns** (e.g., `^git.*` $\rightarrow$ `AUTO_ACCEPT`).
* Set a rule like `sudo.*` $\rightarrow$ `REQUIRE_APPROVAL` to test the workflow.
* **Delete rules** using the `×` button.

#### Approve Commands
* When a user submits a restricted command, it appears in "**Pending Approvals**".
* Click "**Accept**" or "**Reject**" to process the request.

#### Create Users
* **Generate new API keys** for team members.

#### Audit
* View the **Global Audit Trail** to see who executed what command.

---

### 👤 For Members

#### Execute
* **Log in** with your unique API Key.

#### Terminal
* Type commands (e.g., `ls -la`, `echo "hello"`).
    * 🟢 **Green:** Executed successfully (Cost: -1 Credit).
    * 🔴 **Red:** Rejected by a security rule.
    * 🟡 **Yellow:** Pending Admin Approval.

#### History
* View your personal command log on the right panel.

---

### 🧪 Testing the Approval Flow

This demonstrates the process for restricted commands. 

1.  **As Admin:** Add a rule: `^test.*` $\rightarrow$ `REQUIRE_APPROVAL`.
2.  **As Member:** Run command `test connection`.
    * **Result:** Terminal shows "Approval required" (Yellow status).
3.  **As Admin:** Go to the dashboard, see the pending request, click **Accept**.
4.  **As Member:** Run command `test connection` again.
    * **Result:** Terminal shows "**Command executed**" (Green status).
