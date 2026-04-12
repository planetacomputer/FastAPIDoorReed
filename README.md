# 🚪 FastAPI Door Reed

A simple **FastAPI-based web application** to monitor and visualize the state of a **door reed sensor** (open/closed) in real time.

This project is designed for **IoT / embedded systems scenarios**, where a sensor (e.g. Lora ESP32) sends door state events to a backend API and displays them through a web interface.

---

## ✨ Features

- 📡 REST API built with FastAPI  
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
├── app/
│   ├── main.py          # FastAPI entry point
│   ├── routes/          # API endpoints
│   ├── templates/       # Jinja2 templates
│   ├── static/          # CSS / JS / assets
│   └── models/          # Data models
│
├── requirements.txt
├── README.md
├── dbconfig.py
├── venv/
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
uvicorn app.main:app --reload
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

- WebSocket real-time updates  
- Authentication / security  
- Database persistence (SQLite / PostgreSQL)  
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



## 📄 License

MIT License  

---

## 👨‍💻 Author

Developed by [planetacomputer](https://github.com/planetacomputer)
