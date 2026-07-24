#!/usr/bin/env python3
"""
Encrypt tokens.json -> tokens.json.enc  (the encrypted file is what you commit).

  python tools/encrypt_tokens.py --genkey        # print a fresh encryption key
  TOKEN_ENC_KEY=... python tools/encrypt_tokens.py           # encrypt tokens.json
  TOKEN_ENC_KEY=... python tools/encrypt_tokens.py --decrypt # sanity-check: print it back

Keep tokens.json OUT of git (it's plaintext). Commit only tokens.json.enc.
Put TOKEN_ENC_KEY into the repo's GitHub Actions Secrets.
"""
import os
import sys
import json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

if "--genkey" in sys.argv:
    from cryptography.fernet import Fernet
    print(Fernet.generate_key().decode())
    sys.exit(0)

import tokens as tok  # noqa: E402  (needs TOKEN_ENC_KEY)

PLAIN = os.path.join(os.path.dirname(__file__), "..", "tokens.json")

if "--decrypt" in sys.argv:
    print(json.dumps(tok.load(), indent=2))
    sys.exit(0)

with open(PLAIN) as f:
    data = json.load(f)
tok.save(data)
print("Wrote tokens.json.enc  ✓  (commit this file; do NOT commit tokens.json)")
