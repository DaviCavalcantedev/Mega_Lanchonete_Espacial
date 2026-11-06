"""Envio de e-mails com smtplib (biblioteca padrão).

Dois modos, escolhidos automaticamente:
  - smtp:      se SMTP_HOST estiver configurado, envia de verdade pelo servidor de e-mail indicado.
  - simulado:  sem configuração, grava o e-mail em dados/emails/*.eml e mostra um aviso no terminal.
               Assim o sistema funciona e pode ser testado sem nenhuma conta de e-mail.
"""
import os
import re
import smtplib
import ssl
import sys
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from email.utils import formataddr, formatdate, make_msgid
from html import escape

from . import banco

NOME_LOJA = "Mega Lanchonete Espacial"
BRASILIA = timezone(timedelta(hours=-3))


def modo():
    return "smtp" if os.environ.get("SMTP_HOST", "").strip() else "simulado"


def moeda(valor):
    return "R$ " + f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _data(iso):
    try:
        momento = datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(BRASILIA)
        return momento.strftime("%d/%m/%Y às %H:%M") + " (horário de Brasília)"
    except (ValueError, AttributeError):
        return ""


def montar_cobranca(nome, pedido):
    """Monta (assunto, texto, html) da mensagem de cobrança demonstrativa de um pedido."""
    codigo = pedido["id"][:8].upper()
    primeiro = (nome or "").split(" ")[0] or "cliente"
    total = moeda(pedido["total"])
    data = _data(pedido.get("criadoEm"))
    aviso = ("Esta mensagem faz parte de uma demonstração do sistema de e-mails da " + NOME_LOJA +
             ". Nenhuma cobrança real foi gerada: você não precisa pagar nada.")
    assunto = f"Cobrança do pedido {codigo} · {NOME_LOJA}"

    itens_txt = "\n".join(f"  {i['quantidade']}x {i['nome']}  ({moeda(i['preco'] * i['quantidade'])})" for i in pedido["itens"])
    extras = []
    if pedido.get("entrega"):
        extras.append(f"Entrega: {pedido['entrega']}")
    if pedido.get("observacao"):
        extras.append(f"Observações: {pedido['observacao']}")
    texto = (
        f"Olá, {primeiro}!\n\n"
        f"[DEMONSTRAÇÃO] {aviso}\n\n"
        f"Cobrança do pedido {codigo}\n"
        + (f"Feito em {data}\n" if data else "")
        + f"\nItens:\n{itens_txt}\n\n"
        f"Forma de pagamento: {pedido['pagamento']}\n"
        + ("\n".join(extras) + "\n" if extras else "")
        + f"Valor: {total}\n"
        f"Situação: aguardando pagamento (simulado)\n\n"
        f"Obrigado por pedir com a gente.\n{NOME_LOJA}\n"
    )

    linhas = "".join(
        f'<tr><td style="padding:6px 0;color:#1b2440">{i["quantidade"]}× {escape(i["nome"])}</td>'
        f'<td style="padding:6px 0;color:#1b2440;text-align:right;white-space:nowrap">{moeda(i["preco"] * i["quantidade"])}</td></tr>'
        for i in pedido["itens"])
    detalhes = "".join(f'<p style="margin:4px 0;color:#4a5578;font-size:14px">{escape(x)}</p>' for x in extras)
    html = f"""<!DOCTYPE html>
<html lang="pt-BR"><body style="margin:0;padding:24px;background:#eef1f8;font-family:Arial,Helvetica,sans-serif">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:560px;margin:0 auto;background:#ffffff;border-radius:12px;overflow:hidden">
<tr><td style="background:#0a1022;padding:22px 28px">
  <div style="font-size:18px;font-weight:bold;color:#e9eefc">Mega Lanchonete <span style="color:#ff6b2c">Espacial</span></div>
</td></tr>
<tr><td style="padding:26px 28px">
  <p style="margin:0 0 14px;font-size:16px;color:#1b2440">Olá, {escape(primeiro)}!</p>
  <p style="margin:0 0 20px;padding:12px 14px;background:#fff4ec;border-left:4px solid #ff6b2c;font-size:13px;color:#7a3a14"><b>Demonstração.</b> {escape(aviso)}</p>
  <h2 style="margin:0 0 4px;font-size:20px;color:#0a1022">Cobrança do pedido {codigo}</h2>
  <p style="margin:0 0 16px;color:#4a5578;font-size:14px">{escape(data)}</p>
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border-top:1px solid #dfe5f2;border-bottom:1px solid #dfe5f2;font-size:15px">{linhas}</table>
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin-top:14px"><tr>
    <td style="font-size:15px;color:#4a5578">Forma de pagamento: {escape(pedido["pagamento"])}</td>
    <td style="text-align:right;font-size:22px;font-weight:bold;color:#0a1022">{total}</td></tr></table>
  <div style="margin-top:10px">{detalhes}</div>
  <p style="margin:18px 0 0;font-size:14px;color:#1b2440"><b>Situação:</b> aguardando pagamento (simulado)</p>
</td></tr>
<tr><td style="padding:16px 28px;background:#f6f8fc;color:#7b86a6;font-size:12px">Obrigado por pedir com a gente. {NOME_LOJA}</td></tr>
</table></body></html>"""
    return assunto, texto, html


def _mensagem(destino, assunto, texto, html):
    remetente = os.environ.get("SMTP_REMETENTE") or os.environ.get("SMTP_USUARIO") or "nao-responda@mega-lanchonete.local"
    msg = EmailMessage()
    msg["Subject"] = assunto
    msg["From"] = formataddr((NOME_LOJA, remetente))
    msg["To"] = destino
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid(domain="mega-lanchonete.local")
    msg.set_content(texto)
    msg.add_alternative(html, subtype="html")
    return msg


def _enviar_smtp(msg):
    host = os.environ["SMTP_HOST"].strip()
    seguranca = (os.environ.get("SMTP_SEGURANCA") or "starttls").strip().lower()
    porta_padrao = {"ssl": 465, "nenhuma": 25}.get(seguranca, 587)
    porta = int(os.environ.get("SMTP_PORT") or porta_padrao)
    contexto = ssl.create_default_context()
    servidor = smtplib.SMTP_SSL(host, porta, timeout=10, context=contexto) if seguranca == "ssl" else smtplib.SMTP(host, porta, timeout=10)
    with servidor:
        servidor.ehlo()
        if seguranca == "starttls":
            servidor.starttls(context=contexto)
            servidor.ehlo()
        usuario = os.environ.get("SMTP_USUARIO", "").strip()
        if usuario:
            servidor.login(usuario, os.environ.get("SMTP_SENHA", ""))
        servidor.send_message(msg)


def _salvar_simulado(msg, referencia):
    pasta = banco.ARQUIVO.parent / "emails"
    pasta.mkdir(parents=True, exist_ok=True)
    nome = datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + re.sub(r"[^A-Za-z0-9]", "", referencia or "email") + ".eml"
    (pasta / nome).write_bytes(bytes(msg))
    print(f"[e-mail simulado] para {msg['To']}: salvo em {pasta / nome}")


def enviar(destino, assunto, texto, html, referencia=""):
    """Envia (ou simula) um e-mail. Nunca levanta exceção: devolve {ok, modo, erro}."""
    atual = modo()
    msg = _mensagem(destino, assunto, texto, html)
    try:
        if atual == "smtp":
            _enviar_smtp(msg)
        else:
            _salvar_simulado(msg, referencia)
        return {"ok": True, "modo": atual, "erro": None}
    except smtplib.SMTPAuthenticationError:
        erro = "O servidor de e-mail recusou o usuário ou a senha. Confira SMTP_USUARIO e SMTP_SENHA no arquivo .env."
    except smtplib.SMTPRecipientsRefused:
        erro = "O servidor de e-mail recusou o endereço de destino."
    except (smtplib.SMTPException, OSError) as e:
        print(f"[e-mail] falha ao enviar: {type(e).__name__}: {e}", file=sys.stderr)
        erro = "Não foi possível conectar ao servidor de e-mail. Confira as configurações SMTP_* e a conexão com a internet."
    return {"ok": False, "modo": atual, "erro": erro}
