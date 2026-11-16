/* ALTARIS – preferências de acessibilidade (letra maior e alto contraste).
   Guardadas no próprio aparelho (localStorage); sem dados pessoais. */
(function () {
  var raiz = document.documentElement;
  var opcoes = { fonte: "fonte-grande", contraste: "alto-contraste" };

  function ler(chave) {
    try { return localStorage.getItem("altaris-" + chave) === "1"; } catch (e) { return false; }
  }
  function gravar(chave, ligado) {
    try { localStorage.setItem("altaris-" + chave, ligado ? "1" : "0"); } catch (e) { /* modo privado */ }
  }
  function aplicar(chave, ligado) {
    raiz.classList.toggle(opcoes[chave], ligado);
    var botao = document.querySelector('[data-a11y="' + chave + '"]');
    if (botao) { botao.setAttribute("aria-pressed", ligado ? "true" : "false"); }
  }

  Object.keys(opcoes).forEach(function (chave) { aplicar(chave, ler(chave)); });

  document.addEventListener("click", function (ev) {
    var botao = ev.target.closest("[data-a11y]");
    if (!botao) { return; }
    var chave = botao.getAttribute("data-a11y");
    var ligado = botao.getAttribute("aria-pressed") !== "true";
    aplicar(chave, ligado);
    gravar(chave, ligado);
  });
})();
