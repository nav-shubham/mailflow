import os
import re
import json
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer
import socketserver
from datetime import datetime

# Import email pipeline module
try:
    from . import pipeline
except ImportError:
    import pipeline

# App State
app_state = {
    "status": "idle",           # "idle", "scanning", "completed", "error"
    "total_accounts": 0,
    "processed_accounts": 0,
    "current_status_msg": "",
    "emails": [],
    "last_scanned_at": None,
    "error_message": ""
}

# Load last scan from DB on startup if present
try:
    last_emails, last_time = pipeline.get_last_scan_emails()
    if last_emails:
        app_state["emails"] = last_emails
        app_state["last_scanned_at"] = last_time
except Exception as e:
    print(f"Error loading last scan from DB on startup: {e}")

# Background scan worker
def bg_scan_worker():
    global app_state
    app_state["status"] = "scanning"
    app_state["processed_accounts"] = 0
    app_state["total_accounts"] = 0
    app_state["current_status_msg"] = "Initializing..."
    app_state["error_message"] = ""
    app_state["emails"] = []
    
    config = pipeline.load_config()
    
    # Progress callback for pipeline
    def progress_callback(msg, processed, total):
        app_state["current_status_msg"] = msg
        app_state["processed_accounts"] = processed
        app_state["total_accounts"] = total
        
    try:
        # Determine total accounts
        total = 0
        if config["email_1"]: total += 1
        if config["email_2"]: total += 1
        app_state["total_accounts"] = total
        
        if total == 0:
            app_state["status"] = "error"
            app_state["error_message"] = "No email accounts are configured in settings."
            return
            
        # Run scan pipeline
        results = pipeline.scan_emails_pipeline(
            hours_lookback=config["lookback_hours"],
            progress_callback=progress_callback
        )
        
        # Save to DB
        scan_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        pipeline.save_scanned_emails(results, scan_time)
        
        # Update state
        app_state["emails"] = results
        app_state["last_scanned_at"] = scan_time
        app_state["status"] = "completed"
        app_state["current_status_msg"] = f"Finished! Found {len(results)} emails."
        
    except Exception as e:
        app_state["status"] = "error"
        app_state["error_message"] = str(e)
        app_state["current_status_msg"] = f"Failed with error: {e}"

# Server setup
class ThreadedHTTPServer(socketserver.ThreadingMixIn, HTTPServer):
    daemon_threads = True

class WebServerHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Suppress logging spam in console
        pass
        
    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        
        # ROUTE: GET /api/config
        if path == "/api/config":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            config = pipeline.load_config()
            self.wfile.write(json.dumps(config).encode())
            
        # ROUTE: GET /api/emails/status
        elif path == "/api/emails/status":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(app_state).encode())
            
        # SERVE STATIC FILES
        else:
            self.serve_static(path)

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        
        # Parse JSON payload
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length)
        try:
            body = json.loads(post_data.decode()) if post_data else {}
        except Exception:
            body = {}

        # ROUTE: POST /api/config
        if path == "/api/config":
            try:
                pipeline.save_config(body)
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"status": "success", "message": "Config updated successfully."}).encode())
            except Exception as e:
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"status": "error", "message": str(e)}).encode())
            
        # ROUTE: POST /api/emails/scan
        elif path == "/api/emails/scan":
            if app_state["status"] == "scanning":
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"status": "error", "message": "Scan already in progress."}).encode())
                return
                
            # Start background thread
            thread = threading.Thread(target=bg_scan_worker)
            thread.daemon = True
            thread.start()
            
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "success", "message": "Scan started."}).encode())
            
        # ROUTE: POST /api/emails/export
        elif path == "/api/emails/export":
            # Generate Excel report using current list (or loaded from DB if empty)
            emails = app_state["emails"]
            if not emails:
                emails, _ = pipeline.get_last_scan_emails()
                
            if not emails:
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"status": "error", "message": "No email data available to export. Run a scan first."}).encode())
                return
                
            try:
                out_path = pipeline.generate_excel_report(emails)
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({
                    "status": "success", 
                    "message": "Excel report updated.",
                    "path": out_path
                }).encode())
            except Exception as e:
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"status": "error", "message": str(e)}).encode())
        else:
            self.send_response(404)
            self.end_headers()

    def serve_static(self, path):
        static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
        
        # Default route to index.html
        if path == "/" or path == "":
            file_path = os.path.join(static_dir, "index.html")
        else:
            clean_path = path.lstrip("/")
            file_path = os.path.join(static_dir, clean_path)
            
        # Prevent Directory Traversal
        resolved_path = os.path.abspath(file_path)
        if not resolved_path.startswith(os.path.abspath(static_dir)):
            self.send_response(403)
            self.end_headers()
            self.wfile.write(b"403 Forbidden")
            return
            
        if not os.path.exists(resolved_path) or os.path.isdir(resolved_path):
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"404 Not Found")
            return
            
        self.send_response(200)
        
        # Set Content-Type
        if resolved_path.endswith(".html"):
            self.send_header("Content-Type", "text/html")
        elif resolved_path.endswith(".css"):
            self.send_header("Content-Type", "text/css")
        elif resolved_path.endswith(".js"):
            self.send_header("Content-Type", "application/javascript")
        elif resolved_path.endswith(".png"):
            self.send_header("Content-Type", "image/png")
        elif resolved_path.endswith(".jpg") or resolved_path.endswith(".jpeg"):
            self.send_header("Content-Type", "image/jpeg")
        elif resolved_path.endswith(".svg"):
            self.send_header("Content-Type", "image/svg+xml")
        else:
            self.send_header("Content-Type", "application/octet-stream")
            
        self.end_headers()
        
        with open(resolved_path, "rb") as f:
            self.wfile.write(f.read())

def run_server(port=8080):
    server = ThreadedHTTPServer(('127.0.0.1', port), WebServerHandler)
    print(f"📧 MailFlow Email Dashboard running at http://127.0.0.1:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server...")
        server.shutdown()

if __name__ == "__main__":
    run_server()
