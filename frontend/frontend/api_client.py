import os

import requests

API_URL = os.getenv("API_URL", "http://127.0.0.1:8000")
TIMEOUT = 180


class APIError(Exception):
    pass


def _check(resp):
    if resp.status_code >= 400:
        try:
            detail = resp.json().get("detail", resp.text)
        except Exception:
            detail = resp.text
        raise APIError(detail)
    return resp


def upload(file_name, file_bytes):
    r = requests.post(f"{API_URL}/upload", files={"file": (file_name, file_bytes)}, timeout=TIMEOUT)
    return _check(r).json()


def get(path):
    return _check(requests.get(f"{API_URL}{path}", timeout=TIMEOUT)).json()


def post(path, payload=None):
    return _check(requests.post(f"{API_URL}{path}", json=payload, timeout=TIMEOUT)).json()


def get_pdf():
    return _check(requests.get(f"{API_URL}/report", timeout=TIMEOUT)).content