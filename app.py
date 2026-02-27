from functools import wraps
import os
from datetime import datetime
from werkzeug.utils import secure_filename
from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory, session
from flask_sqlalchemy import SQLAlchemy

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}

# Galerias fixas (7º, 8º, 9º, 1ºEM, 2ºEM)
TURMAS = {
    "7ano": "7º Ano",
    "8ano": "8º Ano",
    "9ano": "9º Ano",
    "1em": "1º Ensino Médio",
    "2em": "2º Ensino Médio",
}
TURMAS_LIST = list(TURMAS.keys())


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def normalize_database_url(url: str) -> str:
    """
    Render costuma fornecer DATABASE_URL começando com postgres://
    SQLAlchemy prefere postgresql://.
    """
    if url and url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql://", 1)
    return url

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-change-me")
app.config["ADMIN_PASSWORD"] = os.environ.get("ADMIN_PASSWORD", "bicudo@26")

# Uploads
upload_root = os.environ.get("UPLOAD_FOLDER", os.path.join(app.root_path, "uploads"))
app.config["UPLOAD_FOLDER"] = upload_root
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

# Limite de upload (8 MB)
app.config["MAX_CONTENT_LENGTH"] = int(os.environ.get("MAX_CONTENT_LENGTH", 8 * 1024 * 1024))

db_url = os.environ.get("DATABASE_URL", f"sqlite:///{os.path.join(app.root_path, 'app.db')}")
app.config["SQLALCHEMY_DATABASE_URI"] = normalize_database_url(db_url)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# --- Proteção simples por senha (somente para postar/deletar) ---

def is_admin() -> bool:
    return session.get("is_admin") is True


def admin_required(view_func):
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        if not is_admin():
            return redirect(url_for("auth", next=request.path))
        return view_func(*args, **kwargs)
    return wrapper

# --- Inicialização automática do banco (compatível com Flask 3.x) ---
# Evita erro "no such table" caso o db ainda não exista.
_db_inited = False

@app.before_request
def ensure_db():
    global _db_inited
    if not _db_inited and os.environ.get("AUTO_INIT_DB", "1") == "1":
        with app.app_context():
            db.create_all()
        _db_inited = True

class Image(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), unique=True, nullable=False)
    original_name = db.Column(db.String(255), nullable=True)
    caption = db.Column(db.String(200), nullable=True)
    turma = db.Column(db.String(80), nullable=True)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)


@app.route("/uploads/<path:filename>")
def uploaded_file(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)



@app.route("/")
def index():
    # Página inicial: escolher galeria
    # Conta quantas imagens por turma
    counts = {k: 0 for k in TURMAS_LIST}
    latest = {k: None for k in TURMAS_LIST}

    rows = db.session.query(Image.turma, db.func.count(Image.id)).group_by(Image.turma).all()
    for turma, cnt in rows:
        if turma in counts:
            counts[turma] = int(cnt)

    for k in TURMAS_LIST:
        latest[k] = Image.query.filter(Image.turma == k).order_by(Image.uploaded_at.desc()).first()

    return render_template("home.html", turmas=TURMAS, counts=counts, latest=latest)

@app.route("/galeria/<turma>")
def galeria(turma: str):
    if turma not in TURMAS:
        flash("Galeria inválida.", "warning")
        return redirect(url_for("index"))
    images = Image.query.filter(Image.turma == turma).order_by(Image.uploaded_at.desc()).all()
    return render_template("galeria.html", turma_slug=turma, turma_nome=TURMAS[turma], images=images)

@app.route("/auth", methods=["GET", "POST"])
def auth():
    nxt = request.args.get("next") or url_for("admin")
    if request.method == "POST":
        senha = request.form.get("senha", "")
        if senha == app.config["ADMIN_PASSWORD"]:
            session["is_admin"] = True
            flash("Acesso liberado para postar/deletar.", "success")
            return redirect(nxt)
        flash("Senha incorreta.", "danger")
    return render_template("auth.html", next=nxt)

@app.route("/sair")
def sair():
    session.pop("is_admin", None)
    flash("Você saiu da área de gestão.", "info")
    return redirect(url_for("index"))

@app.route("/admin")
@admin_required
def admin():
    turma = request.args.get("turma", "").strip()
    query = Image.query
    if turma in TURMAS:
        query = query.filter(Image.turma == turma)
    images = query.order_by(Image.uploaded_at.desc()).all()
    return render_template("admin.html", images=images, turmas=TURMAS, turma_atual=turma)

@app.route("/upload", methods=["GET", "POST"])
@admin_required
def upload():
    if request.method == "POST":
        file = request.files.get("image")
        caption = request.form.get("caption", "").strip()
        turma = request.form.get("turma", "").strip()

        if turma not in TURMAS:
            flash("Selecione uma galeria válida.", "warning")
            return redirect(request.url)

        if not file or file.filename == "":
            flash("Selecione uma imagem.", "warning")
            return redirect(request.url)

        if not allowed_file(file.filename):
            flash("Formato não permitido. Use PNG/JPG/JPEG/GIF/WEBP.", "warning")
            return redirect(request.url)

        original_name = file.filename
        safe = secure_filename(original_name)

        stamp = datetime.utcnow().strftime("%Y%m%d%H%M%S%f")
        ext = safe.rsplit(".", 1)[1].lower()
        filename = f"{stamp}.{ext}"

        save_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        file.save(save_path)

        img = Image(filename=filename, original_name=original_name, caption=caption or None, turma=turma)
        db.session.add(img)
        db.session.commit()

        flash("Imagem enviada com sucesso!", "success")
        return redirect(url_for("admin", turma=turma))

    return render_template("upload.html", turmas=TURMAS)

@app.route("/delete/<int:image_id>", methods=["POST"])
@admin_required
def delete_image(image_id: int):
    img = db.session.get(Image, image_id)
    if not img:
        flash("Imagem não encontrada.", "warning")
        return redirect(url_for("admin"))

    try:
        os.remove(os.path.join(app.config["UPLOAD_FOLDER"], img.filename))
    except FileNotFoundError:
        pass

    turma = img.turma
    db.session.delete(img)
    db.session.commit()
    flash("Imagem removida.", "info")
    return redirect(url_for("admin", turma=turma))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
