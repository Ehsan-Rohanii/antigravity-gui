# 🚀 Antigravity Web UI (AGY Web Studio)

A sleek, lightweight, and modern Web GUI for the **Google Antigravity CLI (`agy`)**. It provides an interactive, full-featured paired programming & chat interface directly connected to your local Antigravity Language Server and daemon.

---

## ✨ Features

- **⚡ Zero Heavy Dependencies**: Pure Python backend using standard `http.server` & standard libraries. Fast, secure, and instant startup.
- **💬 Real-Time Streaming**: Live token-by-token response streaming with terminal ANSI decoding and real-time UI rendering.
- **🧠 Thought & Reasoning Visualization**: Dedicated collapsible collapsible cards for AI thinking processes and internal reasoning logs (`<thinking>` and `> thought`).
- **🗂️ Session & History Management**:
  - Full multi-conversation persistence directly linked to Antigravity CLI's local sessions (`~/.gemini/antigravity-cli`).
  - Automatic & AI-powered intelligent chat renaming (using fast & cost-effective Flash models).
  - Clean conversation search, rename, and deletion with confirmation safeguards.
- **🎛️ Dynamic Model & Reasoning Effort Controls**:
  - Select between **Gemini 3.8 Flash / Flash-Low**, **Gemini 3.1 Pro**, **Claude Sonnet 4.6 / Opus**, **GPT-OSS 120B**, etc.
  - Adaptive reasoning effort levels (`low`, `medium`, `high`) mapped dynamically per model.
- **🌐 Built-in Proxy Support**:
  - Direct SOCKS5 / HTTP proxy integration with automatic tunnel health & latency checks (`/api/test_proxy`).
- **📊 Quota & Account Dashboard**:
  - Real-time rate limits, quota utilization, and account tier monitor (`/usage`).
- **🌍 Bilingual & Native Typography**:
  - Full support for **Persian (RTL)** and **English (LTR)**.
  - Direction auto-detection per message with bundled high-legibility IranianSans typography.
- **📱 Responsive Glassmorphic UI**:
  - Modern dark mode layout optimized for both desktop and mobile devices.

---

## 🛠️ Architecture

```mermaid
graph TD
    User([Browser Client / Mobile]) <-->|HTTP / Streaming SSE| WebServer[Python Web Server (main.py)]
    WebServer <-->|Subprocess / CLI| AGY[Antigravity CLI (agy)]
    AGY <-->|gRPC / IPC| LS[Antigravity Language Server]
    WebServer <-->|Read / Write| Storage[(Local Storage ~/.gemini/antigravity-cli)]
```

---

## 📋 Prerequisites

- **Python 3.10+**
- **Antigravity CLI (`agy`)** installed and authenticated on your system.

---

## 🚀 Quick Start

### 1. Clone & Setup
```bash
git clone https://github.com/your-username/antigravity-web-ui.git
cd antigravity-web-ui
```

### 2. Run the Server
Ensure your Antigravity environment variables (if running alongside an active Language Server session) are exported:

```bash
# Optional: export active Language Server credentials if interacting with existing daemon
export ANTIGRAVITY_LS_ADDRESS=$ANTIGRAVITY_LS_ADDRESS
export ANTIGRAVITY_CSRF_TOKEN=$ANTIGRAVITY_CSRF_TOKEN

# Start the Web Studio
python3 main.py
```

### 3. Open in Browser
Open your browser and navigate to:
```
http://localhost:8000
```
*(Or access via your local network IP from other devices on the same LAN).*

---

## ⚙️ Configuration & Settings

Settings are persisted in `ui_settings.json` automatically:
- **Language**: Persian (`fa`) / English (`en`).
- **Default Model**: Select preferred default model.
- **Reasoning Effort**: Select reasoning effort intensity.
- **Proxy Configuration**: Configure SOCKS5 (`socks5://127.0.0.1:10808`) or HTTP proxy for restricted network environments.

---

## 📁 Project Structure

```
├── fonts/
│   └── IranianSans.ttf      # Bundled Persian typography
├── index.html               # Single-page modern UI (HTML/CSS/JS)
├── main.py                  # Lightweight asynchronous backend server
├── ui_settings.json         # User preferences and proxy configuration
└── README.md                # Project documentation
```

---

## 🛡️ License

Distributed under the **MIT License**. See `LICENSE` for more information.
