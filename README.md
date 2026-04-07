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

