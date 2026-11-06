"""Banco de dados SQLite: um único arquivo, sem servidor para instalar ou iniciar."""
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from .produtos_seed import PRODUTOS

RAIZ = Path(__file__).resolve().parent.parent
ARQUIVO = Path(os.environ.get("DB_ARQUIVO") or RAIZ / "dados" / "mega_lanchonete.sqlite3")

SCHEMA = """
CREATE TABLE IF NOT EXISTS usuarios (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    nome          TEXT NOT NULL,
    email         TEXT NOT NULL UNIQUE COLLATE NOCASE,
    senha_hash    TEXT NOT NULL,
    telefone      TEXT,
    avatar        TEXT NOT NULL DEFAULT 'astronauta',
    cep           TEXT,
    rua           TEXT,
    numero        TEXT,
    complemento   TEXT,
    bairro        TEXT,
    cidade        TEXT,
    uf            TEXT,
    criado_em     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sessoes (
    token_hash  TEXT PRIMARY KEY,
    usuario_id  INTEGER NOT NULL REFERENCES usuarios (id) ON DELETE CASCADE,
    expira_em   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS preferencias (
    usuario_id  INTEGER PRIMARY KEY REFERENCES usuarios (id) ON DELETE CASCADE,
    dados       TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS produtos (
    id               INTEGER PRIMARY KEY,
    nome             TEXT NOT NULL,
    preco_centavos   INTEGER NOT NULL,
    categoria        TEXT NOT NULL,
    descricao        TEXT NOT NULL,
    imagem           INTEGER NOT NULL,
    ativo            INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS pedidos (
    id               TEXT PRIMARY KEY,
    usuario_id       INTEGER REFERENCES usuarios (id) ON DELETE SET NULL,
    total_centavos   INTEGER NOT NULL,
    pagamento        TEXT NOT NULL,
    observacao       TEXT,
    entrega          TEXT,
    status           TEXT NOT NULL DEFAULT 'recebido',
    criado_em        TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS itens_pedido (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    pedido_id        TEXT NOT NULL REFERENCES pedidos (id) ON DELETE CASCADE,
    produto_id       INTEGER NOT NULL,
    nome             TEXT NOT NULL,
    preco_centavos   INTEGER NOT NULL,
    quantidade       INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS emails_enviados (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario_id  INTEGER REFERENCES usuarios (id) ON DELETE CASCADE,
    pedido_id   TEXT,
    destino     TEXT NOT NULL,
    assunto     TEXT NOT NULL,
    modo        TEXT NOT NULL,
    status      TEXT NOT NULL,
    erro        TEXT,
    criado_em   TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_emails_usuario ON emails_enviados (usuario_id, criado_em);
CREATE INDEX IF NOT EXISTS idx_produtos_categoria ON produtos (categoria);
CREATE INDEX IF NOT EXISTS idx_pedidos_usuario ON pedidos (usuario_id, criado_em);
CREATE INDEX IF NOT EXISTS idx_itens_pedido ON itens_pedido (pedido_id);
CREATE INDEX IF NOT EXISTS idx_sessoes_expira ON sessoes (expira_em);
"""


def agora():
    """Data e hora atuais em UTC, no formato ISO que o navegador entende."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def conectar():
    conexao = sqlite3.connect(ARQUIVO, timeout=10)
    conexao.row_factory = sqlite3.Row
    conexao.execute("PRAGMA foreign_keys = ON")
    return conexao


@contextmanager
def transacao():
    """Abre uma conexão; confirma as alterações no fim ou desfaz se der erro."""
    conexao = conectar()
    try:
        yield conexao
        conexao.commit()
    except BaseException:
        conexao.rollback()
        raise
    finally:
        conexao.close()


def iniciar():
    """Cria a pasta, o arquivo do banco, as tabelas e o catálogo inicial (se estiver vazio)."""
    ARQUIVO.parent.mkdir(parents=True, exist_ok=True)
    conexao = conectar()
    try:
        conexao.execute("PRAGMA journal_mode = WAL")
        conexao.executescript(SCHEMA)
        conexao.execute("DELETE FROM sessoes WHERE expira_em < ?", (agora(),))
        total = conexao.execute("SELECT COUNT(*) FROM produtos").fetchone()[0]
        if total == 0:
            conexao.executemany(
                "INSERT INTO produtos (id, nome, preco_centavos, categoria, descricao, imagem) VALUES (?, ?, ?, ?, ?, ?)",
                [(p["id"], p["nome"], round(p["preco"] * 100), p["categoria"], p["descricao"], p["imagem"]) for p in PRODUTOS],
            )
            print(f"Catálogo inicial gravado no banco ({len(PRODUTOS)} produtos).")
        conexao.commit()
    finally:
        conexao.close()
