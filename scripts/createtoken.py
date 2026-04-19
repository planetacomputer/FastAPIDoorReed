import base64

#!/usr/bin/env python3
"""
Create a JWT using PyJWT. Reads `JWT_SECRET_KEY` from the environment (or .env).

Usage:
  python3 scripts/createtoken.py --sub tester --exp-seconds 3600

This is a small helper for local testing.
"""
import argparse
import time
import os
from dotenv import load_dotenv
import jwt


def main():
    load_dotenv()
    p = argparse.ArgumentParser(description="Create a JWT for testing")
    p.add_argument("--sub", default="tester", help="sub claim (subject)")
    p.add_argument("--exp-seconds", type=int, default=3600, help="seconds until expiry (default 3600)")
    p.add_argument("--secret", help="Override JWT_SECRET_KEY from env")
    args = p.parse_args()

    secret = args.secret or os.environ.get("JWT_SECRET_KEY")
    if not secret:
        print("Error: JWT_SECRET_KEY not set. Set it in the environment or pass --secret")
        raise SystemExit(2)

    now = int(time.time())
    payload = {"sub": args.sub, "exp": now + int(args.exp_seconds)}
    token = jwt.encode(payload, secret, algorithm="HS256")
    # PyJWT returns a string
    print(token)


if __name__ == "__main__":
    main()