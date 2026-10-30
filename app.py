from flask import Flask, render_template, request, redirect, url_for, flash, Response
import sqlite3, os, csv, io
from datetime import datetime

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'sentinelai-demo-key-change-me')
DB = os.path.join(os.path.dirname(__file__), 'sentinelai.db')

INCIDENT_SEED = [
 ("INC-1048", "Urgent mailbox quota warning", "security@micr0soft-support.example", "High", "Under Investigation", "2026-10-30 09:42", "Spoofed sender domain; credential-harvesting link; urgency language."),
 ("INC-1047", "Updated payroll document", "payroll-review@example.net", "Critical", "Awaiting Approval", "2026-10-30 08:55", "Suspicious attachment; mismatched reply-to; macro-like file extension."),
 ("INC-1046", "Shared project file", "collab-notify@example.org", "Medium", "Contained", "2026-10-29 17:18", "Unexpected sign-in prompt and newly registered sender domain."),
 ("INC-1045", "Invoice payment overdue", "accounts@example.co", "Low", "Resolved", "2026-10-29 15:03", "Bulk-mail traits detected; no active credential collection observed."),
]
AGENTS = [
 ("Triage Agent", "Classifies incoming reports and prioritizes severity", "Online", "1.2s", "94%"),
 ("Investigation Agent", "Reviews sender, links, headers and message indicators", "Online", "3.8s", "91%"),
 ("Risk Reviewer Agent", "Checks confidence, impact and policy thresholds", "Online", "1.6s", "96%"),
 ("Response Agent", "Prepares containment actions for human approval", "Standby", "2.1s", "89%"),
]

def connect():
    conn = sqlite3.connect(DB); conn.row_factory = sqlite3.Row; return conn

def init_db():
    with connect() as c:
        c.execute('''CREATE TABLE IF NOT EXISTS incidents (id TEXT PRIMARY KEY, subject TEXT, sender TEXT, severity TEXT, status TEXT, created_at TEXT, findings TEXT, action TEXT DEFAULT 'None')''')
        c.execute('''CREATE TABLE IF NOT EXISTS approvals (id INTEGER PRIMARY KEY AUTOINCREMENT, incident_id TEXT, action TEXT, rationale TEXT, status TEXT DEFAULT 'Pending', created_at TEXT)''')
        c.execute('''CREATE TABLE IF NOT EXISTS audit (id INTEGER PRIMARY KEY AUTOINCREMENT, actor TEXT, event TEXT, incident_id TEXT, created_at TEXT)''')
        if c.execute('SELECT COUNT(*) FROM incidents').fetchone()[0] == 0:
            c.executemany('INSERT INTO incidents(id,subject,sender,severity,status,created_at,findings) VALUES(?,?,?,?,?,?,?)', INCIDENT_SEED)
            c.executemany('INSERT INTO audit(actor,event,incident_id,created_at) VALUES(?,?,?,?)', [
                ('System', 'Demo workspace initialized', '—', '2026-10-30 08:00'),
                ('Triage Agent', 'Prioritized INC-1047 as Critical', 'INC-1047', '2026-10-30 08:55'),
                ('Investigation Agent', 'Flagged sender-domain mismatch', 'INC-1048', '2026-10-30 09:42')])
            c.execute("INSERT INTO approvals(incident_id,action,rationale,status,created_at) VALUES(?,?,?,?,?)", ('INC-1047','Quarantine message','Critical risk score; suspicious attachment and reply-to mismatch.','Pending','2026-10-30 09:02'))

def log(actor, event, incident_id):
    with connect() as c: c.execute('INSERT INTO audit(actor,event,incident_id,created_at) VALUES(?,?,?,?)',(actor,event,incident_id,datetime.now().strftime('%Y-%m-%d %H:%M:%S')))

@app.context_processor
def common(): return {'pending_count': len(get_pending()), 'now_year': datetime.now().year}

def get_pending():
    with connect() as c: return c.execute("SELECT * FROM approvals WHERE status='Pending' ORDER BY id DESC").fetchall()

@app.route('/')
def dashboard():
    with connect() as c:
        incidents = c.execute('SELECT * FROM incidents ORDER BY created_at DESC').fetchall()
        audits = c.execute('SELECT * FROM audit ORDER BY id DESC LIMIT 6').fetchall()
        counts = {r['severity']: r['n'] for r in c.execute('SELECT severity, COUNT(*) n FROM incidents GROUP BY severity').fetchall()}
        active = c.execute("SELECT COUNT(*) FROM incidents WHERE status NOT IN ('Resolved','Contained')").fetchone()[0]
    return render_template('index.html', incidents=incidents[:5], audits=audits, counts=counts, active=active, agent_count=len(AGENTS))

@app.route('/incidents')
def incidents():
    q=request.args.get('q','').strip(); severity=request.args.get('severity',''); status=request.args.get('status','')
    sql='SELECT * FROM incidents WHERE 1=1'; args=[]
    if q: sql += ' AND (id LIKE ? OR subject LIKE ? OR sender LIKE ?)'; args += [f'%{q}%']*3
    if severity: sql += ' AND severity=?'; args.append(severity)
    if status: sql += ' AND status=?'; args.append(status)
    sql += ' ORDER BY created_at DESC'
    with connect() as c: rows=c.execute(sql,args).fetchall()
    return render_template('incidents.html', incidents=rows, q=q, severity=severity, status=status)

@app.route('/incident/<incident_id>')
def incident_detail(incident_id):
    with connect() as c:
        incident=c.execute('SELECT * FROM incidents WHERE id=?',(incident_id,)).fetchone()
        related=c.execute('SELECT * FROM audit WHERE incident_id=? ORDER BY id DESC',(incident_id,)).fetchall()
    if not incident: flash('Incident not found.','error'); return redirect(url_for('incidents'))
    return render_template('incident-detail.html', incident=incident, related=related)

@app.route('/agents')
def agents(): return render_template('agents.html', agents=AGENTS)

@app.route('/approvals')
def approvals():
    with connect() as c: rows=c.execute('SELECT * FROM approvals ORDER BY CASE status WHEN \'Pending\' THEN 0 ELSE 1 END, id DESC').fetchall()
    return render_template('approvals.html', approvals=rows)

@app.post('/approval/<int:approval_id>/<decision>')
def approval_action(approval_id, decision):
    if decision not in ('approve','reject'): return redirect(url_for('approvals'))
    state='Approved' if decision=='approve' else 'Rejected'
    with connect() as c:
        row=c.execute('SELECT * FROM approvals WHERE id=?',(approval_id,)).fetchone()
        if row and row['status']=='Pending':
            c.execute('UPDATE approvals SET status=? WHERE id=?',(state,approval_id))
            if decision=='approve': c.execute("UPDATE incidents SET status='Contained', action=? WHERE id=?",(row['action'],row['incident_id']))
            log('Human Reviewer', f"{state} response action: {row['action']}", row['incident_id'])
    flash(f'Review recorded: {state.lower()}.','success'); return redirect(url_for('approvals'))

@app.route('/audit')
def audit():
    with connect() as c: rows=c.execute('SELECT * FROM audit ORDER BY id DESC').fetchall()
    return render_template('audit.html', entries=rows)

@app.route('/export.csv')
def export_csv():
    with connect() as c: rows=c.execute('SELECT id,subject,sender,severity,status,created_at,findings,action FROM incidents ORDER BY created_at DESC').fetchall()
    out=io.StringIO(); w=csv.writer(out); w.writerow(['ID','Subject','Sender','Severity','Status','Created','Findings','Action'])
    for r in rows: w.writerow(list(r))
    return Response(out.getvalue(), mimetype='text/csv', headers={'Content-Disposition':'attachment; filename=sentinelai-incidents.csv'})

if __name__ == '__main__':
    init_db()
    app.run(debug=True)
else:
    init_db()
