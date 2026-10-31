import os, sqlite3, secrets, time
from flask import Flask, request, session, redirect, Response, render_template_string, abort, g
from werkzeug.middleware.proxy_fix import ProxyFix

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)
app.secret_key = os.environ.get("SECRET_KEY", "troque-esta-chave")
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
ADMIN_KEY = os.environ.get("ADMIN_KEY", "admin123")  # TROQUE no servidor!
DB = os.environ.get("DB_PATH", "scripts.db")


def db():
    if "db" not in g:
        g.db = sqlite3.connect(DB)
        g.db.row_factory = sqlite3.Row
        g.db.execute("CREATE TABLE IF NOT EXISTS scripts(id TEXT PRIMARY KEY, name TEXT, code TEXT, created INT)")
    return g.db


@app.teardown_appcontext
def close_db(_):
    d = g.pop("db", None)
    if d:
        d.close()


def is_admin():
    return session.get("ok") is True


def get_or_404(sid):
    row = db().execute("SELECT * FROM scripts WHERE id=?", (sid,)).fetchone()
    if not row:
        abort(404)
    return row


PAGE = """<!doctype html><html lang="pt-br"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>RawHub</title>
<style>
:root{color-scheme:dark}*{box-sizing:border-box}
body{margin:0;font:15px system-ui,sans-serif;background:#0f1115;color:#e6e6e6;padding:16px;max-width:820px;margin:auto}
h1{font-size:20px}input,textarea{width:100%;padding:10px;margin:6px 0;background:#1a1d24;color:#eee;border:1px solid #2c313c;border-radius:8px;font:inherit}
textarea{min-height:160px;font-family:ui-monospace,monospace;font-size:13px}
button,.b{background:#3b82f6;color:#fff;border:0;border-radius:8px;padding:8px 12px;font:inherit;cursor:pointer;text-decoration:none;display:inline-block}
.g{background:#2c313c}.r{background:#dc2626}
.card{background:#171a21;border:1px solid #2c313c;border-radius:12px;padding:12px;margin:10px 0}
.row{display:flex;gap:6px;flex-wrap:wrap;margin-top:8px}code{color:#93c5fd;word-break:break-all;font-size:12px}
pre{background:#171a21;padding:12px;border-radius:8px;overflow:auto;white-space:pre-wrap;word-break:break-all}
</style></head><body>
<h1>📦 RawHub</h1>
{% if not admin %}
<form method="post" action="/login"><input type="password" name="key" placeholder="Senha de admin" required>
<button>Entrar</button></form>
{% else %}
<form method="post" action="/logout" style="float:right"><button class="g">Sair</button></form>
<form method="post" action="/new">
<input name="name" placeholder="Nome do script" maxlength="80" required>
<textarea name="code" placeholder="Cole o código aqui..." required></textarea>
<button>Criar link</button></form>
{% for s in rows %}
<div class="card"><b>{{ s['name'] }}</b><br>
<code>loadstring(game:HttpGet("{{ root }}{{ s['id'] }}"))()</code>
<div class="row">
<button onclick="cp(this)" data-t='loadstring(game:HttpGet("{{ root }}{{ s['id'] }}"))()'>Copiar loadstring</button>
<button class="g" onclick="cp(this)" data-t="{{ root }}{{ s['id'] }}">Copiar link</button>
<a class="b g" href="/v/{{ s['id'] }}">Ver código</a>
<a class="b g" href="/{{ s['id'] }}" target="_blank">Raw</a>
<a class="b g" href="/d/{{ s['id'] }}">Baixar</a>
<form method="post" action="/del/{{ s['id'] }}" onsubmit="return confirm('Apagar?')"><button class="r">Apagar</button></form>
</div></div>
{% else %}<p>Nenhum script ainda.</p>{% endfor %}
{% endif %}
<script>
function cp(b){navigator.clipboard.writeText(b.dataset.t).then(()=>{const o=b.textContent;b.textContent='Copiado ✓';setTimeout(()=>b.textContent=o,1200)})}
</script></body></html>"""

VIEW = """<!doctype html><html lang="pt-br"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{{ s['name'] }}</title>
<style>:root{color-scheme:dark}body{font:15px system-ui;background:#0f1115;color:#e6e6e6;padding:16px;max-width:820px;margin:auto}
pre{background:#171a21;padding:12px;border-radius:8px;overflow:auto;white-space:pre-wrap;word-break:break-all;font-size:13px}
.b{background:#3b82f6;color:#fff;border:0;border-radius:8px;padding:8px 12px;text-decoration:none;font:inherit;cursor:pointer}</style></head><body>
<p><a class="b" href="/">← Voltar</a> <button class="b" id="c">Copiar código</button>
<a class="b" href="/d/{{ s['id'] }}">Baixar</a></p>
<h3>{{ s['name'] }}</h3><pre id="code">{{ s['code'] }}</pre>
<script>c.onclick=()=>navigator.clipboard.writeText(document.getElementById('code').textContent).then(()=>c.textContent='Copiado ✓')</script>
</body></html>"""


@app.get("/")
def index():
    rows = db().execute("SELECT * FROM scripts ORDER BY created DESC").fetchall() if is_admin() else []
    return render_template_string(PAGE, admin=is_admin(), rows=rows, root=request.url_root)


@app.post("/login")
def login():
    if secrets.compare_digest(request.form.get("key", ""), ADMIN_KEY):
        session["ok"] = True
    return redirect("/")


@app.post("/logout")
def logout():
    session.clear()
    return redirect("/")


@app.post("/new")
def new():
    if not is_admin():
        abort(403)
    name = request.form.get("name", "").strip()[:80]
    code = request.form.get("code", "")
    if name and code:
        db().execute("INSERT INTO scripts VALUES(?,?,?,?)",
                     (secrets.token_urlsafe(5), name, code, int(time.time())))
        db().commit()
    return redirect("/")


@app.post("/del/<sid>")
def delete(sid):
    if not is_admin():
        abort(403)
    db().execute("DELETE FROM scripts WHERE id=?", (sid,))
    db().commit()
    return redirect("/")


@app.get("/v/<sid>")
def view(sid):
    if not is_admin():
        abort(403)
    return render_template_string(VIEW, s=get_or_404(sid))


@app.get("/d/<sid>")
def download(sid):
    s = get_or_404(sid)
    fn = "".join(c for c in s["name"] if c.isalnum() or c in "-_ ").strip() or "script"
    return Response(s["code"], mimetype="text/plain",
                    headers={"Content-Disposition": f'attachment; filename="{fn}.lua"'})


@app.get("/<sid>")
def raw(sid):  # link curto + raw (é o que o loadstring usa)
    s = get_or_404(sid)
    return Response(s["code"], mimetype="text/plain; charset=utf-8",
                    headers={"Cache-Control": "no-store"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
