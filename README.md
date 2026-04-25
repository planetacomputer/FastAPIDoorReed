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

## 🔐 Authentication for POST /door

The `/door` endpoint is protected with an HS256-signed JWT. The application verifies
the token using the secret provided in the `JWT_SECRET_KEY` environment variable
(it will fall back to `TELEGRAM_TOKEN` only as a convenience). If you don't set a
secret the app will still run, but tokens signed with a real secret won't validate.

How tokens are validated
- The app expects a Bearer token in the `Authorization` header: `Authorization: Bearer <token>`.
- Only `HS256` is supported by the built-in verifier. The code checks the signature
  and optional `exp` (expiry) claim.

Generate a token (minimal, no external deps)

Here's a small Python snippet that creates a compatible HS256 token (for testing):

```python
import base64, hmac, hashlib, json, time

def b64u(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()

header = {"alg": "HS256", "typ": "JWT"}
payload = {"sub": "tester", "exp": int(time.time()) + 3600}
secret = b"your-jwt-secret"

hdr_b64 = b64u(json.dumps(header).encode())
pl_b64 = b64u(json.dumps(payload).encode())
sign = hmac.new(secret, f"{hdr_b64}.{pl_b64}".encode(), hashlib.sha256).digest()
sig_b64 = b64u(sign)
token = f"{hdr_b64}.{pl_b64}.{sig_b64}"
print(token)
```

Using PyJWT (recommended for production)

If you prefer a tested library, install `PyJWT` and run:

```bash
pip install PyJWT
python -c "import jwt, time; print(jwt.encode({'sub':'tester','exp':int(time.time())+3600}, 'your-jwt-secret', algorithm='HS256'))"
```

Take 'certificats intermédiaires' from AD.

Call the endpoint (curl example)

```bash
TOKEN="<paste-your-token-here>"
curl -X POST http://127.0.0.1:8000/door \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"device_id":"limpieza","state":"|0|1","rssi":-78,"snr":6,"battery":3.7}'
```

Notes & security
- Use a strong random secret for `JWT_SECRET_KEY` in production and set it via environment variables (not in source).
- Consider rotating secrets and using short token lifetimes (set `exp` accordingly).
- For full JWT support (multiple algorithms, key management, claims validation), use a library such as `PyJWT` or `python-jose`.


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

## 📄 License

MIT License  

---

## 👨‍💻 Author

Developed by [planetacomputer](https://github.com/planetacomputer)

---
