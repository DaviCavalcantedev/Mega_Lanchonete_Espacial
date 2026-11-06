/* Mega Lanchonete Espacial: interface do site.
   Todos os textos vindos do servidor entram na página via textContent (sem innerHTML). */
(() => {
  "use strict";

  // ---------- Utilitários ----------
  const $ = (seletor, raiz = document) => raiz.querySelector(seletor);
  const $$ = (seletor, raiz = document) => [...raiz.querySelectorAll(seletor)];
  const NS = "http://www.w3.org/2000/svg";
  const dinheiro = valor => Number(valor).toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
  const maxQtd = 20;

  function el(tag, atributos = {}, ...filhos) {
    const no = document.createElement(tag);
    for (const [chave, valor] of Object.entries(atributos)) {
      if (valor == null || valor === false) continue;
      if (chave === "class") no.className = valor;
      else if (chave === "texto") no.textContent = valor;
      else if (chave.startsWith("on")) no.addEventListener(chave.slice(2), valor);
      else no.setAttribute(chave, valor === true ? "" : valor);
    }
    for (const filho of filhos.flat()) if (filho != null && filho !== false) no.append(filho);
    return no;
  }
  function icone(id) {
    const svg = document.createElementNS(NS, "svg");
    const uso = document.createElementNS(NS, "use");
    uso.setAttribute("href", "#" + id);
    svg.append(uso);
    return svg;
  }
  const guardar = (chave, valor) => { try { localStorage.setItem(chave, JSON.stringify(valor)); } catch { /* armazenamento indisponível */ } };
  const ler = chave => { try { return JSON.parse(localStorage.getItem(chave)); } catch { return null; } };

  async function api(caminho, { metodo = "GET", corpo } = {}) {
    const opcoes = { method: metodo, credentials: "same-origin", headers: {} };
    if (metodo !== "GET") { opcoes.headers["Content-Type"] = "application/json"; opcoes.body = JSON.stringify(corpo ?? {}); }
    let resposta;
    try { resposta = await fetch("/api" + caminho, opcoes); }
    catch { throw new Error("Não foi possível falar com o servidor. Verifique sua conexão."); }
    let dados = null;
    try { dados = await resposta.json(); } catch { /* resposta sem corpo */ }
    if (!resposta.ok) {
      const erro = new Error((dados && dados.erro) || "Algo deu errado. Tente novamente.");
      erro.status = resposta.status;
      throw erro;
    }
    return dados;
  }

  function aviso(mensagem, tipo = "") {
    const caixa = el("div", { class: "toast " + tipo, role: tipo === "erro" ? "alert" : "status" }, mensagem);
    $("#toasts").append(caixa);
    setTimeout(() => caixa.remove(), 4800);
  }

  const modalEl = $("#modal");
  function abrirModal(...conteudo) {
    modalEl.replaceChildren(el("div", { class: "modal-corpo" }, conteudo));
    if (!modalEl.open) modalEl.showModal();
  }
  function fecharModal() { if (modalEl.open) modalEl.close(); }
  modalEl.addEventListener("click", evento => { if (evento.target === modalEl) fecharModal(); });

  // ---------- Dados fixos ----------
  const CATEGORIAS = [
    { id: "hamburguer", nome: "Hambúrgueres" },
    { id: "pizza", nome: "Pizzas" },
    { id: "aperitivos", nome: "Aperitivos" },
    { id: "sobremesas", nome: "Sobremesas" },
    { id: "bebidas", nome: "Bebidas" }
  ];
  const nomeCategoria = id => (CATEGORIAS.find(c => c.id === id) || {}).nome || id;
  const PAGAMENTOS = [
    { nome: "Pix", detalhe: "Pagamento instantâneo" },
    { nome: "Cartão de crédito", detalhe: "Crédito" },
    { nome: "Cartão de débito", detalhe: "Débito" },
    { nome: "Dinheiro", detalhe: "Pagamento em dinheiro" }
  ];
  const AVATARES = [
    ["astronauta", "Astronauta"], ["foguete", "Foguete"], ["planeta", "Planeta"],
    ["cometa", "Cometa"], ["satelite", "Satélite"], ["alienigena", "Alienígena"]
  ];
  const TEMAS = [["laranja", "Laranja solar", "#ff6b2c"], ["ciano", "Ciano polar", "#36d1e8"], ["ambar", "Âmbar estelar", "#f4b73c"]];
  const UFS = ["AC","AL","AP","AM","BA","CE","DF","ES","GO","MA","MT","MS","MG","PA","PB","PR","PE","PI","RJ","RN","RS","RO","RR","SC","SP","SE","TO"];
  const PADRAO = { tema: "laranja", estrelas: true, reduzirAnimacoes: false, descricoesVisiveis: false, tamanhoTexto: "normal", compacto: false, pagamentoPadrao: "", notificacoes: true, emailPedidos: true };

  // ---------- Estado ----------
  let produtos = [];
  let categoriaAtual = "hamburguer";
  let carrinho = new Map(); // id -> quantidade
  let usuario = null;
  let totalPedidos = 0;
  let prefs = { ...PADRAO, ...(ler("mle_prefs") || {}) };
  const slots = new Map(); // id -> elemento do cartão com os botões de quantidade

  const produtoPorId = id => produtos.find(p => p.id === id);
  const itensDoCarrinho = () => [...carrinho.entries()].map(([id, qtd]) => ({ produto: produtoPorId(id), qtd })).filter(i => i.produto);
  const totalCarrinho = () => itensDoCarrinho().reduce((s, i) => s + Math.round(i.produto.preco * 100) * i.qtd, 0) / 100;
  const qtdCarrinho = () => itensDoCarrinho().reduce((s, i) => s + i.qtd, 0);
  const imagemDe = p => "imagens/lanche-" + String(p.imagem).padStart(2, "0") + ".jpg";
  const plural = (n, um, varios) => n + " " + (n === 1 ? um : varios);

  // ---------- Fundo estrelado ----------
  const tela = $("#estrelas");
  const ctx = tela.getContext("2d");
  const reduzMovimentoSO = window.matchMedia("(prefers-reduced-motion: reduce)");
  let estrelas = [], largura = 0, altura = 0, quadro = 0;

  function medirCeu() {
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    largura = window.innerWidth; altura = window.innerHeight;
    tela.width = largura * dpr; tela.height = altura * dpr;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    const total = Math.min(260, Math.round((largura * altura) / 9000));
    estrelas = Array.from({ length: total }, () => ({
      x: Math.random() * largura, y: Math.random() * altura,
      r: Math.random() * 1.15 + 0.25, v: Math.random() * 0.1 + 0.015, f: Math.random() * 6.28
    }));
    desenharCeu(0, false);
  }
  function desenharCeu(t, mover) {
    ctx.clearRect(0, 0, largura, altura);
    for (const e of estrelas) {
      if (mover) { e.y += e.v; if (e.y > altura) { e.y = 0; e.x = Math.random() * largura; } }
      const brilho = 0.35 + 0.5 * Math.pow(Math.sin(t / 1400 + e.f), 2);
      ctx.fillStyle = "rgba(233,238,252," + brilho.toFixed(2) + ")";
      ctx.beginPath(); ctx.arc(e.x, e.y, e.r, 0, 6.2832); ctx.fill();
    }
  }
  function ciclo(t) { desenharCeu(t, true); quadro = requestAnimationFrame(ciclo); }
  function atualizarCeu() {
    cancelAnimationFrame(quadro); quadro = 0;
    if (!prefs.estrelas) return;
    if (!prefs.reduzirAnimacoes && !reduzMovimentoSO.matches && !document.hidden) quadro = requestAnimationFrame(ciclo);
    else desenharCeu(0, false);
  }
  window.addEventListener("resize", medirCeu);
  document.addEventListener("visibilitychange", atualizarCeu);
  reduzMovimentoSO.addEventListener("change", atualizarCeu);

  // ---------- Preferências ----------
  let temporizadorPrefs = 0;
  function aplicarPrefs() {
    document.body.dataset.tema = prefs.tema;
    document.documentElement.dataset.texto = prefs.tamanhoTexto;
    document.body.classList.toggle("sem-estrelas", !prefs.estrelas);
    document.body.classList.toggle("reduzir-animacoes", prefs.reduzirAnimacoes);
    document.body.classList.toggle("descricoes-visiveis", prefs.descricoesVisiveis);
    document.body.classList.toggle("compacto", prefs.compacto);
    atualizarCeu();
    sincronizarControlesConfig();
    escolherPagamentoPadrao();
  }
  function salvarPrefs() {
    guardar("mle_prefs", prefs);
    if (!usuario) return;
    clearTimeout(temporizadorPrefs);
    temporizadorPrefs = setTimeout(async () => {
      try { await api("/perfil/preferencias", { metodo: "PUT", corpo: prefs }); }
      catch (erro) { if (erro.status === 401) sessaoExpirada(); else aviso("Não foi possível salvar as preferências na conta.", "erro"); }
    }, 400);
  }
  function mudarPref(chave, valor) { prefs = { ...prefs, [chave]: valor }; aplicarPrefs(); salvarPrefs(); }

  // ---------- Navegação ----------
  const ABAS = ["cardapio", "pedido", "pagamento", "perfil", "configuracoes"];
  function irPara(aba, { foco = true } = {}) {
    if (!ABAS.includes(aba)) aba = "cardapio";
    $$(".aba").forEach(s => s.classList.toggle("ativa", s.id === aba));
    $$(".navegacao button").forEach(b => b.classList.toggle("ativo", b.dataset.aba === aba));
    if (location.hash !== "#" + aba) history.replaceState(null, "", "#" + aba);
    if (foco) { window.scrollTo({ top: 0 }); $("#conteudo").focus({ preventScroll: true }); }
    if (aba === "pagamento") desenharEntrega();
    if (aba === "perfil" && usuario && $("#psub-historico").classList.contains("ativa")) carregarHistorico();
    atualizarBarraMovel();
  }
  document.addEventListener("click", evento => {
    const alvo = evento.target.closest("[data-aba], [data-ir]");
    if (!alvo) return;
    irPara(alvo.dataset.aba || alvo.dataset.ir);
  });
  window.addEventListener("hashchange", () => irPara(location.hash.slice(1), { foco: false }));

  // ---------- Cardápio ----------
  function desenharCategorias() {
    const caixa = $("#categorias");
    caixa.replaceChildren(...CATEGORIAS.map(c => {
      const total = produtos.filter(p => p.categoria === c.id).length;
      return el("button", {
        type: "button", class: c.id === categoriaAtual ? "ativo" : "", "aria-pressed": String(c.id === categoriaAtual),
        onclick: () => { categoriaAtual = c.id; desenharCategorias(); desenharCatalogo(); }
      }, c.nome, el("small", { texto: String(total) }));
    }));
  }

  function desenharCatalogo() {
    const grade = $("#grade-produtos");
    slots.clear();
    const lista = produtos.filter(p => p.categoria === categoriaAtual);
    if (!lista.length) { grade.replaceChildren(el("p", { class: "suave", texto: "Nenhum item nesta categoria." })); return; }
    grade.replaceChildren(...lista.map(produto => {
      const imagem = el("img", { src: imagemDe(produto), alt: produto.nome, loading: "lazy", width: "640", height: "480" });
      const slot = el("div", { class: "acao-slot" });
      slots.set(produto.id, slot);
      const cartao = el("article", { class: "cartao" },
        el("div", { class: "foto" }, el("span", { class: "etiqueta", texto: nomeCategoria(produto.categoria) }), imagem),
        el("div", { class: "cartao-corpo" },
          el("h3", { texto: produto.nome }),
          el("p", { class: "cartao-desc", texto: produto.descricao }),
          el("div", { class: "cartao-rodape" }, el("span", { class: "preco", texto: dinheiro(produto.preco) }), slot)
        )
      );
      pintarSlot(produto.id, cartao);
      return cartao;
    }));
  }

  function passo(id, qtd, cartao) {
    return el("div", { class: "passo", role: "group", "aria-label": "Quantidade" },
      el("button", { type: "button", "aria-label": "Diminuir quantidade", onclick: () => mudarQtd(id, -1) }, icone("i-menos")),
      el("output", { texto: String(qtd), "aria-live": "polite" }),
      el("button", { type: "button", "aria-label": "Aumentar quantidade", disabled: qtd >= maxQtd, onclick: () => mudarQtd(id, 1, cartao) }, icone("i-mais"))
    );
  }
  function pintarSlot(id, cartao) {
    const slot = slots.get(id);
    if (!slot) return;
    const qtd = carrinho.get(id) || 0;
    const cartaoRef = cartao || slot.closest(".cartao");
    slot.replaceChildren(qtd === 0
      ? el("button", { type: "button", class: "btn btn-acento", onclick: () => mudarQtd(id, 1, cartaoRef) }, icone("i-mais"), "Adicionar")
      : passo(id, qtd, cartaoRef));
  }

  // ---------- Carrinho ----------
  function mudarQtd(id, delta, cartao) {
    const nova = Math.max(0, Math.min(maxQtd, (carrinho.get(id) || 0) + delta));
    if (delta > 0 && cartao) voarAteOPedido(cartao);
    if (nova === 0) carrinho.delete(id); else carrinho.set(id, nova);
    atualizarCarrinho();
  }
  function removerItem(id) { carrinho.delete(id); atualizarCarrinho(); }

  function voarAteOPedido(cartao) {
    const foto = $(".foto img", cartao);
    const destino = $('.navegacao button[data-aba="pedido"]');
    if (!foto || !destino || prefs.reduzirAnimacoes || reduzMovimentoSO.matches) return;
    const de = foto.getBoundingClientRect(), ate = destino.getBoundingClientRect();
    const fantasma = el("img", { src: foto.src, alt: "", class: "lanche-voo" });
    fantasma.style.left = de.left + de.width / 2 - 32 + "px";
    fantasma.style.top = de.top + de.height / 2 - 32 + "px";
    document.body.append(fantasma);
    requestAnimationFrame(() => requestAnimationFrame(() => {
      fantasma.style.transform = "translate(" + (ate.left + ate.width / 2 - (de.left + de.width / 2)) + "px," + (ate.top + ate.height / 2 - (de.top + de.height / 2)) + "px) scale(.2)";
      fantasma.style.opacity = "0.15";
    }));
    setTimeout(() => fantasma.remove(), 750);
  }

  function atualizarBarraMovel() {
    const aba = (location.hash.slice(1) || "cardapio");
    $("#barra-pedido").hidden = qtdCarrinho() === 0 || aba === "pedido" || aba === "pagamento";
  }

  function atualizarCarrinho() {
    const itens = itensDoCarrinho();
    const qtd = qtdCarrinho(), total = totalCarrinho();
    guardar("mle_carrinho", [...carrinho.entries()]);

    // resumo lateral, selo e barra móvel
    $("#resumo-qtd").textContent = qtd ? plural(qtd, "item", "itens") : "Pedido vazio";
    $("#resumo-total").textContent = dinheiro(total);
    $("#resumo-ir").disabled = qtd === 0;
    const selo = $("#selo-qtd");
    selo.hidden = qtd === 0; selo.textContent = String(qtd);
    $("#barra-qtd").textContent = plural(qtd, "item", "itens");
    $("#barra-total").textContent = dinheiro(total);
    atualizarBarraMovel();

    // cartões do cardápio
    for (const id of slots.keys()) pintarSlot(id);

    // página do pedido
    const lista = $("#lista-pedido");
    lista.replaceChildren(...itens.map(({ produto, qtd: q }) => el("li", {},
      el("img", { src: imagemDe(produto), alt: "", width: "64", height: "64" }),
      el("div", {}, el("div", { class: "item-nome", texto: produto.nome }), el("div", { class: "item-unit", texto: dinheiro(produto.preco) + " cada" })),
      el("div", { class: "item-direita" }, passo(produto.id, q, null), el("span", { class: "item-sub", texto: dinheiro(produto.preco * q) })),
      el("button", { type: "button", class: "icone-btn", "aria-label": "Remover " + produto.nome, onclick: () => removerItem(produto.id) }, icone("i-lixo"))
    )));
    $("#pedido-vazio").hidden = qtd > 0;
    $("#pedido-totais").hidden = qtd === 0;
    $("#pedido-acoes").hidden = qtd === 0;
    $("#pedido-itens").textContent = String(qtd);
    $("#pedido-total").textContent = dinheiro(total);

    // página de pagamento
    $("#total-pagamento").textContent = dinheiro(total);
    $("#mini-lista").replaceChildren(...itens.map(({ produto, qtd: q }) =>
      el("li", {}, el("span", { texto: q + "× " + produto.nome }), el("span", { texto: dinheiro(produto.preco * q) }))));
    $("#confirmar").disabled = qtd === 0;
  }

  $("#limpar").addEventListener("click", () => {
    abrirModal(
      el("h3", { texto: "Limpar o pedido?" }),
      el("p", { texto: "Todos os itens serão removidos do seu pedido." }),
      el("div", { class: "acoes" },
        el("button", { type: "button", class: "btn btn-contorno", onclick: fecharModal }, "Cancelar"),
        el("button", { type: "button", class: "btn btn-perigo", onclick: () => { carrinho.clear(); atualizarCarrinho(); fecharModal(); } }, "Limpar pedido"))
    );
  });
  $("#resumo-ir").addEventListener("click", () => irPara("pedido"));

  // ---------- Pagamento ----------
  function montarPagamentos() {
    $("#opcoes-pagamento").replaceChildren(...PAGAMENTOS.map(p => el("label", { class: "opcao" },
      el("input", { type: "radio", name: "pagamento", value: p.nome }),
      el("span", { class: "opcao-marca" }),
      el("span", {}, el("b", { texto: p.nome }), el("small", { texto: p.detalhe }))
    )));
    const select = $("#cfg-pagamento");
    PAGAMENTOS.forEach(p => select.append(el("option", { value: p.nome, texto: p.nome })));
  }
  function escolherPagamentoPadrao() {
    const marcado = $('input[name="pagamento"]:checked');
    if (marcado || !prefs.pagamentoPadrao) return;
    const alvo = $$('input[name="pagamento"]').find(i => i.value === prefs.pagamentoPadrao);
    if (alvo) alvo.checked = true;
  }

  function textoEndereco(e) {
    if (!e || !e.rua) return "";
    return [e.rua + (e.numero ? ", " + e.numero : ""), e.complemento, e.bairro, [e.cidade, e.uf].filter(Boolean).join("/")].filter(Boolean).join(" · ");
  }
  function desenharEntrega() {
    const caixa = $("#entrega-info");
    if (usuario && usuario.endereco.rua) {
      caixa.replaceChildren(el("b", { texto: "Endereço de entrega" }), textoEndereco(usuario.endereco),
        el("div", {}, el("button", { type: "button", onclick: () => { irPara("perfil"); abrirSubPerfil("entrega"); } }, "Alterar endereço")));
    } else if (usuario) {
      caixa.replaceChildren(el("b", { texto: "Endereço de entrega" }), "Você ainda não salvou um endereço.",
        el("div", {}, el("button", { type: "button", onclick: () => { irPara("perfil"); abrirSubPerfil("entrega"); } }, "Adicionar endereço")));
    } else {
      caixa.replaceChildren(el("b", { texto: "Endereço de entrega" }), "Entre na sua conta para salvar o endereço e acompanhar o pedido no histórico.",
        el("div", {}, el("button", { type: "button", onclick: () => irPara("perfil") }, "Entrar ou criar conta")));
    }

    const aviso_email = $("#email-info");
    aviso_email.hidden = !usuario;
    if (usuario) {
      aviso_email.replaceChildren(el("b", { texto: "Cobrança por e-mail" }),
        prefs.emailPedidos
          ? "Ao confirmar, enviaremos a cobrança (demonstrativa, sem valor real) para " + usuario.email + "."
          : "O envio de e-mail está desativado.",
        prefs.emailPedidos ? null : el("div", {}, el("button", { type: "button", onclick: () => irPara("configuracoes") }, "Ativar nas configurações")));
    }
  }

  $("#confirmar").addEventListener("click", async () => {
    const itens = itensDoCarrinho();
    if (!itens.length) { aviso("Adicione itens ao pedido antes de continuar.", "erro"); return; }
    const escolhido = $('input[name="pagamento"]:checked');
    if (!escolhido) { aviso("Escolha uma forma de pagamento.", "erro"); $(".opcao input").focus(); return; }
    const botao = $("#confirmar");
    botao.disabled = true; botao.textContent = "Enviando pedido…";
    try {
      const pedido = await api("/pedidos", {
        metodo: "POST",
        corpo: { itens: itens.map(i => ({ id: i.produto.id, quantidade: i.qtd })), pagamento: escolhido.value, observacao: $("#observacao").value }
      });
      carrinho.clear(); $("#observacao").value = "";
      atualizarCarrinho();
      if (usuario) totalPedidos += 1;
      mostrarRecibo(pedido);
    } catch (erro) {
      aviso(erro.message, "erro");
    } finally {
      botao.textContent = "Confirmar pedido";
      botao.disabled = carrinho.size === 0;
    }
  });

  function textoEmail(e) {
    if (!e.enviado) return e.mensagem || "Não foi possível enviar.";
    return (e.modo === "simulado" ? "Cobrança simulada para " : "Cobrança enviada para ") + e.destino;
  }

  function mostrarRecibo(pedido) {
    if (!prefs.notificacoes) { aviso("Pedido registrado. Código " + pedido.id.slice(0, 8).toUpperCase() + ".", "ok"); irPara("cardapio"); return; }
    const linha = (rotulo, valor) => el("div", {}, el("dt", { texto: rotulo }), el("dd", { texto: valor }));
    abrirModal(
      el("div", { class: "selo-ok" }, icone("i-ok")),
      el("h3", { texto: "Pedido registrado" }),
      el("p", { texto: "Recebemos o seu pedido. O valor foi calculado pelo servidor." }),
      el("dl", { class: "recibo" },
        linha("Código", pedido.id.slice(0, 8).toUpperCase()),
        linha("Itens", String(pedido.itens.reduce((s, i) => s + i.quantidade, 0))),
        linha("Pagamento", pedido.pagamento),
        pedido.email ? linha("E-mail", textoEmail(pedido.email)) : null,
        pedido.entrega ? linha("Entrega", pedido.entrega) : null,
        linha("Total", dinheiro(pedido.total))
      ),
      el("p", { class: "nota", texto: "Pagamento demonstrativo: nenhuma cobrança real foi feita." }),
      el("div", { class: "acoes" },
        usuario ? el("button", { type: "button", class: "btn btn-contorno", onclick: () => { fecharModal(); irPara("perfil"); abrirSubPerfil("historico"); } }, "Ver meus pedidos") : null,
        el("button", { type: "button", class: "btn btn-acento", onclick: () => { fecharModal(); irPara("cardapio"); } }, "Voltar ao cardápio"))
    );
  }

  // ---------- Conta ----------
  function erroForm(form, mensagem) {
    const caixa = $(".erro-form", form);
    caixa.hidden = !mensagem; caixa.textContent = mensagem || "";
  }
  function emEnvio(form, enviando, texto) {
    const botao = $('button[type="submit"]', form);
    if (enviando) { botao.dataset.rotulo = botao.textContent; botao.textContent = texto; } else if (botao.dataset.rotulo) botao.textContent = botao.dataset.rotulo;
    botao.disabled = enviando;
  }
  async function enviarForm(form, textoEnvio, tarefa) {
    erroForm(form, "");
    emEnvio(form, true, textoEnvio);
    try { await tarefa(); }
    catch (erro) { if (erro.status === 401 && usuario) sessaoExpirada(); else erroForm(form, erro.message); }
    finally { emEnvio(form, false); }
  }

  function trocarAuth(modo) {
    $$("[data-auth]").forEach(b => { const ativo = b.dataset.auth === modo; b.classList.toggle("ativo", ativo); b.setAttribute("aria-selected", String(ativo)); });
    $("#form-entrar").hidden = modo !== "entrar";
    $("#form-criar").hidden = modo !== "criar";
  }
  $$("[data-auth]").forEach(b => b.addEventListener("click", () => trocarAuth(b.dataset.auth)));

  $("#form-entrar").addEventListener("submit", evento => {
    evento.preventDefault();
    const form = evento.currentTarget, d = new FormData(form);
    enviarForm(form, "Entrando…", async () => {
      await api("/auth/login", { metodo: "POST", corpo: { email: d.get("email"), senha: d.get("senha") } });
      form.reset();
      await carregarConta();
      aviso("Bem-vindo de volta, " + usuario.nome.split(" ")[0] + ".", "ok");
    });
  });

  $("#form-criar").addEventListener("submit", evento => {
    evento.preventDefault();
    const form = evento.currentTarget, d = new FormData(form);
    if (d.get("senha") !== d.get("confirma")) { erroForm(form, "As senhas não são iguais."); return; }
    enviarForm(form, "Criando conta…", async () => {
      await api("/auth/cadastro", { metodo: "POST", corpo: { nome: d.get("nome"), email: d.get("email"), senha: d.get("senha") } });
      form.reset();
      // preferências escolhidas como visitante passam a valer na conta nova
      const locais = { ...prefs };
      await carregarConta();
      prefs = locais; aplicarPrefs(); salvarPrefs();
      aviso("Conta criada. Boa viagem, " + usuario.nome.split(" ")[0] + ".", "ok");
    });
  });

  async function carregarConta() {
    const dados = await api("/perfil");
    usuario = dados.usuario;
    totalPedidos = dados.totalPedidos;
    prefs = { ...PADRAO, ...dados.preferencias };
    guardar("mle_prefs", prefs);
    aplicarPrefs();
    atualizarConta();
  }

  function sessaoExpirada() {
    usuario = null; atualizarConta();
    aviso("Sua sessão expirou. Entre novamente.", "erro");
    irPara("perfil");
  }

  function iconeAvatar(id) { return icone("a-" + (AVATARES.some(a => a[0] === id) ? id : "astronauta")); }

  function atualizarConta() {
    const logado = Boolean(usuario);
    $("#conta-nome").textContent = logado ? usuario.nome : "Visitante";
    $("#conta-sub").textContent = logado ? usuario.email : "Entrar ou criar conta";
    $("#conta-avatar").replaceChildren(iconeAvatar(logado ? usuario.avatar : "astronauta"));
    $("#perfil-visitante").hidden = logado;
    $("#perfil-logado").hidden = !logado;
    $("#perfil-sub").textContent = logado ? "Gerencie seus dados, endereço de entrega, segurança e pedidos." : "Crie uma conta para guardar seus dados, endereço e histórico de pedidos.";
    $("#config-sub").textContent = logado ? "As mudanças valem na hora e ficam salvas na sua conta." : "As mudanças valem na hora e ficam neste navegador. Entre na conta para levá-las a outros aparelhos.";
    if (logado) {
      $("#perfil-avatar").replaceChildren(iconeAvatar(usuario.avatar));
      $("#perfil-nome-titulo").textContent = usuario.nome;
      const desde = new Date(usuario.criadoEm).toLocaleDateString("pt-BR", { month: "long", year: "numeric" });
      $("#perfil-meta").textContent = usuario.email + " · cliente desde " + desde;
      preencherFormsPerfil();
    }
    desenharEntrega();
  }

  function preencherFormsPerfil() {
    const f = $("#form-dados");
    f.nome.value = usuario.nome; f.email.value = usuario.email; f.telefone.value = mascaraTelefone(usuario.telefone);
    $$('input[name="avatar"]', f).forEach(i => { i.checked = i.value === usuario.avatar; });
    const e = $("#form-entrega"), end = usuario.endereco;
    for (const campo of ["cep", "rua", "numero", "complemento", "bairro", "cidade", "uf"]) e[campo].value = end[campo] || "";
    erroForm(f, ""); erroForm(e, "");
  }

  function montarAvatares() {
    $("#avatares").replaceChildren(...AVATARES.map(([id, nome]) => el("label", { class: "avatar-opcao", title: nome },
      el("input", { type: "radio", name: "avatar", value: id, "aria-label": nome }),
      el("span", { class: "avatar" }, icone("a-" + id))
    )));
    const uf = $('#form-entrega select[name="uf"]');
    UFS.forEach(u => uf.append(el("option", { value: u, texto: u })));
  }

  function mascaraTelefone(valor) {
    const d = String(valor || "").replace(/\D/g, "").slice(0, 11);
    if (d.length <= 2) return d;
    if (d.length <= 6) return "(" + d.slice(0, 2) + ") " + d.slice(2);
    if (d.length <= 10) return "(" + d.slice(0, 2) + ") " + d.slice(2, 6) + "-" + d.slice(6);
    return "(" + d.slice(0, 2) + ") " + d.slice(2, 7) + "-" + d.slice(7);
  }
  function mascaraCep(valor) {
    const d = String(valor || "").replace(/\D/g, "").slice(0, 8);
    return d.length > 5 ? d.slice(0, 5) + "-" + d.slice(5) : d;
  }
  $('#form-dados input[name="telefone"]').addEventListener("input", e => { e.target.value = mascaraTelefone(e.target.value); });
  $('#form-entrega input[name="cep"]').addEventListener("input", e => { e.target.value = mascaraCep(e.target.value); });

  $("#form-dados").addEventListener("submit", evento => {
    evento.preventDefault();
    const form = evento.currentTarget, d = new FormData(form);
    enviarForm(form, "Salvando…", async () => {
      const r = await api("/perfil", {
        metodo: "PUT",
        corpo: { nome: d.get("nome"), email: d.get("email"), telefone: d.get("telefone"), avatar: d.get("avatar"), endereco: usuario.endereco }
      });
      usuario = r.usuario; atualizarConta();
      aviso("Dados atualizados.", "ok");
    });
  });

  $("#form-entrega").addEventListener("submit", evento => {
    evento.preventDefault();
    const form = evento.currentTarget, d = new FormData(form);
    enviarForm(form, "Salvando…", async () => {
      const endereco = Object.fromEntries(["cep", "rua", "numero", "complemento", "bairro", "cidade", "uf"].map(c => [c, d.get(c)]));
      const r = await api("/perfil", {
        metodo: "PUT",
        corpo: { nome: usuario.nome, email: usuario.email, telefone: usuario.telefone, avatar: usuario.avatar, endereco }
      });
      usuario = r.usuario; atualizarConta();
      aviso("Endereço salvo.", "ok");
    });
  });

  $("#form-senha").addEventListener("submit", evento => {
    evento.preventDefault();
    const form = evento.currentTarget, d = new FormData(form);
    if (d.get("nova") !== d.get("confirma")) { erroForm(form, "As senhas novas não são iguais."); return; }
    enviarForm(form, "Atualizando…", async () => {
      await api("/perfil/senha", { metodo: "PUT", corpo: { senhaAtual: d.get("atual"), novaSenha: d.get("nova") } });
      form.reset();
      aviso("Senha atualizada.", "ok");
    });
  });

  $("#sair").addEventListener("click", async () => {
    try { await api("/auth/logout", { metodo: "POST" }); } catch { /* o cookie expira sozinho */ }
    usuario = null; totalPedidos = 0;
    atualizarConta(); trocarAuth("entrar");
    aviso("Você saiu da conta.");
  });

  $("#excluir-conta").addEventListener("click", () => {
    const campo = el("input", { type: "password", autocomplete: "current-password", "aria-label": "Sua senha" });
    const erro = el("p", { class: "erro-form", role: "alert", hidden: true });
    const confirmar = el("button", { type: "button", class: "btn btn-perigo" }, "Excluir para sempre");
    confirmar.addEventListener("click", async () => {
      erro.hidden = true; confirmar.disabled = true;
      try {
        await api("/perfil", { metodo: "DELETE", corpo: { senha: campo.value } });
        usuario = null; totalPedidos = 0; fecharModal(); atualizarConta(); trocarAuth("entrar");
        aviso("Conta excluída.");
      } catch (e) { erro.textContent = e.message; erro.hidden = false; confirmar.disabled = false; }
    });
    abrirModal(
      el("h3", { texto: "Excluir sua conta?" }),
      el("p", { texto: "Isso apaga seus dados, endereço e preferências e não pode ser desfeito. Digite sua senha para confirmar." }),
      el("div", { class: "campo" }, campo), erro,
      el("div", { class: "acoes" }, el("button", { type: "button", class: "btn btn-contorno", onclick: fecharModal }, "Cancelar"), confirmar)
    );
    campo.focus();
  });

  // sub-abas do perfil
  function abrirSubPerfil(nome) {
    $$("[data-psub]").forEach(b => { const ativo = b.dataset.psub === nome; b.classList.toggle("ativo", ativo); b.setAttribute("aria-selected", String(ativo)); });
    $$(".psub").forEach(s => s.classList.toggle("ativa", s.id === "psub-" + nome));
    if (nome === "historico") carregarHistorico();
  }
  $$("[data-psub]").forEach(b => b.addEventListener("click", () => abrirSubPerfil(b.dataset.psub)));

  async function carregarHistorico() {
    if (!usuario) return;
    const lista = $("#historico");
    try {
      const pedidos = await api("/pedidos");
      $("#historico-vazio").hidden = pedidos.length > 0;
      lista.replaceChildren(...pedidos.map(p => el("li", { class: "pedido-hist" },
        el("div", { class: "ph-topo" },
          el("span", { class: "ph-codigo", texto: "Pedido " + p.id.slice(0, 8).toUpperCase() }),
          el("span", { class: "ph-data", texto: new Date(p.criadoEm).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" }) })),
        el("p", { class: "ph-itens", texto: p.itens.map(i => i.quantidade + "× " + i.nome).join(", ") }),
        el("div", { class: "ph-rodape" },
          el("span", { class: "ph-status", texto: p.status.charAt(0).toUpperCase() + p.status.slice(1) }),
          el("span", { class: "ph-total", texto: p.pagamento + " · " + dinheiro(p.total) })),
        el("div", { class: "ph-acoes" }, (() => {
          const botao = el("button", { type: "button", class: "btn btn-contorno btn-pequeno" }, "Enviar cobrança por e-mail");
          botao.addEventListener("click", () => enviarCobranca(p, botao));
          return botao;
        })())
      )));
    } catch (erro) {
      if (erro.status === 401) sessaoExpirada(); else aviso(erro.message, "erro");
    }
  }

  async function enviarCobranca(pedido, botao) {
    const rotulo = botao.textContent;
    botao.disabled = true; botao.textContent = "Enviando…";
    try {
      const r = await api("/pedidos/" + pedido.id + "/cobranca", { metodo: "POST" });
      aviso(r.modo === "simulado"
        ? "Cobrança simulada para " + r.destino + ". Modo de teste: o e-mail foi salvo em dados/emails."
        : "Cobrança enviada para " + r.destino + ".", "ok");
    } catch (erro) {
      if (erro.status === 401) sessaoExpirada(); else aviso(erro.message, "erro");
    } finally {
      botao.textContent = rotulo; botao.disabled = false;
    }
  }

  // ---------- Configurações ----------
  function montarTemas() {
    $("#temas").replaceChildren(...TEMAS.map(([id, nome, cor]) => {
      const marca = el("i"); marca.style.background = cor;
      const entrada = el("input", { type: "radio", name: "tema", value: id });
      entrada.addEventListener("change", () => mudarPref("tema", id));
      return el("label", { class: "tema-opcao" }, entrada, el("span", {}, marca, nome));
    }));
  }
  function sincronizarControlesConfig() {
    $$('input[name="tema"]').forEach(i => { i.checked = i.value === prefs.tema; });
    $("#cfg-texto").value = prefs.tamanhoTexto;
    $("#cfg-estrelas").checked = prefs.estrelas;
    $("#cfg-animacoes").checked = prefs.reduzirAnimacoes;
    $("#cfg-compacto").checked = prefs.compacto;
    $("#cfg-descricoes").checked = prefs.descricoesVisiveis;
    $("#cfg-pagamento").value = prefs.pagamentoPadrao;
    $("#cfg-notificacoes").checked = prefs.notificacoes;
    $("#cfg-email").checked = prefs.emailPedidos;
  }
  function ligarConfig() {
    $("#cfg-texto").addEventListener("change", e => mudarPref("tamanhoTexto", e.target.value));
    $("#cfg-estrelas").addEventListener("change", e => mudarPref("estrelas", e.target.checked));
    $("#cfg-animacoes").addEventListener("change", e => mudarPref("reduzirAnimacoes", e.target.checked));
    $("#cfg-compacto").addEventListener("change", e => mudarPref("compacto", e.target.checked));
    $("#cfg-descricoes").addEventListener("change", e => mudarPref("descricoesVisiveis", e.target.checked));
    $("#cfg-notificacoes").addEventListener("change", e => mudarPref("notificacoes", e.target.checked));
    $("#cfg-email").addEventListener("change", e => { mudarPref("emailPedidos", e.target.checked); desenharEntrega(); });
    $("#cfg-pagamento").addEventListener("change", e => {
      mudarPref("pagamentoPadrao", e.target.value);
      $$('input[name="pagamento"]').forEach(i => { i.checked = i.value === e.target.value; });
    });
    $("#cfg-restaurar").addEventListener("click", () => { prefs = { ...PADRAO }; aplicarPrefs(); salvarPrefs(); aviso("Preferências restauradas.", "ok"); });
  }

  // ---------- Início ----------
  async function iniciar() {
    montarPagamentos(); montarAvatares(); montarTemas(); ligarConfig();
    medirCeu(); aplicarPrefs();
    irPara(location.hash.slice(1), { foco: false });

    const grade = $("#grade-produtos");
    try {
      produtos = await api("/produtos");
      const salvo = ler("mle_carrinho");
      if (Array.isArray(salvo)) {
        carrinho = new Map(salvo.filter(([id, q]) => produtoPorId(id) && Number.isInteger(q) && q > 0).map(([id, q]) => [id, Math.min(q, maxQtd)]));
      }
      desenharCategorias(); desenharCatalogo();
    } catch (erro) {
      grade.replaceChildren(el("p", { class: "suave", texto: "Não foi possível carregar o cardápio. " + erro.message }));
    }
    atualizarCarrinho();

    try { await carregarConta(); } catch { atualizarConta(); } // sem sessão: segue como visitante
  }
  iniciar();
})();
