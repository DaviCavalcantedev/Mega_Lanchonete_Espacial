# Mega Lanchonete Espacial

Site de pedidos com tema espacial: cardápio, carrinho com quantidades, pagamento demonstrativo, contas de usuário e histórico de pedidos.
Servidor e API em **Python** com banco de dados **SQLite** (um único arquivo, nada para instalar ou iniciar).

## Recursos

- Cardápio com 5 categorias, carregado do banco
- Cadastro e login (senha criptografada com scrypt, sessão em cookie `HttpOnly`)
- Perfil: avatar, dados pessoais, endereço de entrega, troca de senha, exclusão de conta e histórico de pedidos
- Configurações: cor de destaque, tamanho do texto, fundo estrelado, redução de animações, modo compacto, descrições visíveis, pagamento preferido e recibo na tela (salvas na conta ou, para visitantes, no navegador)
- Pedidos gravados no banco; o preço é sempre recalculado no servidor
- E-mail de cobrança demonstrativa de cada pedido, enviado ao e-mail da conta (sem valor real, sem links), com botão para reenviar no histórico

## Como rodar

Requisito: Python 3.9 ou superior. Não há nada para instalar (só biblioteca padrão).

```bash
python servidor.py        # Windows: py servidor.py
```

Acesse http://localhost:3000

Na primeira execução o servidor cria a pasta `dados/`, o arquivo do banco (`dados/mega_lanchonete.sqlite3`), as tabelas e o catálogo de 30 produtos.

### E-mail de cobrança (demonstração)

Quem tem conta recebe, a cada pedido, um e-mail "Cobrança do pedido XXXXXXXX" com os itens, o valor e a forma de pagamento. É só uma demonstração: o texto avisa que nenhuma cobrança real foi gerada e não há links nem dados de pagamento. No histórico de pedidos (Perfil > Pedidos) há o botão **Enviar cobrança por e-mail** para reenviar, e em Configurações dá para desligar o envio automático.

- **Sem configurar nada (modo simulado):** o e-mail não sai da sua máquina. Ele é salvo em `dados/emails/` como arquivo `.eml` (abra com o Outlook, Thunderbird ou o app de e-mail do computador) e o terminal mostra um aviso.
- **Envio de verdade (modo SMTP):** copie `.env.example` para `.env`, remova o `#` das linhas `SMTP_*` e preencha. Com Gmail é preciso ativar a verificação em duas etapas e criar uma [senha de app](https://myaccount.google.com/apppasswords); a senha normal da conta não funciona. Reinicie o servidor depois de editar o `.env`.

O e-mail só é enviado para o endereço da própria conta e há limites (5 e-mails a cada 10 minutos por conta e 1 minuto entre reenvios do mesmo pedido). Se o servidor de e-mail falhar, o pedido continua sendo registrado normalmente e o histórico de envios fica na tabela `emails_enviados`.

O endereço de e-mail do cadastro não é verificado (não há link de confirmação).

### Configuração opcional (variáveis de ambiente ou arquivo `.env`)

| Variável | Padrão | Para quê |
|---|---|---|
| `PORT` | `3000` | Porta do servidor |
| `HOST` | `0.0.0.0` | Endereço de escuta |
| `DB_ARQUIVO` | `dados/mega_lanchonete.sqlite3` | Local do arquivo do banco |
| `MLE_PRODUCAO` | (vazio) | `true` marca o cookie como `Secure` (use com HTTPS) |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_SEGURANCA`, `SMTP_USUARIO`, `SMTP_SENHA`, `SMTP_REMETENTE` | (vazio) | Envio real de e-mail (veja acima). `SMTP_SEGURANCA`: `starttls` (padrão), `ssl` ou `nenhuma` |

Exemplo: `PORT=3001 python servidor.py` (Windows PowerShell: `$env:PORT=3001; py servidor.py`).

## Estrutura

```
servidor.py          servidor web + rotas da API
backend/banco.py     SQLite: tabelas, conexão e catálogo inicial
backend/seguranca.py hash de senha e sessões
backend/emails.py    montagem e envio de e-mails (SMTP ou simulado)
backend/config.py    leitura do arquivo .env
backend/validacao.py validação dos dados recebidos
backend/produtos_seed.py  catálogo inicial (editável)
public/              site (index.html, css/, js/, imagens/)
dados/               banco de dados e e-mails simulados (criado sozinho, fora do Git)
```

## Rotas da API

| Método | Rota | Descrição | Login |
|---|---|---|---|
| GET | `/api/produtos` | Catálogo | não |
| POST | `/api/pedidos` | Cria pedido: `{ itens: [{ id, quantidade }], pagamento, observacao }` | opcional |
| GET | `/api/pedidos` | Histórico do usuário | sim |
| POST | `/api/pedidos/<id>/cobranca` | Reenvia a cobrança demonstrativa por e-mail | sim |
| POST | `/api/auth/cadastro` | `{ nome, email, senha }` | não |
| POST | `/api/auth/login` | `{ email, senha }` | não |
| POST | `/api/auth/logout` | Encerra a sessão | não |
| GET | `/api/perfil` | Dados, preferências e total de pedidos | sim |
| PUT | `/api/perfil` | Atualiza dados e endereço | sim |
| PUT | `/api/perfil/senha` | `{ senhaAtual, novaSenha }` | sim |
| GET / PUT | `/api/perfil/preferencias` | Lê e grava preferências | sim |
| DELETE | `/api/perfil` | Exclui a conta: `{ senha }` | sim |

## Segurança

Senhas com scrypt e sal individual, consultas parametrizadas, sessões guardadas no banco apenas como hash, política de segurança de conteúdo (CSP) e demais cabeçalhos, limite de tentativas em login e cadastro, cookie `SameSite=Lax`, proteção contra acesso a arquivos fora de `public/`.

## Observações

- O pagamento é demonstrativo: nenhuma cobrança real é feita.
- Para ver o banco: abra `dados/mega_lanchonete.sqlite3` com o [DB Browser for SQLite](https://sqlitebrowser.org/) ou use `sqlite3` no terminal.
- Para zerar tudo, pare o servidor e apague a pasta `dados/`.
- Para alterar o cardápio de um banco já criado, edite a tabela `produtos` (o arquivo `produtos_seed.py` só vale na primeira execução).

## Publicação

O servidor usa a variável `PORT`, adequado para Render, Railway e similares. Atenção: o SQLite precisa de disco persistente; em hospedagens sem disco persistente os dados são perdidos a cada reinício. Para uso real em produção com muitos acessos, considere migrar para PostgreSQL.
