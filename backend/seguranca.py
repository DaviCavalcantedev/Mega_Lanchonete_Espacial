"""Senhas e sessões, usando apenas a biblioteca padrão do Python."""
import hashlib
import hmac
import os
import secrets

_N, _R, _P = 2 ** 14, 8, 1


def hash_senha(senha: str) -> str:
    sal = os.urandom(16)
    resumo = hashlib.scrypt(senha.encode("utf-8"), salt=sal, n=_N, r=_R, p=_P, dklen=32)
    return f"scrypt${_N}${_R}${_P}${sal.hex()}${resumo.hex()}"


def confere_senha(senha: str, guardado: str) -> bool:
    try:
        _, n, r, p, sal, resumo = guardado.split("$")
        esperado = bytes.fromhex(resumo)
        calculado = hashlib.scrypt(
            senha.encode("utf-8"), salt=bytes.fromhex(sal), n=int(n), r=int(r), p=int(p), dklen=len(esperado)
        )
        return hmac.compare_digest(calculado, esperado)
    except (ValueError, TypeError):
        return False


# Usado para que o login demore o mesmo tempo quando o e-mail não existe.
HASH_FALSO = hash_senha("senha-inexistente-1")


def novo_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """O banco guarda só o hash do token: quem ler o arquivo não consegue usar as sessões."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
