from .errors import BusinessError

class MaterialService:
    MODES = {"Обмен", "Продажа", "Бесплатно"}
    def __init__(self, db): self.db = db

    def list_available(self, query="", category=""):
        sql = """SELECT m.*, u.name AS owner_name FROM materials m
                 JOIN users u ON u.id=m.owner_id WHERE m.status='active'"""
        args = []
        if query:
            sql += " AND (m.title LIKE ? OR m.description LIKE ?)"
            args += [f"%{query}%", f"%{query}%"]
        if category:
            sql += " AND m.category=?"
            args.append(category)
        sql += " ORDER BY m.created_at DESC"
        return self.db.execute(sql, args).fetchall()

    def categories(self):
        return [r["category"] for r in self.db.execute(
            "SELECT DISTINCT category FROM materials WHERE status='active' ORDER BY category").fetchall()]

    def get(self, material_id):
        return self.db.execute("""SELECT m.*, u.name AS owner_name FROM materials m
            JOIN users u ON u.id=m.owner_id WHERE m.id=?""", (material_id,)).fetchone()

    def create(self, owner_id, title, description, category, mode, price, file_url):
        title, description, category = title.strip(), description.strip(), category.strip()
        if not all([title, description, category]):
            raise BusinessError("Название, описание и категория обязательны.")
        if len(title) > 120:
            raise BusinessError("Название не должно превышать 120 символов.")
        if mode not in self.MODES:
            raise BusinessError("Выберите допустимый тип размещения.")
        try: price = float(price or 0)
        except ValueError: raise BusinessError("Цена должна быть числом.")
        if price < 0: raise BusinessError("Цена не может быть отрицательной.")
        if mode != "Продажа": price = 0
        self.db.execute("""INSERT INTO materials(owner_id,title,description,category,mode,price,file_url)
            VALUES(?,?,?,?,?,?,?)""", (owner_id,title,description,category,mode,price,file_url.strip()))

    def update(self, material_id, owner_id, form):
        row = self.db.execute("SELECT * FROM materials WHERE id=?", (material_id,)).fetchone()
        if not row: raise BusinessError("Материал не найден.")
        if row["owner_id"] != owner_id: raise BusinessError("Редактировать материал может только его владелец.")
        if row["status"] != "active": raise BusinessError("Нельзя редактировать материал с активной сделкой или закрытым статусом.")
        title, description, category = form.get("title","").strip(), form.get("description","").strip(), form.get("category","").strip()
        mode = form.get("mode","")
        if not title or not description or not category: raise BusinessError("Название, описание и категория обязательны.")
        if len(title)>120: raise BusinessError("Название не должно превышать 120 символов.")
        if mode not in self.MODES: raise BusinessError("Выберите допустимый тип размещения.")
        try: price=float(form.get("price","0") or 0)
        except ValueError: raise BusinessError("Цена должна быть числом.")
        if price < 0: raise BusinessError("Цена не может быть отрицательной.")
        if mode != "Продажа": price=0
        # Optimistic concurrency: version in WHERE prevents overwriting a concurrent edit.
        cur=self.db.execute("""UPDATE materials SET title=?,description=?,category=?,mode=?,price=?,file_url=?,version=version+1
            WHERE id=? AND owner_id=? AND version=?""",
            (title,description,category,mode,price,form.get("file_url","").strip(),material_id,owner_id,row["version"]))
        if cur.rowcount != 1: raise BusinessError("Материал был изменён другим пользователем. Обновите страницу и повторите.")

    def delete(self, material_id, owner_id):
        row=self.db.execute("SELECT * FROM materials WHERE id=?",(material_id,)).fetchone()
        if not row: raise BusinessError("Материал не найден.")
        if row["owner_id"] != owner_id: raise BusinessError("Удалить материал может только его владелец.")
        if self.db.execute("SELECT 1 FROM deals WHERE material_id=? AND status IN ('pending','accepted')",(material_id,)).fetchone():
            raise BusinessError("Нельзя удалить материал, по которому есть активные запросы.")
        self.db.execute("DELETE FROM materials WHERE id=?",(material_id,))
