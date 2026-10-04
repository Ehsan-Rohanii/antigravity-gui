import http.server
import json
import os
import pty
import select
import shutil
import subprocess
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

# ---------------------------------------------------------
# Load .env configuration
# ---------------------------------------------------------
def load_env(filepath=".env"):
    env_path = Path(__file__).parent / filepath
    if env_path.exists():
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    k, v = line.split("=", 1)
                    os.environ[k.strip()] = v.strip()

load_env()

HOST = os.environ.get("HOST", "127.0.0.1")
PORT = int(os.environ.get("PORT", "8000"))

AG_HOME_PATH_STR = os.environ.get("AGY_HOME", str(Path.home() / ".gemini" / "antigravity-cli"))
AG_HOME = Path(AG_HOME_PATH_STR)
BRAIN_DIR = AG_HOME / "brain"
HISTORY_FILE = AG_HOME / "history.jsonl"
TITLES_FILE = AG_HOME / "custom_titles.json"

cli_bin_env = os.environ.get("CLI_BIN", "agy")
CLI_BIN = cli_bin_env if shutil.which(cli_bin_env) else "antigravity"

# ---------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------
def get_cli_version():
    try:
        proc = subprocess.run([CLI_BIN, "--version"], capture_output=True, text=True, timeout=5)
        return proc.stdout.strip()
    except Exception:
        return "Unknown"

def get_usage_data():
    usage = {
        "gemini_weekly": "0", "gemini_weekly_reset": "",
        "gemini_5h": "0", "gemini_5h_reset": "",
        "claude_weekly": "0", "claude_weekly_reset": "",
        "claude_5h": "0", "claude_5h_reset": ""
    }
    
    # Try Fast RPC first
    ls_address = os.environ.get("ANTIGRAVITY_LS_ADDRESS")
    csrf_token = os.environ.get("ANTIGRAVITY_CSRF_TOKEN")
    
    if ls_address and csrf_token:
        try:
            req = urllib.request.Request(
                f"http://{ls_address}/exa.language_server_pb.LanguageServerService/RetrieveUserQuotaSummary",
                data=b"{}",
                headers={"Content-Type": "application/json", "x-codeium-csrf-token": csrf_token}
            )
            with urllib.request.urlopen(req, timeout=1) as response:
                res_data = json.loads(response.read().decode())
                groups = res_data.get("response", {}).get("groups", [])
                for group in groups:
                    for b in group.get("buckets", []):
                        bid = b.get("bucketId", "")
                        frac = b.get("remainingFraction", 0)
                        pct = str(int(frac * 100))
                        reset = b.get("resetTime", "")
                        
                        if bid == "gemini-weekly":
                            usage["gemini_weekly"] = pct
                            usage["gemini_weekly_reset"] = reset
                        elif bid == "gemini-5h":
                            usage["gemini_5h"] = pct
                            usage["gemini_5h_reset"] = reset
                        elif bid == "3p-weekly":
                            usage["claude_weekly"] = pct
                            usage["claude_weekly_reset"] = reset
                        elif bid == "3p-5h":
                            usage["claude_5h"] = pct
                            usage["claude_5h_reset"] = reset
                return usage
        except Exception as e:
            print("Fast RPC failed:", e)
            pass

    # Fallback to slow CLI
    try:
        proc = subprocess.run([CLI_BIN, "-p", "/usage"], capture_output=True, text=True, timeout=10)
        lines = proc.stdout.strip().split("\n")
        
        for line in lines:
            line = line.strip().replace("\r", "")
            if not line or "Limit Remaining" not in line: continue
            
            group = line[:30].lower()
            period = line[30:55].lower() if len(line) > 55 else ""
            rest = line[55:].strip()
            parts = rest.split()
            percent = parts[0].replace("%", "").strip() if parts else "0"
            reset_time = " ".join(parts[1:]) if len(parts) > 1 else ""
            
            if "gemini" in group and "weekly" in period:
                usage["gemini_weekly"] = percent
                usage["gemini_weekly_reset"] = reset_time
            elif "gemini" in group and "five hour" in period:
                usage["gemini_5h"] = percent
                usage["gemini_5h_reset"] = reset_time
            elif ("claude" in group or "gpt" in group) and "weekly" in period:
                usage["claude_weekly"] = percent
                usage["claude_weekly_reset"] = reset_time
            elif ("claude" in group or "gpt" in group) and "five hour" in period:
                usage["claude_5h"] = percent
                usage["claude_5h_reset"] = reset_time
                    
        return usage
    except Exception:
        return usage

def get_user_info():
    import glob
    log_dir = os.path.join(AG_HOME_PATH_STR, "log")
    email = "Unknown User"
    tier = "PRO"
    
    try:
        log_files = sorted(glob.glob(os.path.join(log_dir, "cli-*.log")), reverse=True)
        for log_file in log_files:
            with open(log_file, "r", encoding="utf-8") as f:
                content = f.read()
                if "authenticated successfully as" in content:
                    lines = content.split("\n")
                    for line in reversed(lines):
                        if "authenticated successfully as" in line:
                            email = line.split("authenticated successfully as ")[-1].strip()
                            break
            if email != "Unknown User":
                break
    except Exception:
        pass
    
    return {"email": email, "tier": tier}

def load_custom_titles():
    if TITLES_FILE.exists():
        try:
            with open(TITLES_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_custom_title(cid, new_title):
    titles = load_custom_titles()
    titles[cid] = new_title
    TITLES_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(TITLES_FILE, "w", encoding="utf-8") as f:
        json.dump(titles, f, ensure_ascii=False, indent=2)

def get_antigravity_sessions():
    custom_titles = load_custom_titles()
    sessions = {}

    if HISTORY_FILE.exists():
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line: continue
                    try:
                        record = json.loads(line)
                        cid = record.get("conversationId")
                        if not cid: continue
                        
                        ts = record.get("timestamp", 0) / 1000.0
                        if cid not in sessions:
                            sessions[cid] = {
                                "id": cid,
                                "title": record.get("display") or "",
                                "timestamp": ts,
                            }
                        else:
                            sessions[cid]["timestamp"] = max(sessions[cid]["timestamp"], ts)
                    except json.JSONDecodeError:
                        continue
        except Exception:
            pass

    if BRAIN_DIR.exists():
        for item in BRAIN_DIR.iterdir():
            if item.is_dir():
                cid = item.name
                mtime = item.stat().st_mtime
                if cid not in sessions:
                    sessions[cid] = {
                        "id": cid,
                        "title": "",
                        "timestamp": mtime,
                    }
                else:
                    sessions[cid]["timestamp"] = max(sessions[cid]["timestamp"], mtime)

    result = []
    for cid, info in sessions.items():
        if cid in custom_titles:
            info["title"] = custom_titles[cid]
        
        if not info["title"] or info["title"] in ["بدون عنوان", "گفت‌وگوی ذخیره‌شده"]:
            first_prompt = get_first_prompt(cid)
            info["title"] = first_prompt.strip() if first_prompt else f"گفتگوی ناشناس ({cid[:6]})"

        result.append(info)

    result.sort(key=lambda x: x["timestamp"], reverse=True)
    return result

def get_first_prompt(cid):
    logs_dir = BRAIN_DIR / cid / ".system_generated" / "logs"
    for filename in ["transcript_full.jsonl", "transcript.jsonl"]:
        p = logs_dir / filename
        if p.exists():
            try:
                with open(p, "r", encoding="utf-8") as f:
                    for line in f:
                        data = json.loads(line)
                        if data.get("type") == "USER_INPUT" or data.get("source") == "USER_EXPLICIT":
                            c = data.get("content")
                            raw_text = ""
                            if isinstance(c, str):
                                raw_text = c.strip()
                            elif isinstance(c, dict) and "text" in c:
                                raw_text = c["text"].strip()
                                
                            if raw_text:
                                lines = [l.strip() for l in raw_text.split('\n') if l.strip()]
                                if lines:
                                    first_line = lines[0]
                                    words = first_line.split()
                                    if len(words) > 6:
                                        first_line = " ".join(words[:6]) + "..."
                                    if len(first_line) > 35:
                                        first_line = first_line[:32] + "..."
                                    return first_line
                            return "چت جدید"
            except Exception:
                pass
    return None

def load_conversation_messages(cid):
    messages = []
    logs_dir = BRAIN_DIR / cid / ".system_generated" / "logs"
    log_file = logs_dir / "transcript_full.jsonl"
    if not log_file.exists():
        log_file = logs_dir / "transcript.jsonl"

    if log_file.exists():
        try:
            with open(log_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line: continue
                    try:
                        record = json.loads(line)
                        src = record.get("source", "")
                        stype = record.get("type", "")
                        
                        # Only show user messages and planner (assistant) text responses
                        if stype not in ["USER_INPUT", "PLANNER_RESPONSE"] and src != "USER_EXPLICIT":
                            continue
                            
                        content = record.get("content")
                        created_at = record.get("created_at", "")

                        text = ""
                        if isinstance(content, str):
                            text = content
                        elif isinstance(content, dict):
                            text = content.get("text", "") or json.dumps(content, ensure_ascii=False)
                        elif isinstance(content, list):
                            texts = []
                            for item in content:
                                if isinstance(item, str): texts.append(item)
                                elif isinstance(item, dict) and "text" in item: texts.append(item["text"])
                            text = "\n".join(texts)

                        if not text: continue

                        role = "user" if (stype == "USER_INPUT" or src == "USER_EXPLICIT") else "assistant"
                        messages.append({"role": role, "text": text, "created_at": created_at})
                    except Exception:
                        continue
        except Exception:
            pass

    return messages

# ---------------------------------------------------------
# HTTP Request Handler
# ---------------------------------------------------------
class AppHandler(http.server.BaseHTTPRequestHandler):
    def _send_json(self, data, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))

    def do_GET(self):
        url = urllib.parse.urlparse(self.path)
        
        # Serve index.html
        if url.path in ["/", "/index.html"]:
            index_path = Path(__file__).parent / "index.html"
            if not index_path.exists():
                self.send_error(404, "index.html not found")
                return
                
            with open(index_path, "r", encoding="utf-8") as f:
                html = f.read()
                
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
            self.send_header("Pragma", "no-cache")
            self.send_header("Expires", "0")
            self.end_headers()
            version = get_cli_version()
            html = html.replace("{{CLI_VERSION}}", version)
            self.wfile.write(html.encode("utf-8"))
            
        # Serve Fonts
        elif url.path.startswith("/fonts/"):
            file_name = os.path.basename(url.path)
            if ".." in file_name or "/" in file_name:
                self.send_error(400)
                return
            file_path = Path(__file__).parent / "fonts" / file_name
            if file_path.exists() and file_path.is_file():
                self.send_response(200)
                if file_name.endswith(".ttf"):
                    self.send_header("Content-Type", "font/ttf")
                self.end_headers()
                with open(file_path, "rb") as f:
                    self.wfile.write(f.read())
            else:
                self.send_error(404)
                
        # API Endpoints
        elif url.path == "/api/user":
            self._send_json(get_user_info())
            
        elif url.path == "/api/usage":
            self._send_json(get_usage_data())
            
        elif url.path == "/api/sessions":
            self._send_json(get_antigravity_sessions())
            
        elif url.path.startswith("/api/sessions/"):
            cid = url.path.split("/")[-1]
            titles = load_custom_titles()
            title = titles.get(cid) or get_first_prompt(cid) or f"Session {cid[:8]}"
            msgs = load_conversation_messages(cid)
            self._send_json({"id": cid, "title": title, "messages": msgs})
            
        else:
            self.send_error(404)

    def do_POST(self):
        url = urllib.parse.urlparse(self.path)
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length).decode("utf-8")) if length > 0 else {}

        if url.path.endswith("/rename"):
            cid = url.path.split("/")[-2]
            new_title = body.get("title", "").strip()
            if new_title:
                save_custom_title(cid, new_title)
                self._send_json({"success": True})
            else:
                self._send_json({"error": "عنوان نامعتبر است"}, 400)

        elif url.path == "/api/chat":
            prompt = body.get("prompt", "").strip()
            session_id = body.get("session_id")
            model = body.get("model")
            effort = body.get("effort")

            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Connection", "close")
            self.end_headers()

            if not session_id:
                session_id = str(uuid.uuid4())

            meta = json.dumps({"session_id": session_id}) + "\n"
            self.wfile.write(meta.encode("utf-8"))
            self.wfile.flush()

            cmd = [CLI_BIN, "--dangerously-skip-permissions", "--conversation", session_id]
            if model and model != "inherit":
                cmd += ["--model", model]
            if effort:
                cmd += ["--effort", effort]
            cmd += ["-p", prompt]

            env = os.environ.copy()
            env["FORCE_COLOR"] = "1"
            
            try:
                master, slave = pty.openpty()
                proc = subprocess.Popen(
                    cmd,
                    stdin=slave,
                    stdout=slave,
                    stderr=slave,
                    close_fds=True,
                    env=env
                )
                os.close(slave)

                while True:
                    r, _, _ = select.select([master], [], [], 0.1)
                    if master in r:
                        try:
                            chunk = os.read(master, 4096)
                            if not chunk:
                                break
                            self.wfile.write(chunk)
                            self.wfile.flush()
                        except OSError:
                            break
                    
                    if proc.poll() is not None:
                        try:
                            while True:
                                r_rem, _, _ = select.select([master], [], [], 0)
                                if master in r_rem:
                                    chunk = os.read(master, 4096)
                                    if not chunk:
                                        break
                                    self.wfile.write(chunk)
                                    self.wfile.flush()
                                else:
                                    break
                        except OSError:
                            pass
                        break

                os.close(master)
                proc.wait()
            except Exception as e:
                self.wfile.write(f"\nError: {str(e)}".encode("utf-8"))
                self.wfile.flush()

# ---------------------------------------------------------
# Server Boot
# ---------------------------------------------------------
if __name__ == "__main__":
    print(f"CLI Detected: {CLI_BIN}")
    print(f"Reading sessions from: {AG_HOME}")
    print(f"Open in browser: http://{HOST}:{PORT}")
    server = http.server.ThreadingHTTPServer((HOST, PORT), AppHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
