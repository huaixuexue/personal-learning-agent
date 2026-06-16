import hashlib
import secrets

from sqlalchemy.orm import Session

from app.models import UserAccount
from app.services.log_service import normalize_username


def hash_password(password: str, salt: str) -> str:
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        120_000,
    )
    return digest.hex()


def login_or_create(db: Session, username: str, password: str) -> tuple[UserAccount, bool]:
    safe_username = normalize_username(username)
    account = db.query(UserAccount).filter(UserAccount.username == safe_username).first()
    if account is not None:
        expected = hash_password(password, account.password_salt)
        if not secrets.compare_digest(expected, account.password_hash):
            raise ValueError("用户名或密码错误")
        return account, False

    salt = secrets.token_hex(16)
    account = UserAccount(
        username=safe_username,
        password_salt=salt,
        password_hash=hash_password(password, salt),
    )
    db.add(account)
    db.commit()
    db.refresh(account)
    return account, True
