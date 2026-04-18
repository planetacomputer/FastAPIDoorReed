# 🚪 FastAPI Door Reed

A simple **FastAPI-based web application** to monitor and visualize the state of a **door reed sensor** (open/closed) in real time.

This project is designed for **IoT / embedded systems scenarios**, where a sensor (e.g. Lora ESP32) sends door state events to a backend API and displays them through a web interface.

---

## ✨ Features

- 📡 REST API built with FastAPI  
- Database MySQL
- 🚪 Track door state (OPEN / CLOSED)  
- 🕒 Timestamped events  
- 🌐 Simple web interface (HTML + Jinja2)  
- 📊 Historical log of sensor activity  
- ⚡ Lightweight and easy to deploy  

---

## 🧱 Tech Stack

- **Backend:** FastAPI  
- **Templating:** Jinja2  
- **Frontend:** HTML + CSS (W3CSS / FontAwesome)  
- **Hardware (optional):** Raspberry Pi + Reed Sensor  
- **Server:** Uvicorn  

---

## 📁 Project Structure

```
FastAPIDoorReed/
│
├── main.py                # FastAPI entry point and routes
├── db.py                  # MySQL helpers and pool
├── dbconfig.py            # DB connection configuration
├── ws.py                  # WebSocket helpers (if used)
├── utils.py               # UI/formatting and helper functions
├── requirements.txt
├── README.md
├── templates/             # Jinja2 templates
│   ├── base.html
│   ├── events.html
│   ├── puerta.html
│   ├── puerta_list.html
│   └── puerta_calendar.html
├── static/                # CSS / fonts / assets
│   ├── styles.css
│   ├── w3.css
│   ├── font-awesome.min.css
│   └── fonts/
├── tests/                 # pytest tests
│   ├── test_db.py
│   └── test_utils.py
└── ...
```

---

## ⚙️ Installation

### 1. Clone the repository

```bash
git clone https://github.com/planetacomputer/FastAPIDoorReed.git
cd FastAPIDoorReed
```

### 2. Create virtual environment

```bash
python -m venv venv
source venv/bin/activate  # Linux / macOS
venv\Scripts\activate     # Windows
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

---

## ▶️ Run the application

```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

or

```bash
uvicorn main:app --reload
```

Open your browser:

```
http://127.0.0.1:8000
```

---

## 🔌 API Endpoints

### POST /event

Send door state updates:

```json
{
  "state": "0"
}
```

---

### GET /

Web interface showing:

- Current door status  
- Event history  
- Timestamps  

---

## 🧪 Example (cURL)

```bash
curl -X POST http://127.0.0.1:8000/event \
     -H "Content-Type: application/json" \
     -d '{"state": "0"}'
```

```bash
curl -F "url=https://7943747593.ngrok-free.app/webhook" https://api.telegram.org/botXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX/setWebhook
```
---

## 🖥️ Hardware Integration (Optional)

You can connect a reed sensor to a Raspberry Pi:

- GPIO detects door open/close  
- Python script sends POST requests to the API  

Example:

```python
import requests

requests.post("http://localhost:8000/event", json={"state": "0"})
```

---

## 🎯 Use Cases

- Smart home door monitoring  
- Classroom or lab door tracking  
- IoT learning projects  
- Event logging systems  

---

## 🚀 Future Improvements

- Authentication / security  
- Notifications (Telegram / email)  
- Dashboard with charts  

---

## 🤝 Contributing

Contributions are welcome!

1. Fork the repo  
2. Create a new branch  
3. Commit your changes  
4. Open a Pull Request  

---

# FastAPIDoorReed

Run the FastAPI server with uvicorn:

```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

# Docker local
```bash
docker run -p 3306:3306 --name doorreed -e MYSQL_ROOT_PASSWORD=my-secret-pw -d mysql:latest
```

# FastAPIDoorReed for SQLite
```bash
uvicorn main_sqlite:app --host 0.0.0.0 --port 8000
```

# Curl insert
```bash
curl -X POST http://localhost:8000/door -H 'Content-Type: application/json' -d '{"device_id":"limpieza","state":"|0|1","rssi":-78,"snr":6,"battery":3.7}'
```



## 🧪 Running tests (pytest)

This project includes a small pytest file at `tests/test_db.py` for basic DB checks (it calls `ensure_schema()` and `fetch_rows_from_db()`). These are integration-style tests and will connect to the MySQL configured in `dbconfig.py`.


```bash
pytest -q
```

Notes and tips:
- The tests may create the `door_events` table if it doesn't exist (idempotent). If you don't want to touch a production DB, point `dbconfig.py` to a test database before running tests.
- If you prefer unit tests that don't touch the DB, I can convert these to use mocks.
- To run a single test file:

```bash
pytest -q tests/test_db.py
```

```bash
python3 -m py_compile dbconfig.py main.py && pytest -q
```

## � Continuous Integration (GitHub Actions)

This repository now includes a GitHub Actions workflow at `.github/workflows/python-app.yml` that runs the test suite on pushes and pull requests targeting `main`.

What it does:
- Sets up Python (3.11 and 3.12 matrix)
- Installs dependencies from `requirements.txt` (if present)
- Runs `pytest -q`

If your tests require a MySQL instance or environment variables, you'll need to update the workflow to provide a service container or mock the DB for CI. I can help add a service-based job (MySQL) if you want the integration tests to run in CI.

To test CI locally, run the same commands used in the workflow:

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
pytest -q
```

## 🟢 Local development with .env

For local development you can provide secrets and environment overrides using a `.env` file (kept out of version control).

1. Copy the example:

```bash
cp .env.example .env
```

2. Edit `.env` and set your `TELEGRAM_TOKEN` (and any DB overrides if needed).

3. Start the app normally; the project uses `python-dotenv` to load `.env` automatically when the app starts:

```bash
uvicorn main:app --reload
```

Note: `.env` is ignored by `.gitignore` so it won't be committed.


## �📄 License

MIT License  

---

## 👨‍💻 Author

Developed by [planetacomputer](https://github.com/planetacomputer)

---
