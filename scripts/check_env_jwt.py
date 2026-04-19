#!/usr/bin/env python3
"""
Check the JWT_SECRET_KEY entry in .env and decode it if it's a JWT token.
"""
import os
import base64
import json
import sys


def load_env(path='.env'):
    if not os.path.exists(path):
        print(f"No {path} file found")
        return {}
    out = {}
    with open(path, 'r', encoding='utf-8') as f:
        for ln in f:
            ln = ln.strip()
            if not ln or ln.startswith('#'):
                continue
            if '=' in ln:
                k, v = ln.split('=', 1)
                out[k.strip()] = v.strip()
    return out


def b64url_decode(s: str) -> bytes:
    s = s.strip()
    rem = len(s) % 4
    if rem:
        s += '=' * (4 - rem)
    return base64.urlsafe_b64decode(s)


def main():
    env = load_env('.env')
    val = env.get('JWT_SECRET_KEY')
    if val is None:
        print('JWT_SECRET_KEY not found in .env')
        raise SystemExit(2)
    print('JWT_SECRET_KEY from .env:')
    print(val)
    # Heuristic: if it contains two dots, assume it's a JWT token
    if val.count('.') == 2:
        print('\nIt looks like a JWT token (contains two dots). Decoding header and payload:')
        try:
            h, p, s = val.split('.')
            header = json.loads(b64url_decode(h).decode('utf-8'))
            payload = json.loads(b64url_decode(p).decode('utf-8'))
            print('\nHeader:')
            print(json.dumps(header, indent=2))
            print('\nPayload:')
            print(json.dumps(payload, indent=2))
        except Exception as e:
            print('Failed to decode token parts:', e)
    else:
        print('\nJWT_SECRET_KEY does not look like a JWT token (no two dots). It may be a raw secret used to sign tokens.')


if __name__ == '__main__':
    main()
