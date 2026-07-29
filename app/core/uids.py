import base64


def encode_uid(user_id: int) -> str:
    return base64.urlsafe_b64encode(str(user_id).encode()).decode().rstrip("=")


def decode_uid(uid: str) -> int:
    padding = (-len(uid)) % 4
    normalized = uid + ("=" * padding)
    return int(base64.urlsafe_b64decode(normalized.encode()).decode())
