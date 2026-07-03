import http.server
import socketserver
import os
import sys
import json
import sqlite3
import subprocess
import urllib.parse
from threading import Thread, Lock
from collections import deque

PORT = 8000

# Dynamic Paths Configuration
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(SCRIPT_DIR) if os.path.basename(SCRIPT_DIR) == "backend" else SCRIPT_DIR

PROFILES_PATH = os.path.join(BASE_DIR, "project_profiles.json")
REPORT_PATH = os.path.join(BASE_DIR, "ats_score_report.md")
DIST_DIR = os.path.join(BASE_DIR, "dashboard", "dist")

# Global Log Buffer for live terminal streaming
MAX_LOG_LINES = 1000
logs_buffer = deque(maxlen=MAX_LOG_LINES)
logs_lock = Lock()

def append_log(line):
    with logs_lock:
        logs_buffer.append(line)

class ThreadingHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True

class APIHandler(http.server.BaseHTTPRequestHandler):
    def send_cors_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_cors_headers()
        self.end_headers()

    def do_GET(self):
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path
        query = urllib.parse.parse_qs(parsed_url.query)

        if path.startswith('/api/'):
            self.handle_api_get(path, query)
        else:
            self.handle_static_serve(path)

    def do_POST(self):
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path

        if path.startswith('/api/'):
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length).decode('utf-8')
            try:
                body = json.loads(post_data) if post_data else {}
            except Exception:
                body = {}
            self.handle_api_post(path, body)
        else:
            self.send_response(404)
            self.end_headers()

    def handle_api_get(self, path, query):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_cors_headers()
        self.end_headers()

        response_data = {"error": "Endpoint not found"}

        if path == '/api/projects':
            if os.path.exists(PROFILES_PATH):
                try:
                    with open(PROFILES_PATH, 'r', encoding='utf-8') as f:
                        response_data = json.load(f)
                except Exception as e:
                    response_data = {"error": f"Error parsing profiles: {e}"}
            else:
                response_data = []

        elif path == '/api/project/ast':
            proj_path = query.get('path', [''])[0]
            db_path = os.path.join(proj_path, ".code-review-graph", "graph.db")
            if os.path.exists(db_path):
                response_data = self.query_ast_graph(db_path)
            else:
                response_data = {"nodes": [], "edges": [], "error": "AST Database not found for this project."}

        elif path == '/api/reviews':
            response_data = self.get_recent_reviews()

        elif path == '/api/score-report':
            if os.path.exists(REPORT_PATH):
                try:
                    with open(REPORT_PATH, 'r', encoding='utf-8') as f:
                        response_data = {"content": f.read()}
                except Exception as e:
                    response_data = {"error": f"Error reading score report: {e}"}
            else:
                response_data = {"content": "# No ATS score report found yet.\nRun scoring to generate a report."}

        elif path == '/api/logs':
            with logs_lock:
                response_data = {"logs": list(logs_buffer)}

        self.wfile.write(json.dumps(response_data).encode('utf-8'))

    def handle_api_post(self, path, body):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_cors_headers()
        self.end_headers()

        response_data = {"status": "error", "message": "Unknown API endpoint"}

        if path == '/api/run-review':
            mode = body.get('mode', 'analyze')
            cmd = ["python3", "backend/multi_project_analyzer.py", "--mode", mode]
            Thread(target=self.run_background_command, args=(cmd,)).start()
            response_data = {"status": "success", "message": f"Started project review in {mode} mode"}

        elif path == '/api/score-resume':
            jd_text = body.get('jd_text', '')
            cmd = ["python3", "backend/ats_scorer.py"]
            if jd_text:
                cmd.extend(["--text", jd_text])
            Thread(target=self.run_background_command, args=(cmd,)).start()
            response_data = {"status": "success", "message": "Triggered resume scoring analysis"}

        elif path == '/api/optimize-resume':
            jd_text = body.get('jd_text', '')
            cmd = ["python3", "backend/ats_optimizer.py"]
            if jd_text:
                cmd.extend(["--text", jd_text])
            Thread(target=self.run_background_command, args=(cmd,)).start()
            response_data = {"status": "success", "message": "Triggered resume keyword optimization"}

        self.wfile.write(json.dumps(response_data).encode('utf-8'))

    def query_ast_graph(self, db_path):
        nodes = []
        edges = []
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Retrieve nodes
            cursor.execute("SELECT id, name, kind, file_path FROM nodes WHERE kind IN ('File', 'Class', 'Function') LIMIT 200;")
            nodes = [{"id": str(r[0]), "name": r[1], "kind": r[2], "file_path": r[3]} for r in cursor.fetchall()]
            
            # Retrieve edges using correct schema mapping (source_qualified -> source, target_qualified -> target)
            cursor.execute("SELECT source_qualified, target_qualified, kind FROM edges LIMIT 300;")
            edges = [{"source": str(r[0]), "target": str(r[1]), "kind": r[2]} for r in cursor.fetchall()]
            
            conn.close()
        except Exception as e:
            print(f"[Server AST Query] SQLite Error: {e}")
        return {"nodes": nodes, "edges": edges}

    def get_recent_reviews(self):
        reviews = []
        try:
            for file in os.listdir(BASE_DIR):
                if file.endswith("_review_findings.md"):
                    file_path = os.path.join(BASE_DIR, file)
                    with open(file_path, 'r', encoding='utf-8') as f:
                        reviews.append({
                            "filename": file,
                            "project": file.replace("_review_findings.md", ""),
                            "mtime": os.path.getmtime(file_path),
                            "content": f.read()
                        })
            # Sort by modified time descending
            reviews.sort(key=lambda x: x["mtime"], reverse=True)
        except Exception as e:
            print(f"[Server Reviews Query] Error: {e}")
        return reviews

    def run_background_command(self, cmd):
        append_log(f"[Server Background] Starting command: {' '.join(cmd)}\n")
        try:
            process = subprocess.Popen(
                cmd,
                cwd=BASE_DIR,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )
            
            for line in iter(process.stdout.readline, ''):
                sys.stdout.write(line)
                sys.stdout.flush()
                append_log(line)
                
            process.stdout.close()
            returncode = process.wait()
            append_log(f"[Server Background] Command finished with exit code: {returncode}\n")
        except Exception as e:
            append_log(f"[Server Background] Error running command: {e}\n")

    def handle_static_serve(self, path):
        clean_path = path.lstrip('/')
        if not clean_path:
            clean_path = 'index.html'

        file_path = os.path.join(DIST_DIR, clean_path)
        
        # Fallback to index.html for React SPA routing
        if not os.path.exists(file_path) or os.path.isdir(file_path):
            file_path = os.path.join(DIST_DIR, 'index.html')

        if not os.path.exists(file_path):
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Static assets not built yet. Please run npm run build in the dashboard directory.")
            return

        # Content Types mapping
        content_type = 'text/html'
        if file_path.endswith('.js'):
            content_type = 'application/javascript'
        elif file_path.endswith('.css'):
            content_type = 'text/css'
        elif file_path.endswith('.json'):
            content_type = 'application/json'
        elif file_path.endswith('.png'):
            content_type = 'image/png'
        elif file_path.endswith('.svg'):
            content_type = 'image/svg+xml'

        try:
            with open(file_path, 'rb') as f:
                data = f.read()
            self.send_response(200)
            self.send_header('Content-Type', content_type)
            self.end_headers()
            self.wfile.write(data)
        except Exception as e:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(f"Server Error: {e}".encode('utf-8'))

def run_server():
    server_address = ('', PORT)
    httpd = ThreadingHTTPServer(server_address, APIHandler)
    print(f"\n[Server] 🌐 Qwen-Antigravity Control Server active at http://localhost:{PORT}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[Server] Shutting down...")
        httpd.server_close()

if __name__ == "__main__":
    run_server()
