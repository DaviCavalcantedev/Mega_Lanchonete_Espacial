"""Validação e limpeza dos dados recebidos do navegador."""
import re

EMAIL = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]{2,}$")
AVATARES = ["astronauta", "foguete", "planeta", "cometa", "satelite", "alienigena"]
PAGAMENTOS = ["Pix", "Cartão de crédito", "Cartão de débito", "Dinheiro"]
UFS = ["AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS", "MG", "PA", "PB", "PR",
       "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO"]


def texto(valor, maximo):
    if not isinstance(valor, str):
        return ""
    return " ".join(valor.split())[:maximo]


def validar_nome(valor):
    nome = texto(valor, 60)
    return nome if len(nome) >= 2 else None


def validar_email(valor):
    email = texto(valor, 120).lower()
    return email if EMAIL.match(email) else None


def validar_senha(valor):
    if not isinstance(valor, str) or not 8 <= len(valor) <= 72:
        return "A senha deve ter de 8 a 72 caracteres."
    if not re.search(r"[A-Za-z]", valor) or not re.search(r"\d", valor):
        return "A senha deve ter pelo menos uma letra e um número."
    return None


def validar_telefone(valor):
    """Devolve só os dígitos, '' se vazio ou None se inválido."""
    digitos = re.sub(r"\D", "", texto(valor, 20))
    if not digitos:
        return ""
    return digitos if 10 <= len(digitos) <= 11 else None


def validar_cep(valor):
    digitos = re.sub(r"\D", "", texto(valor, 9))
    if not digitos:
        return ""
    return f"{digitos[:5]}-{digitos[5:]}" if len(digitos) == 8 else None
