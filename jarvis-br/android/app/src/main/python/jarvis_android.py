"""
J.A.R.V.I.S BR no APK (fork PT-BR 3.6.1) — a ponte entre o app Android e o JARVIS do celular.

O app NÃO reescreve o JARVIS: ele roda o mesmo `celular/jarvis_celular.py` da versão Termux (os mesmos
plugins, modos, cérebro local, organismo, OMEGA…), dentro do próprio app, e mostra a mesma interface num
WebView. Este arquivo só troca as três coisas que no Termux vinham de fora:

    • os comandos `termux-*` do plugin celular_android  → a ponte Java (lanterna, bateria, vibrar…);
    • abrir link/arquivo                                → o Android (link) ou o próprio app (relatórios HTML);
    • a voz do Chrome (que o WebView não tem)           → o reconhecimento de voz e o TTS do Android.

Cérebro "both": com internet e chave, o Gemini pensa; sem internet (ou sem chave), o cérebro local faz os
comandos que já aprendeu com você — exatamente como no PC e no Termux.
"""
from __future__ import annotations

import json
import os
import sys
import threading
import traceback
from pathlib import Path

PORTA = 8766                     # a versão Termux usa 8765: os dois podem existir no mesmo celular
_estado: dict = {"servidor": None, "ponte": None, "erro": ""}

# Voz do Android dentro da página: o WebView não tem SpeechRecognition nem speechSynthesis de verdade.
# Este trecho entra no <head> ANTES do script da página, que continua igual ao da versão do Chrome.
VOZ_JS = r"""<script>
(function () {
  var V = window.JarvisVoz; if (!V) return;
  var falas = {}, n = 0, ouvinte = null;
  function chamar(f, ev) { try { if (typeof f === "function") f(ev || {}); } catch (e) { console.error(e); } }
  function Utt(t) { this.text = t || ""; this.lang = "pt-BR"; this.rate = 1; this.pitch = 1; this.volume = 1; this.voice = null;
                    this.onstart = this.onend = this.onerror = null; }
  var VOZ = { name: "Voz do Android", lang: "pt-BR", default: true, localService: true, voiceURI: "android" };
  var synth = {
    speaking: false, pending: false, paused: false, onvoiceschanged: null,
    getVoices: function () { return [VOZ]; },
    speak: function (u) { var id = "f" + (++n); falas[id] = u; synth.speaking = true;
                          V.falar(String(u.text || ""), Number(u.rate) || 1, id); },
    cancel: function () { var velhas = falas; falas = {}; synth.speaking = false; V.parar();
                          Object.keys(velhas).forEach(function (id) { setTimeout(function () { chamar(velhas[id].onerror, { error: "interrupted" }); }, 0); }); },
    pause: function () {}, resume: function () {}
  };
  try { Object.defineProperty(window, "speechSynthesis", { value: synth, configurable: true, writable: true }); } catch (e) { window.speechSynthesis = synth; }
  window.SpeechSynthesisUtterance = Utt;
  function Rec() { this.lang = "pt-BR"; this.interimResults = false; this.continuous = false;
                   this.onstart = this.onresult = this.onerror = this.onend = null; }
  Rec.prototype.start = function () { ouvinte = this; V.ouvir(String(this.lang || "pt-BR"), !!this.interimResults); };
  Rec.prototype.stop = function () { V.pararOuvir(); };
  Rec.prototype.abort = Rec.prototype.stop;
  window.SpeechRecognition = window.webkitSpeechRecognition = Rec;
  window.__jarvisVoz = function (ev, a) {
    var u;
    if (ev === "fala_inicio") { u = falas[a]; if (u) chamar(u.onstart); }
    else if (ev === "fala_fim" || ev === "fala_erro") {
      u = falas[a]; delete falas[a]; if (!Object.keys(falas).length) synth.speaking = false;
      if (u) chamar(ev === "fala_fim" ? u.onend : u.onerror, ev === "fala_erro" ? { error: "synthesis-failed" } : {});
    }
    else if (!ouvinte) return;
    else if (ev === "ouvir_inicio") chamar(ouvinte.onstart);
    else if (ev === "ouvir_parcial" || ev === "ouvir_final") {
      var r = [{ transcript: String(a || ""), confidence: 1 }]; r.isFinal = ev === "ouvir_final";
      chamar(ouvinte.onresult, { results: [r], resultIndex: 0 });
    }
    else if (ev === "ouvir_erro") chamar(ouvinte.onerror, { error: String(a || "") });
    else if (ev === "ouvir_fim") { var o = ouvinte; ouvinte = null; chamar(o.onend); }
  };
})();
</script>"""


def html_android(original: str) -> str:
    """A página do celular com a voz do Android entrando antes de tudo. Pura."""
    i = original.lower().find("<head>")
    if i < 0:
        return VOZ_JS + original
    i += len("<head>")
    return original[:i] + "\n" + VOZ_JS + original[i:]


# ─────────────────────────────────────────────────────────── ponte com o Java ───
def chamar_ponte(ponte, comando: str, args=(), entrada=None) -> str:
    """Pede uma coisa ao Android. Resposta começando com "ERRO:" vira exceção com a mensagem."""
    r = str(ponte.comando(str(comando), json.dumps({"a": [str(x) for x in args], "entrada": entrada}, ensure_ascii=False)) or "")
    if r.startswith("ERRO:"):
        raise RuntimeError(r[5:].strip())
    return r


def termux_pela_ponte(ponte):
    """Substituto da função termux() do plugin celular_android: mesmo jeito de chamar, mesma resposta."""
    def termux(*args, timeout=20, entrada=None) -> str:
        return chamar_ponte(ponte, args[0], args[1:], entrada).strip()
    return termux


def abrir_pela_ponte(ponte):
    def abrir(alvo) -> bool:
        try:
            return chamar_ponte(ponte, "abrir", [str(alvo)]) == "ok"
        except Exception as e:
            print(f"[Android] não abri {alvo}: {e}")
            return False
    return abrir


def _trocar_termux_no_plugin(ponte) -> int:
    """O carregador de plugins pode ter mais de uma cópia do módulo: troca em todas."""
    trocados = 0
    for m in list(sys.modules.values()):
        if str(getattr(m, "__file__", "") or "").replace("\\", "/").endswith("plugins/celular_android.py") and hasattr(m, "termux"):
            m.termux = termux_pela_ponte(ponte)
            trocados += 1
    return trocados


# ─────────────────────────────────────────────────────────── início ───
def iniciar(raiz, ponte, pasta_publica, porta: int = PORTA) -> str:
    """Chamado pelo serviço do app. Carrega o JARVIS do celular e sobe o servidor da interface.
    Devolve "ok" (subiu), "ja" (já estava rodando) ou levanta exceção com o motivo."""
    if _estado["servidor"] is not None:
        _estado["ponte"] = ponte
        return "ja"
    raiz = Path(str(raiz)).resolve()
    pasta_publica = Path(str(pasta_publica)).resolve()
    pasta_publica.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("HOME", str(raiz.parent))
    os.environ["JARVIS_ANDROID"] = "1"
    os.chdir(str(raiz))
    for p in (str(raiz), str(raiz / "celular")):
        if p not in sys.path:
            sys.path.insert(0, p)
    _estado["ponte"] = ponte

    import webbrowser
    from plugins import _comum
    nomes = {"Documents": "Documentos", "Downloads": "Downloads", "Pictures": "Fotos", "Videos": "Videos", "Desktop": "Documentos"}
    _comum.pasta_usuario = lambda nome: pasta_publica / nomes.get(nome, nome)
    _comum.abrir_no_sistema = abrir_pela_ponte(ponte)
    webbrowser.open = lambda url, *a, **k: _comum.abrir_no_sistema(url)

    import jarvis_celular as jc
    pagina = raiz / "celular" / "jarvis_android.html"
    pagina.write_text(html_android(jc.HTML.read_text(encoding="utf-8")), encoding="utf-8")
    jc.HTML = pagina
    jc.iniciar()
    _trocar_termux_no_plugin(ponte)
    import importlib
    for nome in ("livro_razao", "experimento_vida", "omega"):      # 3.6 também no celular
        try:
            importlib.import_module(f"plugins.{nome}").on_session_start(jc.PLAYER)
        except Exception as e:
            print(f"[Android] {nome}: {e}")

    from http.server import ThreadingHTTPServer
    srv = ThreadingHTTPServer(("127.0.0.1", int(porta)), jc.Handler)
    srv.daemon_threads = True
    threading.Thread(target=srv.serve_forever, name="jarvis-servidor", daemon=True).start()
    _estado["servidor"] = srv
    total = sum(1 for r in jc.REG.list_for_ui() if r["valid"])
    print(f"[Android] {total} plugins prontos em http://127.0.0.1:{porta}/")
    return "ok"


def iniciar_seguro(raiz, ponte, pasta_publica, porta: int = PORTA) -> str:
    """Igual a iniciar(), mas devolve o erro como texto (o app mostra na tela para você mandar)."""
    try:
        return iniciar(raiz, ponte, pasta_publica, porta)
    except Exception:
        _estado["erro"] = traceback.format_exc()
        return "ERRO:" + _estado["erro"]


def parar() -> None:
    srv = _estado.get("servidor")
    if srv is not None:
        srv.shutdown()
        _estado["servidor"] = None
