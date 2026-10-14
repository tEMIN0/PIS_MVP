from werkzeug.security import generate_password_hash, check_password_hash
from .errors import BusinessError

class UserService:
    def __init__(self, db): self.db = db

    def register(self, name, email, password):
        name, email = name.strip(), email.strip().lower()
        if not name or not email or not password:
            raise BusinessError("Имя, email и пароль обязательны.")
        if "@" not in email or "." not in email.split("@")[-1]:
            raise BusinessError("Укажите корректный email.")
        if len(password) < 8:
            raise BusinessError("Пароль должен содержать не менее 8 символов.")
        try:
            self.db.execute("INSERT INTO users(name,email,password_hash) VALUES(?,?,?)",
                            (name, email, generate_password_hash(password)))
        except Exception as exc:
            if "UNIQUE" in str(exc).upper():
                raise BusinessError("Пользователь с таким email уже зарегистрирован.")
            raise

    def authenticate(self, email, password):
        row = self.db.execute("SELECT * FROM users WHERE email=?", (email.strip().lower(),)).fetchone()
        if row and check_password_hash(row["password_hash"], password or ""):
            return row
        return None

    def get_by_id(self, user_id):
        return self.db.execute("SELECT id,name,email,created_at FROM users WHERE id=?", (user_id,)).fetchone()
