from flask import Flask, render_template, request, redirect, url_for, session, flash, abort
from werkzeug.security import generate_password_hash, check_password_hash
from database import init_db, get_db
from services.user_service import UserService
from services.material_service import MaterialService
from services.deal_service import DealService
from services.errors import BusinessError
import os

app = Flask(__name__)
from database import close_db
app.teardown_appcontext(close_db)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-secret-key-for-production")
init_db()

def current_user():
    if "user_id" not in session:
        return None
    return UserService(get_db()).get_by_id(session["user_id"])

@app.context_processor
def inject_user():
    return {"current_user": current_user()}

@app.errorhandler(BusinessError)
def handle_business_error(error):
    flash(str(error), "error")
    return redirect(request.referrer or url_for("index"))

@app.errorhandler(404)
def not_found(_):
    return render_template("error.html", message="Запрашиваемый объект не найден."), 404

@app.route("/")
def index():
    q = request.args.get("q", "").strip()
    category = request.args.get("category", "").strip()
    materials = MaterialService(get_db()).list_available(query=q, category=category)
    categories = MaterialService(get_db()).categories()
    return render_template("index.html", materials=materials, categories=categories, q=q, selected_category=category)

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        db = get_db()
        UserService(db).register(
            request.form.get("name", ""), request.form.get("email", ""),
            request.form.get("password", "")
        )
        db.commit()
        flash("Регистрация завершена. Теперь войдите в систему.", "success")
        return redirect(url_for("login"))
    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user = UserService(get_db()).authenticate(request.form.get("email", ""), request.form.get("password", ""))
        if not user:
            raise BusinessError("Неверный email или пароль.")
        session.clear()
        session["user_id"] = user["id"]
        return redirect(url_for("index"))
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))

@app.route("/materials/new", methods=["GET", "POST"])
def new_material():
    if not current_user():
        flash("Для размещения материала необходимо войти.", "error")
        return redirect(url_for("login"))
    if request.method == "POST":
        db = get_db()
        MaterialService(db).create(
            owner_id=current_user()["id"],
            title=request.form.get("title", ""),
            description=request.form.get("description", ""),
            category=request.form.get("category", ""),
            mode=request.form.get("mode", ""),
            price=request.form.get("price", "0"),
            file_url=request.form.get("file_url", "")
        )
        db.commit()
        flash("Материал опубликован.", "success")
        return redirect(url_for("index"))
    return render_template("material_form.html")

@app.route("/materials/<int:material_id>")
def material_detail(material_id):
    material = MaterialService(get_db()).get(material_id)
    if not material:
        abort(404)
    return render_template("material_detail.html", material=material)

@app.route("/materials/<int:material_id>/edit", methods=["GET", "POST"])
def edit_material(material_id):
    user = current_user()
    if not user:
        return redirect(url_for("login"))
    service = MaterialService(get_db())
    material = service.get(material_id)
    if not material:
        abort(404)
    if request.method == "POST":
        service.update(material_id, user["id"], request.form)
        get_db().commit()
        flash("Изменения сохранены.", "success")
        return redirect(url_for("material_detail", material_id=material_id))
    return render_template("material_form.html", material=material)

@app.route("/materials/<int:material_id>/delete", methods=["POST"])
def delete_material(material_id):
    user = current_user()
    if not user:
        return redirect(url_for("login"))
    service = MaterialService(get_db())
    service.delete(material_id, user["id"])
    get_db().commit()
    flash("Материал удалён.", "success")
    return redirect(url_for("index"))

@app.route("/materials/<int:material_id>/request", methods=["POST"])
def request_deal(material_id):
    user = current_user()
    if not user:
        return redirect(url_for("login"))
    db = get_db()
    DealService(db).create(material_id, user["id"])
    db.commit()
    flash("Запрос отправлен владельцу материала.", "success")
    return redirect(url_for("material_detail", material_id=material_id))

@app.route("/my/deals")
def my_deals():
    user = current_user()
    if not user:
        return redirect(url_for("login"))
    service = DealService(get_db())
    return render_template("deals.html", incoming=service.incoming(user["id"]), outgoing=service.outgoing(user["id"]))

@app.route("/deals/<int:deal_id>/<action>", methods=["POST"])
def deal_action(deal_id, action):
    user = current_user()
    if not user:
        return redirect(url_for("login"))
    DealService(get_db()).change_status(deal_id, user["id"], action)
    get_db().commit()
    flash("Статус запроса обновлён.", "success")
    return redirect(url_for("my_deals"))

if __name__ == "__main__":
    app.run(debug=True)
