from .errors import BusinessError

class DealService:
    def __init__(self, db): self.db=db

    def create(self, material_id, requester_id):
        material=self.db.execute("SELECT * FROM materials WHERE id=?",(material_id,)).fetchone()
        if not material or material["status"] != "active": raise BusinessError("Материал недоступен.")
        if material["owner_id"] == requester_id: raise BusinessError("Нельзя отправить запрос на собственный материал.")
        if self.db.execute("SELECT 1 FROM deals WHERE material_id=? AND requester_id=?",(material_id,requester_id)).fetchone():
            raise BusinessError("Вы уже отправляли запрос по этому материалу.")
        self.db.execute("INSERT INTO deals(material_id,requester_id) VALUES(?,?)",(material_id,requester_id))

    def incoming(self, owner_id):
        return self.db.execute("""SELECT d.*, m.title, u.name AS requester_name FROM deals d
          JOIN materials m ON m.id=d.material_id JOIN users u ON u.id=d.requester_id
          WHERE m.owner_id=? ORDER BY d.created_at DESC""",(owner_id,)).fetchall()

    def outgoing(self, requester_id):
        return self.db.execute("""SELECT d.*, m.title, u.name AS owner_name FROM deals d
          JOIN materials m ON m.id=d.material_id JOIN users u ON u.id=m.owner_id
          WHERE d.requester_id=? ORDER BY d.created_at DESC""",(requester_id,)).fetchall()

    def change_status(self, deal_id, owner_id, action):
        deal=self.db.execute("""SELECT d.*,m.owner_id,m.status AS material_status FROM deals d
            JOIN materials m ON m.id=d.material_id WHERE d.id=?""",(deal_id,)).fetchone()
        if not deal: raise BusinessError("Запрос не найден.")
        if deal["owner_id"] != owner_id: raise BusinessError("Менять статус запроса может только владелец материала.")
        mapping={"accept":"accepted","reject":"rejected","complete":"completed"}
        if action not in mapping: raise BusinessError("Недопустимое действие.")
        if action=="accept":
            if deal["status"]!="pending" or deal["material_status"]!="active":
                raise BusinessError("Запрос нельзя принять: он уже обработан или материал недоступен.")
            # Transactional conditional update protects against competing acceptance requests.
            cur=self.db.execute("UPDATE materials SET status='reserved',version=version+1 WHERE id=? AND status='active'",
                                (deal["material_id"],))
            if cur.rowcount != 1: raise BusinessError("Материал уже зарезервирован другим запросом.")
            self.db.execute("UPDATE deals SET status='rejected' WHERE material_id=? AND id<>? AND status='pending'",
                            (deal["material_id"],deal_id))
        elif action=="reject":
            if deal["status"]!="pending": raise BusinessError("Можно отклонить только ожидающий запрос.")
        elif action=="complete":
            if deal["status"]!="accepted": raise BusinessError("Завершить можно только принятую сделку.")
            self.db.execute("UPDATE materials SET status='closed',version=version+1 WHERE id=?",(deal["material_id"],))
        self.db.execute("UPDATE deals SET status=? WHERE id=?",(mapping[action],deal_id))
