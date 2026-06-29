"""
web_app.py  —  Goldmine Lead Scraper Pro (SaaS Edition)
============================================================
Professional lead generation tool with subscription tiers.
"""

import os, sys, json, csv, time, queue, threading, io, shutil
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

PLAYWRIGHT_BROWSERS_DIR = os.path.join(
    os.environ.get("LOCALAPPDATA", os.path.expanduser("~")),
    "ms-playwright",
)
os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", PLAYWRIGHT_BROWSERS_DIR)

from flask import Flask, render_template, request, jsonify, Response, send_file, session, redirect, url_for

app = Flask(__name__)
if getattr(sys, 'frozen', False):
    # Running in a bundle (EXE)
    template_folder = os.path.join(sys._MEIPASS, 'templates')
    app.template_folder = template_folder
app.config.update(
    SECRET_KEY="goldmine-saas-website-2026-whatsapp-923330282889",
    SESSION_COOKIE_SAMESITE="None",
    SESSION_COOKIE_SECURE=True,
)

# ── Paths ────────────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STORAGE_DIR = os.path.join(BASE_DIR, "goldmine_data")
HISTORY_FILE = os.path.join(STORAGE_DIR, "history.json")
LIMITS_FILE = os.path.join(STORAGE_DIR, "guest_limits.json")

if not os.path.exists(STORAGE_DIR):
    os.makedirs(STORAGE_DIR)
if not os.path.exists(HISTORY_FILE):
    with open(HISTORY_FILE, "w") as f: json.dump({}, f)

# ── Accounts Database ────────────────────────────────────────────────────────
ACCOUNTS = {
    "townywalay": {
        "password": "rolzah",
        "tier": "Yearly Premium",
        "expiry": "2027-06-29",
        "description": "Yearly Plan - Unlimited Tool Access"
    },
    "Anasbhai": {
        "password": "scrapeanas",
        "tier": "Monthly Premium",
        "expiry": "2026-07-29",  # Expires after 1 month from June 29, 2026
        "description": "Monthly Plan - Expires July 29, 2026"
    }
}

# ── Imports ──────────────────────────────────────────────────────────────────
import subprocess

def ensure_browser():
    """Ensure playwright chromium is installed for the client."""
    os.makedirs(PLAYWRIGHT_BROWSERS_DIR, exist_ok=True)
    os.environ["PLAYWRIGHT_BROWSERS_PATH"] = PLAYWRIGHT_BROWSERS_DIR
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            browser.close()
            print("Browser engine: OK")
    except Exception as e:
        print(f"Browser engine missing. Installing dependencies... (This happens only once)")
        try:
            from playwright.__main__ import main
            import sys
            sys.argv = ["playwright", "install", "chromium"]
            try:
                main()
            except SystemExit:
                pass
            print("Browser installation successful!")
        except Exception as err:
            print(f"Auto-repair failed: {err}")

# Run browser check
ensure_browser()

try:
    from scraper2 import scrape, save_to_csv
    SCRAPER_OK = True
except ImportError:
    SCRAPER_OK = False

try:
    from email_finder_tab import scrape_email_from_website
    EMAIL_OK = True
except ImportError:
    EMAIL_OK = False

# ── Guest Limit Helper ───────────────────────────────────────────────────────
def check_and_update_guest_limit(ip, count_to_add=0):
    """
    Tracks and enforces the 20 leads/day limit for guest users.
    Returns (is_allowed, remaining_quota, error_message).
    """
    today = datetime.now().strftime("%Y-%m-%d")
    try:
        if os.path.exists(LIMITS_FILE):
            with open(LIMITS_FILE, "r") as f:
                data = json.load(f)
        else:
            data = {}
    except Exception:
        data = {}

    if today not in data:
        data = {today: {}}

    current_count = data[today].get(ip, 0)

    if current_count >= 20:
        return False, 0, "Daily limit of 20 leads reached for guest users. Contact WhatsApp +92 3330282889 to upgrade to Premium!"

    if count_to_add > 0:
        current_count += count_to_add
        data[today][ip] = current_count
        try:
            with open(LIMITS_FILE, "w") as f:
                json.dump(data, f)
        except Exception as e:
            print(f"Error saving limits: {e}")

    remaining = max(0, 20 - current_count)
    return True, remaining, ""

# ── Shared job state (Volatile) ──────────────────────────────────────────────
job = {
    "scrape_running":  False,
    "email_running":   False,
    "stop_flag":       False,
    "results":         [],
    "csv_path":        "",
    "csv_name":        "",
    "scrape_queue":    queue.Queue(),
    "email_queue":     queue.Queue(),
}

def _clear_q(q: queue.Queue):
    while not q.empty():
        try: q.get_nowait()
        except: break

# ── History Helpers ─────────────────────────────────────────────────────────
def save_to_history(username, name, path, count):
    if not username or username == "Guest": return
    try:
        if not os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE, "w") as f: json.dump({}, f)
            
        with open(HISTORY_FILE, "r") as f:
            hist = json.load(f)
        
        if username not in hist: hist[username] = []
        
        hist[username].insert(0, {
            "id": str(int(time.time())),
            "name": name,
            "path": os.path.basename(path),
            "count": count,
            "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
        
        with open(HISTORY_FILE, "w") as f:
            json.dump(hist, f, indent=2)
    except Exception as e:
        print(f"History Save Error: {e}")

def get_history(username):
    if not username or username == "Guest": return []
    try:
        with open(HISTORY_FILE, "r") as f:
            hist = json.load(f)
        return hist.get(username, [])
    except: return []

# ── Routes ───────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    if session.get("username"):
        return redirect(url_for("dashboard_view"))
    return render_template("index.html")

@app.route("/dashboard")
def dashboard_view():
    if not session.get("username"):
        return redirect(url_for("index"))
    return render_template("app.html")

@app.route("/api/login", methods=["POST"])
def login():
    data = request.json or {}
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()
    
    if not username or not password:
        return jsonify({"valid": False, "error": "Username and password required"})
        
    user = ACCOUNTS.get(username)
    if user and user["password"] == password:
        # Check Expiry
        expiry_date = datetime.strptime(user["expiry"], "%Y-%m-%d").date()
        if datetime.now().date() > expiry_date:
            return jsonify({"valid": False, "error": f"Subscription expired on {user['expiry']}. Please contact WhatsApp +92 3330282889 to renew."})
            
        session["logged_in"] = True
        session["username"] = username
        session["tier"] = user["tier"]
        session["expiry"] = user["expiry"]
        return jsonify({"valid": True, "tier": user["tier"], "redirect": url_for("dashboard_view")})
        
    return jsonify({"valid": False, "error": "Invalid username or password"})

@app.route("/api/guest", methods=["POST"])
def guest_login():
    session["logged_in"] = False
    session["username"] = "Guest"
    session["tier"] = "Free"
    session["expiry"] = "None"
    return jsonify({"valid": True, "redirect": url_for("dashboard_view")})

@app.route("/api/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))

@app.route("/api/session")
def get_session():
    username = session.get("username", "")
    tier = session.get("tier", "Free")
    
    # Calculate guest quota if applicable
    remaining_leads = 20
    if tier == "Free":
        ip = request.headers.get('X-Forwarded-For', request.remote_addr) or "local_guest"
        _, remaining_leads, _ = check_and_update_guest_limit(ip)

    return jsonify({
        "logged_in": bool(username and username != "Guest"),
        "guest_mode": bool(username == "Guest"),
        "username": username,
        "tier": tier,
        "expiry": session.get("expiry", "None"),
        "remaining_leads": remaining_leads
    })

@app.before_request
def handle_options_preflight():
    if request.method == "OPTIONS":
        response = app.make_default_options_response()
        origin = request.headers.get("Origin")
        if origin:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Credentials"] = "true"
        else:
            response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type,Authorization"
        response.headers["Access-Control-Allow-Methods"] = "GET,PUT,POST,DELETE,OPTIONS"
        return response

@app.after_request
def add_header(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    origin = request.headers.get("Origin")
    if origin:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
    else:
        response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type,Authorization"
    response.headers["Access-Control-Allow-Methods"] = "GET,PUT,POST,DELETE,OPTIONS"
    return response

# ── Scraper ──────────────────────────────────────────────────────────────────

@app.route("/api/scrape", methods=["POST"])
def start_scrape():
    if job["scrape_running"]: return jsonify({"error": "Busy"}), 400
    data = request.json or {}
    niche, location = data.get("niche", ""), data.get("location", "")
    if not niche or not location: return jsonify({"error": "Fields required"}), 400
    
    tier = session.get("tier", "Free")
    is_pro = tier in ("Yearly Premium", "Monthly Premium")
    requested_count = int(data.get("count", 50))
    
    ip_addr = request.headers.get('X-Forwarded-For', request.remote_addr) or "local_guest"
    
    # Apply limit rules
    if not is_pro:
        allowed, remaining, msg = check_and_update_guest_limit(ip_addr)
        if not allowed:
            return jsonify({"error": msg}), 403
        count = max(1, min(requested_count, remaining))
    else:
        count = max(1, min(requested_count, 500))
        
    username = session.get("username", "Guest")

    job["scrape_running"] = True
    job["stop_flag"] = False
    job["results"] = []
    _clear_q(job["scrape_queue"])

    def run():
        try:
            def on_progress(current, max_leads, name, info=None):
                info = info or {}
                stage = info.get("stage", "lead")
                if stage == "collect":
                    raw = info.get("raw", 0)
                    raw_total = max(info.get("raw_total", max_leads), 1)
                    pct = min(raw / raw_total * 25, 25)
                elif stage == "checking":
                    checked = info.get("checked", 0)
                    raw_total = max(info.get("raw_total", max_leads), 1)
                    pct = 25 + min(checked / raw_total, 1) * 75
                else:
                    pct = current / max(max_leads, 1) * 100

                if stage != "collect" and current >= max_leads:
                    pct = 100

                job["scrape_queue"].put({
                    "t": "progress",
                    "current": current,
                    "total": max_leads,
                    "name": name,
                    "pct": round(pct, 1),
                    "stage": stage,
                    "checked": info.get("checked", 0),
                    "raw_total": info.get("raw_total", max_leads),
                })
            
            results = scrape(niche, location, count, data.get("filter", "without"), on_progress)
            
            job["scrape_queue"].put({"t": "log", "msg": "Finalizing leads..."})
            for r in results: r["Email"] = ""
            job["results"] = results

            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            fname = f"Goldmine_{niche.replace(' ','_')}_{ts}.csv"
            path = os.path.join(STORAGE_DIR, fname)
            save_to_csv(results, path)
            job["csv_path"] = path
            job["csv_name"] = fname
            
            save_to_history(username, f"{niche} in {location}", path, len(results))
            
            # If guest, update their daily usage count
            if not is_pro:
                check_and_update_guest_limit(ip_addr, len(results))
            
            job["scrape_queue"].put({"t": "done", "count": len(results)})
        except Exception as e: 
            print(f"Scrape Thread Error: {e}")
            job["scrape_queue"].put({"t": "error", "msg": str(e)})
        finally: 
            job["scrape_running"] = False

    threading.Thread(target=run, daemon=True).start()
    return jsonify({"status": "started"})

# ── Email Enrichment ────────────────────────────────────────────────────────

@app.route("/api/emails/find", methods=["POST"])
def find_emails():
    tier = session.get("tier", "Free")
    is_pro = tier in ("Yearly Premium", "Monthly Premium")
    
    if not is_pro:
        return jsonify({"error": "Email Enrichment is locked for Guest users. Please contact WhatsApp +92 3330282889 to upgrade to Premium."}), 403
        
    if job["email_running"] or not job["results"]: 
        return jsonify({"error": "Invalid state or empty results"}), 400
        
    job["email_running"] = True
    _clear_q(job["email_queue"])

    def run():
        try:
            results = job["results"]
            found = 0
            
            for i, r in enumerate(results):
                site = r.get("Website", "").strip()
                if not site: continue
                job["email_queue"].put({"t": "checking", "name": r.get("Name")})
                email = scrape_email_from_website(site)
                if email:
                    r["Email"] = email
                    found += 1
                pct = round((i+1)/len(results)*100, 1)
                job["email_queue"].put({"t": "update", "found": found, "pct": pct})
            
            if job["csv_path"]:
                path = job["csv_path"].replace(".csv", "_Enriched.csv")
                with open(path, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.DictWriter(f, fieldnames=results[0].keys())
                    writer.writeheader()
                    writer.writerows(results)
                job["csv_path"] = path
            
            job["email_queue"].put({"t": "done"})
        except Exception as e: 
            print(f"Email Thread Error: {e}")
            job["email_queue"].put({"t": "error", "msg": str(e)})
        finally: 
            job["email_running"] = False

    threading.Thread(target=run, daemon=True).start()
    return jsonify({"status": "started"})

# ── API ENDPOINTS ──────────────────────────────────────────────────────────

@app.route("/api/history")
def api_history():
    username = session.get("username")
    return jsonify(get_history(username))

@app.route("/api/results")
def get_results():
    return jsonify(job.get("results", []))

@app.route("/api/download/csv")
def download_csv():
    path = job.get("csv_path")
    if path and os.path.exists(path):
        return send_file(path, as_attachment=True)
    return "Not found", 404

@app.route("/api/download/history/<id>")
def download_history(id):
    username = session.get("username")
    hist = get_history(username)
    item = next((x for x in hist if x["id"] == id), None)
    if item:
        path = os.path.join(STORAGE_DIR, item["path"])
        if os.path.exists(path): return send_file(path, as_attachment=True)
    return "Not found", 404

@app.route("/api/scrape/stream")
def scrape_stream():
    def gen():
        while True:
            try:
                msg = job["scrape_queue"].get(timeout=30)
                yield f"data: {json.dumps(msg)}\n\n"
                if msg["t"] in ("done", "error"): break
            except queue.Empty:
                yield f"data: {json.dumps({'t':'ping'})}\n\n"
    return Response(gen(), mimetype="text/event-stream")

@app.route("/api/emails/stream")
def email_stream():
    def gen():
        while True:
            try:
                msg = job["email_queue"].get(timeout=30)
                yield f"data: {json.dumps(msg)}\n\n"
                if msg["t"] in ("done", "error"): break
            except queue.Empty:
                yield f"data: {json.dumps({'t':'ping'})}\n\n"
    return Response(gen(), mimetype="text/event-stream")

# ── Main Entry ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 8888))
    # Parse port parameter if provided
    for i, arg in enumerate(sys.argv):
        if arg == "--port" and i + 1 < len(sys.argv):
            try:
                port = int(sys.argv[i+1])
            except ValueError:
                pass
            break
            
    if len(sys.argv) > 1 and sys.argv[1] == "--server":
        print(f"Starting public/local web server on port {port}...")
        app.run(host="0.0.0.0", port=port, debug=False)
    else:
        try:
            from flaskwebgui import FlaskUI
            ui = FlaskUI(app=app, server="flask", port=port, width=1280, height=900)
            ui.run()
        except ImportError:
            print(f"FlaskUI not installed. Starting server mode on port {port}...")
            app.run(host="0.0.0.0", port=port, debug=True)
