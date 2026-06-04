# 📧 MailFlow

MailFlow is a lightweight, self-hosted web dashboard and email processing pipeline. It connects to your configured Gmail accounts, scans recent emails, stores a local cache in SQLite, and provides a web-based UI to inspect logs, trigger manual scans, and export beautiful Excel reports.

---

## 🚀 Features

- **Multi-Account IMAP Scanning**: Scans multiple Gmail accounts simultaneously within a configurable lookback window (e.g., last 48 hours).
- **Embedded Web Dashboard**: Fully local, lightweight dashboard to view scan progress, logs, and historical emails.
- **Local SQLite Cache**: Saves scan history to a local SQLite database (`emails.db`) for instant retrieval.
- **Excel Report Generator**: One-click generation of detailed spreadsheet summaries (`Email_Report.xlsx`).
- **Modern Packaging with `uv`**: Uses the fast `uv` tool to manage the project virtual environment and packages cleanly.

---

## 🛠️ Requirements & Setup

Make sure you have [uv](https://github.com/astral-sh/uv) installed on your system.

### 1. Initialize the Virtual Environment
Create the virtual environment and install the required dependencies:
```bash
uv sync
```

### 2. Configure Environment Variables
Create a `.env` file in the root of the project to add your credentials. Use Gmail **App Passwords** (not your master Google password) for IMAP access:

```env
EMAIL_LOOKBACK_HOURS = "48"
EMAIL_1 = "your-first-email@gmail.com"
EMAIL_1_PASSWORD = "xxxx-xxxx-xxxx-xxxx"
EMAIL_2 = "your-second-email@gmail.com"
EMAIL_2_PASSWORD = "yyyy-yyyy-yyyy-yyyy"
```

---

## 🏃 Running the Application

Start the threaded web server:
```bash
uv run python app.py
```

Once running, navigate your web browser to:
👉 **[http://127.0.0.1:8080](http://127.0.0.1:8080)**

---

## 📂 Project Structure

```text
mailflow/
├── app.py           # Web server entrypoint, API routes, and static serving
├── pipeline.py      # Core email retrieval logic, SQLite database integration, and Excel generator
├── .env             # Configurations and account secrets (git-ignored)
├── emails.db        # SQLite database caching retrieved email logs (git-ignored)
├── pyproject.toml   # Project dependencies and python settings
├── uv.lock          # Lockfile for reproducible builds
└── static/          # Web dashboard assets
    ├── index.html   # Main Dashboard HTML layout
    ├── style.css    # Premium CSS design
    └── app.js       # Dynamic AJAX logic and state updates
```

---

## 🔒 Security Notice

**Never commit your `.env` or `emails.db` files.** The repository is pre-configured with a `.gitignore` to keep your passwords, active email addresses, and downloaded email content secure.
