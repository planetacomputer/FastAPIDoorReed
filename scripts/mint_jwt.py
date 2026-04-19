#!/usr/bin/env python3
"""
Mint a simple HS256 JWT for local testing.

Usage:
  export JWT_SECRET_KEY="your-jwt-secret"
  python3 scripts/mint_jwt.py --sub tester

You can also pass --secret to override the env var.
"""
import argparse
import base64
import hashlib
import hmac
import json
import time
import os


def b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def make_token(secret: bytes, sub: str = "tester", exp: int | None = None) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    if exp is None:
        exp = int(time.time()) + 3600
    payload = {"sub": sub, "exp": exp}
    header_b = json.dumps(header, separators=(",", ":")).encode("utf-8")
    payload_b = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    segments = [b64url_encode(header_b), b64url_encode(payload_b)]
    signing_input = (".".join(segments)).encode("ascii")
    sig = hmac.new(secret, signing_input, hashlib.sha256).digest()
    segments.append(b64url_encode(sig))
    return ".".join(segments)


def main() -> None:
    p = argparse.ArgumentParser(description="Mint a HS256 JWT for local testing")
    p.add_argument("--secret", help="Secret to sign the token. If omitted read JWT_SECRET_KEY env var.")
    p.add_argument("--sub", default="tester", help="sub claim (subject)")
    p.add_argument("--exp", type=int, help="exp claim as unix timestamp (optional)")
    args = p.parse_args()

    secret = args.secret.encode("utf-8") if args.secret else os.environ.get("JWT_SECRET_KEY", "").encode("utf-8")
    if not secret or secret == b"":
        print("Error: JWT secret not provided. Set JWT_SECRET_KEY env var or pass --secret.")
        raise SystemExit(2)

    token = make_token(secret, sub=args.sub, exp=args.exp)
    print(token)


if __name__ == "__main__":
    main()
