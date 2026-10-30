# SentinelAI — Phase 5 Frontend & UI/UX

A runnable Flask + SQLite demo dashboard for a hackathon phishing incident investigation and response workflow. It includes Dashboard, Incident Management, Agent Activity, Human Approval Queue, Audit Logs, and CSV export.

> **Demo note:** Sample incidents and agent activity are simulated. This project does not connect to mailboxes or run real AI/security analysis. Integrate the outputs from your team's Phases 1–4 before using it with real data. Approval actions in this demo update the local SQLite database only.

## Run in VS Code (Windows)
1. Extract `SentinelAI_Phase5.zip`.
2. Open the extracted `SentinelAI_Phase5` folder in VS Code.
3. Open **Terminal → New Terminal**.
4. Run:
   ```powershell
   py -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   python app.py
   ```
5. Open `http://127.0.0.1:5000` in your browser.

The `sentinelai.db` SQLite database is created automatically. Stop the server with `Ctrl+C`.
