import os, base64, json, time, datetime, sys
os.environ["TOKEN"] = "eyJhbGciOiuIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ0ZXN0ZXIiLCJleHAiOjE3NzY1OTI5OTB9.hUx_NDappz0T3OnFdjRcKbu71Ot9-18sCKwkvhFcRNI"
t = os.environ.get("TOKEN")
if not t:
    print("Set $TOKEN first"); sys.exit(2)
try:
    payload_b64 = t.split(".")[1]
    payload_b64 += "=" * (-len(payload_b64) % 4)
    payload = json.loads(base64.urlsafe_b64decode(payload_b64).decode())
    print("Payload:", json.dumps(payload, indent=2))
    if "exp" in payload:
        exp = int(payload["exp"])
        print("exp (unix):", exp)
        print("exp (UTC):", datetime.datetime.utcfromtimestamp(exp).isoformat() + "Z")
        print("now (unix):", int(time.time()))
        print("seconds until expiry:", exp - int(time.time()))
    else:
        print("Token has no exp claim (does not expire by exp check).")
except Exception as e:
    print("Failed to decode token:", e)