"""Mega Lanchonete Espacial: servidor web + API, só com a biblioteca padrão do Python.

Uso:  python servidor.py     (no Windows também funciona:  py servidor.py)
"""
import json
import mimetypes
import os
import re
import sqlite3
import sys
import threading
import time
import traceback
import uuid
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

from backend import config as _config  # noqa: F401  (carrega o arquivo .env antes de tudo)
from backend import banco, emails, seguranca
from backend import validacao as V

RAIZ = Path(__file__).resolve().parent
PUBLICO = RAIZ / "public"
PRODUCAO = os.environ.get("MLE_PRODUCAO", "").lower() in ("1", "true", "sim")
COOKIE = "mle_sessao"
SESSAO_DIAS = 7
LIMITE_CORPO = 50 * 1024

mimetypes.add_type("text/javascript", ".js")
mimetypes.add_type("image/webp", ".webp")

CSP = ("default-src 'self'; script-src 'self'; style-src 'self' https://fonts.googleapis.com; "
       "font-src https://fonts.gstatic.com; img-src 'self' data:; connect-src 'self'; object-src 'none'; "
       "frame-ancestors 'none'; base-uri 'self'; form-action 'self'")

PREFERENCIAS_PADRAO = {
    "tema": "laranja", "estrelas": True, "reduzirAnimacoes": False, "descricoesVisiveis": False,
    "tamanhoTexto": "normal", "compacto": False, "pagamentoPadrao": "", "notificacoes": True,
    "emailPedidos": True,
}
TEMAS = ["laranja", "ciano", "ambar"]
TAMANHOS = ["normal", "grande", "maior"]


class Erro(Exception):
    def __init__(self, status, mensagem):
        super().__init__(mensagem)
        self.status = status
        self.mensagem = mensagem


# ---------- limite de tentativas (login e cadastro) ----------
_tentativas = defaultdict(deque)
_trava = threading.Lock()


def limitar(ip, maximo=30, janela=15 * 60):
    agora = time.monotonic()
    with _trava:
        fila = _tentativas[ip]
        while fila and agora - fila[0] > janela:
            fila.popleft()
        if len(fila) >= maximo:
            raise Erro(429, "Muitas tentativas. Aguarde alguns minutos e tente de novo.")
        fila.append(agora)


# ---------- contexto de cada requisição da API ----------
class Contexto:
    def __init__(self, corpo, usuario_id, ip, token):
        self.corpo = corpo
        self.usuario_id = usuario_id
        self.ip = ip
        self.token = token
        self.cookies = []
        self.parametros = ()

    def exigir_login(self):
        if not self.usuario_id:
            raise Erro(401, "Entre na sua conta para continuar.")

    def abrir_sessao(self, conexao, usuario_id):
        token = seguranca.novo_token()
        expira = (datetime.now(timezone.utc) + timedelta(days=SESSAO_DIAS)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
        conexao.execute("INSERT INTO sessoes (token_hash, usuario_id, expira_em) VALUES (?, ?, ?)",
                        (seguranca.hash_token(token), usuario_id, expira))
        self.cookies.append(self._cookie(token, SESSAO_DIAS * 86400))

    def encerrar_sessao(self, conexao):
        if self.token:
            conexao.execute("DELETE FROM sessoes WHERE token_hash = ?", (seguranca.hash_token(self.token),))
        self.cookies.append(self._cookie("", 0))

    @staticmethod
    def _cookie(valor, idade):
        texto = f"{COOKIE}={valor}; Path=/; HttpOnly; SameSite=Lax; Max-Age={idade}"
        return texto + "; Secure" if PRODUCAO else texto


def corpo_dict(ctx):
    return ctx.corpo if isinstance(ctx.corpo, dict) else {}


# ---------- autenticação ----------
def cadastro(ctx):
    limitar(ctx.ip)
    b = corpo_dict(ctx)
    nome, email, erro_senha = V.validar_nome(b.get("nome")), V.validar_email(b.get("email")), V.validar_senha(b.get("senha"))
    if not nome:
        raise Erro(400, "Informe um nome com pelo menos 2 letras.")
    if not email:
        raise Erro(400, "Informe um e-mail válido.")
    if erro_senha:
        raise Erro(400, erro_senha)
    senha_hash = seguranca.hash_senha(b["senha"])
    with banco.transacao() as c:
        try:
            cur = c.execute("INSERT INTO usuarios (nome, email, senha_hash, criado_em) VALUES (?, ?, ?, ?)",
                            (nome, email, senha_hash, banco.agora()))
        except sqlite3.IntegrityError:
            raise Erro(409, "Já existe uma conta com este e-mail.")
        ctx.abrir_sessao(c, cur.lastrowid)
    return 201, {"ok": True}


def login(ctx):
    limitar(ctx.ip)
    b = corpo_dict(ctx)
    email = V.validar_email(b.get("email"))
    senha = b.get("senha") if isinstance(b.get("senha"), str) else ""
    with banco.transacao() as c:
        linha = c.execute("SELECT id, senha_hash FROM usuarios WHERE email = ?", (email,)).fetchone() if email else None
        confere = seguranca.confere_senha(senha[:72], linha["senha_hash"] if linha else seguranca.HASH_FALSO)
        if not linha or not confere:
            raise Erro(401, "E-mail ou senha incorretos.")
        c.execute("DELETE FROM sessoes WHERE expira_em < ?", (banco.agora(),))
        ctx.abrir_sessao(c, linha["id"])
    return 200, {"ok": True}


def logout(ctx):
    with banco.transacao() as c:
        ctx.encerrar_sessao(c)
    return 200, {"ok": True}


# ---------- perfil ----------
def montar_usuario(l):
    return {
        "id": l["id"], "nome": l["nome"], "email": l["email"], "telefone": l["telefone"] or "", "avatar": l["avatar"],
        "endereco": {k: l[k] or "" for k in ("cep", "rua", "numero", "complemento", "bairro", "cidade", "uf")},
        "criadoEm": l["criado_em"],
    }


def limpar_preferencias(entrada, base=PREFERENCIAS_PADRAO):
    e = entrada if isinstance(entrada, dict) else {}
    booleano = lambda k: e[k] if isinstance(e.get(k), bool) else base[k]
    pagamento = e.get("pagamentoPadrao")
    return {
        "tema": e.get("tema") if e.get("tema") in TEMAS else base["tema"],
        "estrelas": booleano("estrelas"),
        "reduzirAnimacoes": booleano("reduzirAnimacoes"),
        "descricoesVisiveis": booleano("descricoesVisiveis"),
        "tamanhoTexto": e.get("tamanhoTexto") if e.get("tamanhoTexto") in TAMANHOS else base["tamanhoTexto"],
        "compacto": booleano("compacto"),
        "pagamentoPadrao": pagamento if pagamento == "" or pagamento in V.PAGAMENTOS else base["pagamentoPadrao"],
        "notificacoes": booleano("notificacoes"),
        "emailPedidos": booleano("emailPedidos"),
    }


def carregar_preferencias(c, usuario_id):
    linha = c.execute("SELECT dados FROM preferencias WHERE usuario_id = ?", (usuario_id,)).fetchone()
    if not linha:
        return dict(PREFERENCIAS_PADRAO)
    try:
        return limpar_preferencias(json.loads(linha["dados"]))
    except ValueError:
        return dict(PREFERENCIAS_PADRAO)


def perfil_ver(ctx):
    ctx.exigir_login()
    with banco.transacao() as c:
        usuario = c.execute("SELECT * FROM usuarios WHERE id = ?", (ctx.usuario_id,)).fetchone()
        total = c.execute("SELECT COUNT(*) FROM pedidos WHERE usuario_id = ?", (ctx.usuario_id,)).fetchone()[0]
        return 200, {"usuario": montar_usuario(usuario), "preferencias": carregar_preferencias(c, ctx.usuario_id), "totalPedidos": total}


def perfil_editar(ctx):
    ctx.exigir_login()
    b = corpo_dict(ctx)
    e = b.get("endereco") if isinstance(b.get("endereco"), dict) else {}
    nome, email = V.validar_nome(b.get("nome")), V.validar_email(b.get("email"))
    telefone, cep = V.validar_telefone(b.get("telefone")), V.validar_cep(e.get("cep"))
    uf = V.texto(e.get("uf"), 2).upper()
    if not nome:
        raise Erro(400, "Informe um nome com pelo menos 2 letras.")
    if not email:
        raise Erro(400, "Informe um e-mail válido.")
    if telefone is None:
        raise Erro(400, "Telefone inválido. Use DDD + número.")
    if cep is None:
        raise Erro(400, "CEP inválido. Use 8 dígitos.")
    if uf and uf not in V.UFS:
        raise Erro(400, "Estado (UF) inválido.")
    avatar = b.get("avatar") if b.get("avatar") in V.AVATARES else "astronauta"
    with banco.transacao() as c:
        try:
            c.execute(
                "UPDATE usuarios SET nome=?, email=?, telefone=?, avatar=?, cep=?, rua=?, numero=?, complemento=?, "
                "bairro=?, cidade=?, uf=? WHERE id=?",
                (nome, email, telefone or None, avatar, cep or None, V.texto(e.get("rua"), 120) or None,
                 V.texto(e.get("numero"), 10) or None, V.texto(e.get("complemento"), 60) or None,
                 V.texto(e.get("bairro"), 60) or None, V.texto(e.get("cidade"), 60) or None, uf or None, ctx.usuario_id))
        except sqlite3.IntegrityError:
            raise Erro(409, "Este e-mail já está em uso por outra conta.")
        usuario = c.execute("SELECT * FROM usuarios WHERE id = ?", (ctx.usuario_id,)).fetchone()
    return 200, {"usuario": montar_usuario(usuario)}


def perfil_senha(ctx):
    ctx.exigir_login()
    b = corpo_dict(ctx)
    erro_senha = V.validar_senha(b.get("novaSenha"))
    if erro_senha:
        raise Erro(400, erro_senha)
    atual = b.get("senhaAtual")
    with banco.transacao() as c:
        guardado = c.execute("SELECT senha_hash FROM usuarios WHERE id = ?", (ctx.usuario_id,)).fetchone()["senha_hash"]
        if not isinstance(atual, str) or not seguranca.confere_senha(atual[:72], guardado):
            raise Erro(403, "A senha atual está incorreta.")
        c.execute("UPDATE usuarios SET senha_hash = ? WHERE id = ?", (seguranca.hash_senha(b["novaSenha"]), ctx.usuario_id))
    return 200, {"ok": True}


def preferencias_ver(ctx):
    ctx.exigir_login()
    with banco.transacao() as c:
        return 200, {"preferencias": carregar_preferencias(c, ctx.usuario_id)}


def preferencias_salvar(ctx):
    ctx.exigir_login()
    with banco.transacao() as c:
        novas = limpar_preferencias(ctx.corpo, carregar_preferencias(c, ctx.usuario_id))
        c.execute("INSERT INTO preferencias (usuario_id, dados) VALUES (?, ?) "
                  "ON CONFLICT(usuario_id) DO UPDATE SET dados = excluded.dados",
                  (ctx.usuario_id, json.dumps(novas)))
    return 200, {"preferencias": novas}


def perfil_excluir(ctx):
    ctx.exigir_login()
    senha = corpo_dict(ctx).get("senha")
    with banco.transacao() as c:
        guardado = c.execute("SELECT senha_hash FROM usuarios WHERE id = ?", (ctx.usuario_id,)).fetchone()["senha_hash"]
        if not isinstance(senha, str) or not seguranca.confere_senha(senha[:72], guardado):
            raise Erro(403, "Senha incorreta. A conta não foi excluída.")
        c.execute("DELETE FROM usuarios WHERE id = ?", (ctx.usuario_id,))
        ctx.encerrar_sessao(c)
    return 200, {"ok": True}


# ---------- produtos e pedidos ----------
def produtos_listar(ctx):
    with banco.transacao() as c:
        linhas = c.execute("SELECT id, nome, preco_centavos, categoria, descricao, imagem FROM produtos WHERE ativo = 1 ORDER BY id").fetchall()
    return 200, [{"id": l["id"], "nome": l["nome"], "preco": l["preco_centavos"] / 100, "categoria": l["categoria"],
                  "descricao": l["descricao"], "imagem": l["imagem"]} for l in linhas]


def normalizar_itens(entrada):
    """Aceita [{id, quantidade}] ou uma lista simples de ids. Devolve None se for inválido."""
    if not isinstance(entrada, list) or not 1 <= len(entrada) <= 100:
        return None
    soma = {}
    for item in entrada:
        bruto_id = item.get("id") if isinstance(item, dict) else item
        bruto_qtd = item.get("quantidade") if isinstance(item, dict) else 1
        if isinstance(bruto_id, bool) or isinstance(bruto_qtd, bool) or not isinstance(bruto_id, int) or not isinstance(bruto_qtd, int):
            return None
        if not 1 <= bruto_qtd <= 20:
            return None
        soma[bruto_id] = min(soma.get(bruto_id, 0) + bruto_qtd, 20)
    return list(soma.items())


def pedido_criar(ctx):
    b = corpo_dict(ctx)
    itens = normalizar_itens(b.get("itens"))
    if itens is None:
        raise Erro(400, "Envie entre 1 e 100 itens, com quantidade de 1 a 20 cada.")
    pagamento = b.get("pagamento")
    if pagamento not in V.PAGAMENTOS:
        raise Erro(400, "Escolha uma forma de pagamento válida.")
    observacao = V.texto(b.get("observacao"), 200)

    with banco.transacao() as c:
        marcas = ",".join("?" * len(itens))
        # O preço vem sempre do banco; qualquer valor enviado pelo navegador é ignorado.
        produtos = {l["id"]: l for l in c.execute(
            f"SELECT id, nome, preco_centavos FROM produtos WHERE ativo = 1 AND id IN ({marcas})", [i for i, _ in itens])}
        if any(i not in produtos for i, _ in itens):
            raise Erro(400, "O pedido contém um produto que não existe mais.")
        linhas = [(produtos[i], q) for i, q in itens]
        total = sum(p["preco_centavos"] * q for p, q in linhas)

        entrega = None
        if ctx.usuario_id:
            u = c.execute("SELECT rua, numero, complemento, bairro, cidade, uf FROM usuarios WHERE id = ?", (ctx.usuario_id,)).fetchone()
            if u and u["rua"]:
                cidade_uf = "/".join(x for x in (u["cidade"], u["uf"]) if x)
                partes = [u["rua"] + (f", {u['numero']}" if u["numero"] else ""), u["complemento"], u["bairro"], cidade_uf]
                entrega = " · ".join(x for x in partes if x)[:255]

        pedido_id, criado = str(uuid.uuid4()), banco.agora()
        c.execute("INSERT INTO pedidos (id, usuario_id, total_centavos, pagamento, observacao, entrega, criado_em) VALUES (?, ?, ?, ?, ?, ?, ?)",
                  (pedido_id, ctx.usuario_id, total, pagamento, observacao or None, entrega, criado))
        c.executemany("INSERT INTO itens_pedido (pedido_id, produto_id, nome, preco_centavos, quantidade) VALUES (?, ?, ?, ?, ?)",
                      [(pedido_id, p["id"], p["nome"], p["preco_centavos"], q) for p, q in linhas])
    resposta = {
        "id": pedido_id, "total": total / 100, "pagamento": pagamento, "observacao": observacao, "entrega": entrega,
        "status": "recebido", "criadoEm": criado,
        "itens": [{"id": p["id"], "nome": p["nome"], "preco": p["preco_centavos"] / 100, "quantidade": q} for p, q in linhas],
    }
    if ctx.usuario_id:
        with banco.transacao() as c:
            quer_email = carregar_preferencias(c, ctx.usuario_id)["emailPedidos"]
        if quer_email:  # um problema no e-mail nunca derruba o pedido, que já foi gravado
            try:
                resposta["email"] = enviar_cobranca(ctx.usuario_id, resposta)
            except Erro as e:
                resposta["email"] = {"enviado": False, "destino": None, "modo": emails.modo(), "mensagem": e.mensagem}
    return 201, resposta


def carregar_pedidos(c, usuario_id, pedido_id=None):
    """Pedidos de um usuário no formato da API (mais recentes primeiro)."""
    if pedido_id:
        pedidos = c.execute("SELECT * FROM pedidos WHERE usuario_id = ? AND id = ?", (usuario_id, pedido_id)).fetchall()
    else:
        pedidos = c.execute("SELECT * FROM pedidos WHERE usuario_id = ? ORDER BY criado_em DESC LIMIT 50", (usuario_id,)).fetchall()
    itens = {}
    if pedidos:
        marcas = ",".join("?" * len(pedidos))
        for i in c.execute(f"SELECT * FROM itens_pedido WHERE pedido_id IN ({marcas}) ORDER BY id", [p["id"] for p in pedidos]):
            itens.setdefault(i["pedido_id"], []).append(
                {"id": i["produto_id"], "nome": i["nome"], "preco": i["preco_centavos"] / 100, "quantidade": i["quantidade"]})
    return [{"id": p["id"], "total": p["total_centavos"] / 100, "pagamento": p["pagamento"], "observacao": p["observacao"],
             "entrega": p["entrega"], "status": p["status"], "criadoEm": p["criado_em"], "itens": itens.get(p["id"], [])}
            for p in pedidos]


def pedidos_listar(ctx):
    ctx.exigir_login()  # cada pessoa vê apenas os próprios pedidos
    with banco.transacao() as c:
        return 200, carregar_pedidos(c, ctx.usuario_id)


# ---------- e-mail de cobrança (demonstrativo) ----------
EMAILS_POR_JANELA = 5
JANELA_EMAILS = 10 * 60
ESPERA_REENVIO = 60


def _iso_segundos_atras(segundos):
    return (datetime.now(timezone.utc) - timedelta(seconds=segundos)).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def enviar_cobranca(usuario_id, pedido):
    """Envia a cobrança demonstrativa do pedido para o e-mail da conta. Levanta Erro se passar do limite."""
    with banco.transacao() as c:
        u = c.execute("SELECT nome, email FROM usuarios WHERE id = ?", (usuario_id,)).fetchone()
        recentes = c.execute("SELECT COUNT(*) FROM emails_enviados WHERE usuario_id = ? AND criado_em > ?",
                             (usuario_id, _iso_segundos_atras(JANELA_EMAILS))).fetchone()[0]
        repetido = c.execute("SELECT 1 FROM emails_enviados WHERE usuario_id = ? AND pedido_id = ? AND status = 'enviado' AND criado_em > ?",
                             (usuario_id, pedido["id"], _iso_segundos_atras(ESPERA_REENVIO))).fetchone()
    if repetido:
        raise Erro(429, "A cobrança deste pedido acabou de ser enviada. Aguarde um minuto para reenviar.")
    if recentes >= EMAILS_POR_JANELA:
        raise Erro(429, "Você já recebeu vários e-mails há pouco. Aguarde alguns minutos para pedir outro.")

    assunto, texto, corpo_html = emails.montar_cobranca(u["nome"], pedido)
    r = emails.enviar(u["email"], assunto, texto, corpo_html, referencia=pedido["id"][:8])
    with banco.transacao() as c:  # registro de tudo que foi enviado (também serve de base para o limite)
        c.execute("INSERT INTO emails_enviados (usuario_id, pedido_id, destino, assunto, modo, status, erro, criado_em) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                  (usuario_id, pedido["id"], u["email"], assunto, r["modo"], "enviado" if r["ok"] else "falhou", r["erro"], banco.agora()))
    return {"enviado": r["ok"], "destino": u["email"], "modo": r["modo"], "mensagem": r["erro"]}


def pedido_cobranca(ctx):
    ctx.exigir_login()
    with banco.transacao() as c:
        encontrados = carregar_pedidos(c, ctx.usuario_id, ctx.parametros[0])
    if not encontrados:
        raise Erro(404, "Pedido não encontrado.")
    resultado = enviar_cobranca(ctx.usuario_id, encontrados[0])
    if not resultado["enviado"]:
        raise Erro(502, resultado["mensagem"])
    return 200, resultado


ROTAS = {
    ("GET", "/api/produtos"): produtos_listar,
    ("POST", "/api/pedidos"): pedido_criar,
    ("GET", "/api/pedidos"): pedidos_listar,
    ("POST", "/api/auth/cadastro"): cadastro,
    ("POST", "/api/auth/login"): login,
    ("POST", "/api/auth/logout"): logout,
    ("GET", "/api/perfil"): perfil_ver,
    ("PUT", "/api/perfil"): perfil_editar,
    ("DELETE", "/api/perfil"): perfil_excluir,
    ("PUT", "/api/perfil/senha"): perfil_senha,
    ("GET", "/api/perfil/preferencias"): preferencias_ver,
    ("PUT", "/api/perfil/preferencias"): preferencias_salvar,
}


ROTAS_COM_PARAMETRO = [
    ("POST", re.compile(r"^/api/pedidos/([0-9a-f-]{36})/cobranca$"), pedido_cobranca),
]


# ---------- servidor HTTP ----------
class Manipulador(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "MegaLanchonete"
    sys_version = ""

    def log_message(self, formato, *args):
        if not PRODUCAO and not str(args[0]).startswith(("GET /imagens", "GET /css", "GET /js")):
            sys.stderr.write("%s - %s\n" % (self.address_string(), formato % args))

    do_GET = lambda self: self._tratar("GET")
    do_POST = lambda self: self._tratar("POST")
    do_PUT = lambda self: self._tratar("PUT")
    do_DELETE = lambda self: self._tratar("DELETE")

    def _tratar(self, metodo):
        try:
            caminho = urlsplit(self.path).path
            corpo = self._ler_corpo()
            if caminho.startswith("/api/") or caminho == "/api":
                self._api(metodo, caminho, corpo)
            elif metodo == "GET":
                self._estatico(caminho)
            else:
                raise Erro(405, "Método não permitido.")
        except Erro as e:
            self._json(e.status, {"erro": e.mensagem})
        except Exception:
            traceback.print_exc()
            self._json(500, {"erro": "Erro interno no servidor. Tente novamente em instantes."})

    def _ler_corpo(self):
        try:
            tamanho = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            tamanho = 0
        if tamanho > LIMITE_CORPO:
            self.close_connection = True
            raise Erro(413, "Requisição muito grande.")
        return self.rfile.read(tamanho) if tamanho else b""

    def _api(self, metodo, caminho, bruto):
        token = None
        if "Cookie" in self.headers:
            try:
                morango = SimpleCookie(self.headers["Cookie"]).get(COOKIE)
                token = morango.value if morango else None
            except Exception:
                token = None
        usuario_id = None
        if token:
            with banco.transacao() as c:
                linha = c.execute("SELECT usuario_id FROM sessoes WHERE token_hash = ? AND expira_em > ?",
                                  (seguranca.hash_token(token), banco.agora())).fetchone()
                usuario_id = linha["usuario_id"] if linha else None

        corpo = {}
        if bruto:
            if "application/json" not in (self.headers.get("Content-Type") or ""):
                raise Erro(415, "Envie os dados em formato JSON.")
            try:
                corpo = json.loads(bruto.decode("utf-8"))
            except (ValueError, UnicodeDecodeError):
                raise Erro(400, "JSON inválido.")

        funcao, parametros = ROTAS.get((metodo, caminho.rstrip("/"))), ()
        if funcao is None:
            for m, padrao, f in ROTAS_COM_PARAMETRO:
                achou = padrao.match(caminho.rstrip("/"))
                if m == metodo and achou:
                    funcao, parametros = f, achou.groups()
                    break
        if funcao is None:
            existe = any(c == caminho.rstrip("/") for _, c in ROTAS)
            raise Erro(405 if existe else 404, "Método não permitido." if existe else "Rota da API não encontrada.")
        ctx = Contexto(corpo, usuario_id, self.client_address[0], token)
        ctx.parametros = parametros
        status, dados = funcao(ctx)
        self._json(status, dados, ctx.cookies)

    def _cabecalhos_seguros(self):
        self.send_header("Content-Security-Policy", CSP)
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "same-origin")

    def _json(self, status, dados, cookies=()):
        corpo = json.dumps(dados, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(corpo)))
        self.send_header("Cache-Control", "no-store")
        for cookie in cookies:
            self.send_header("Set-Cookie", cookie)
        self._cabecalhos_seguros()
        self.end_headers()
        self.wfile.write(corpo)

    def _estatico(self, caminho):
        relativo = unquote(caminho).lstrip("/") or "index.html"
        alvo = (PUBLICO / relativo).resolve()
        if alvo.is_dir():
            alvo = alvo / "index.html"
        if PUBLICO not in alvo.parents or not alvo.is_file():
            raise Erro(404, "Página não encontrada.")
        dados = alvo.read_bytes()
        tipo = mimetypes.guess_type(alvo.name)[0] or "application/octet-stream"
        if tipo.startswith("text/") or tipo in ("application/json", "image/svg+xml"):
            tipo += "; charset=utf-8"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(dados)))
        self.send_header("Cache-Control", "public, max-age=3600" if PRODUCAO else "no-cache")
        self._cabecalhos_seguros()
        self.end_headers()
        self.wfile.write(dados)


def principal():
    banco.iniciar()
    porta = int(os.environ.get("PORT") or 3000)
    host = os.environ.get("HOST") or "0.0.0.0"
    try:
        servidor = ThreadingHTTPServer((host, porta), Manipulador)
    except OSError as erro:
        print(f"Não foi possível usar a porta {porta}: {erro}\nFeche o outro programa ou use outra porta, por exemplo: PORT=3001 python servidor.py")
        sys.exit(1)
    servidor.daemon_threads = True
    print(f"Mega Lanchonete Espacial no ar: http://localhost:{porta}")
    print(f"Banco de dados: {banco.ARQUIVO}")
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor encerrado.")


if __name__ == "__main__":
    principal()
