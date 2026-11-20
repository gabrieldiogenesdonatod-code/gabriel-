"""
Gerente de reparos da regeneração: o catálogo de tratamentos e como cada um é feito.

Cada tratamento tem um nível de permissão:
    segura       faz sozinho — não muda arquivo seu (isolar, esperar a internet, dar mais tempo,
                 recarregar o plugin, liberar memória, reanimar um órgão interno, avisar você)
    autorizacao  só com o seu SIM na tela (restaurar um JSON, voltar um código para a cópia do DNA)
Nada aqui apaga arquivo nem instala pacote: quem troca um arquivo guarda o antigo do lado
(".corrompido-DATA" / ".mutante-DATA") e entra no "Jarvis, desfaz".
"""

from __future__ import annotations

import gc
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path

from biological_core.config import AUTORIZACAO, SEGURA


@dataclass(frozen=True)
class Tratamento:
    nome: str
    nivel: str
    descricao: str
    escreve: bool = False
    notifica: bool = False


CATALOGO = {t.nome: t for t in (
    Tratamento("observar", SEGURA, "só observar (pode ter sido uma falha isolada)"),
    Tratamento("isolar_temporario", SEGURA, "isolar por um tempo e testar de novo"),
    Tratamento("esperar_rede", SEGURA, "esperar a internet voltar e testar na hora"),
    Tratamento("aumentar_limite", SEGURA, "dar mais tempo para a ferramenta terminar"),
    Tratamento("recarregar_modulo", SEGURA, "recarregar o plugin (reiniciar o componente)"),
    Tratamento("recriar_pasta", SEGURA, "recriar a pasta que sumiu", escreve=True),
    Tratamento("reflexo_memoria", SEGURA, "liberar memória (coleta de lixo e caches)"),
    Tratamento("reanimar_orgao", SEGURA, "reanimar uma parte interna parada"),
    Tratamento("pedir_chave", SEGURA, "avisar qual chave falta", notifica=True),
    Tratamento("informar_pacote", SEGURA, "dizer qual pacote instalar (não instala sozinho)", notifica=True),
    Tratamento("sugerir_correcao", SEGURA, "pedir ao auto-melhoria uma correção testada", notifica=True),
    Tratamento("avisar_recurso", SEGURA, "avisar falta de memória ou disco", notifica=True),
    Tratamento("restaurar_json", AUTORIZACAO, "voltar o arquivo de dados para a última versão boa", escreve=True),
    Tratamento("restaurar_codigo", AUTORIZACAO, "voltar o código para a cópia confiável do DNA", escreve=True),
    Tratamento("pedir_intervencao", SEGURA, "manter isolado e chamar você", notifica=True),
)}

PACOTE_DE = {"cv2": "opencv-python", "PIL": "pillow", "yaml": "pyyaml", "sklearn": "scikit-learn", "bs4": "beautifulsoup4",
             "dotenv": "python-dotenv", "serial": "pyserial", "docx": "python-docx", "win32api": "pywin32",
             "pptx": "python-pptx", "speech_recognition": "SpeechRecognition", "google": "google-genai"}
LIMITE_MAXIMO_S = 120.0


class GerenteReparos:
    def __init__(self, org):
        self.org = org
        self._avisados: dict[str, float] = {}

    def _avisar_uma_vez(self, chave: str, texto: str, prioridade: str = "normal", horas: float = 12) -> bool:
        agora = time.time()
        if agora - self._avisados.get(chave, 0) < horas * 3600:
            return False
        self._avisados[chave] = agora
        self.org.avisar(texto, prioridade)
        return True

    def aplicar(self, nome: str, inc: dict, ficha: str | None = None) -> tuple[str, str]:
        """(estado, mensagem). Estados: aplicado · resolvido · informado · falhou · aguardando_autorizacao · aguardando_humano."""
        fn = getattr(self, f"_t_{nome}", None)
        if fn is None:
            return "falhou", f"tratamento desconhecido: {nome}"
        try:
            return fn(inc, ficha)
        except Exception as e:
            return "falhou", f"{type(e).__name__}: {e}"

    # ── seguros ───────────────────────────────────────────────────────────────
    def _t_observar(self, inc, _f):
        return "aplicado", "só observando: se voltar a acontecer, o cérebro escolhe outro tratamento"

    def _t_isolar_temporario(self, inc, _f):
        ok = self.org.imune.isolamento.abrir(inc["modulo"], inc.get("acao"), f"isolado pelo cérebro: {inc['categoria']}", inc["categoria"])
        return ("aplicado", "isolado por um tempo; a próxima chamada depois do descanso é o teste") if ok else \
               ("falhou", "é um módulo essencial: não pode ser isolado")

    def _t_esperar_rede(self, inc, _f):
        self.org.imune.isolamento.abrir(inc["modulo"], inc.get("acao"), "sem internet", "rede")
        self.org.esperando_rede.add((inc["modulo"], inc.get("acao")))
        return "aplicado", "isolado até a internet voltar; o JARVIS testa a conexão a cada minuto"

    def _t_aumentar_limite(self, inc, _f):
        from core import vigia
        atual = vigia.LIMITES.get(inc["modulo"]) or vigia.limite_configurado()
        if atual >= LIMITE_MAXIMO_S:
            return "falhou", f"já está no limite máximo ({LIMITE_MAXIMO_S:.0f} s)"
        novo = min(LIMITE_MAXIMO_S, atual * 2)
        vigia.LIMITES[inc["modulo"]] = novo
        self.org.estado.setdefault("limites", {})[inc["modulo"]] = novo
        self.org.salvar_estado()
        return "aplicado", f"'{inc['modulo']}' agora tem {novo:.0f} s para terminar (era {atual:.0f} s)"

    def _t_recarregar_modulo(self, inc, _f):
        caminho = self.org.raiz / "plugins" / f"{inc['modulo']}.py"
        if not caminho.is_file():
            return "falhou", "não é um plugin que dê para recarregar"
        ok, motivo = self.org.imune.prevencao.verificar_codigo(caminho)
        if not ok:
            return "falhou", f"o arquivo não compila ({motivo}): recarregar não adianta"
        from core import registro_ferramentas
        ok, msg = registro_ferramentas.carregar_plugin(caminho)
        return ("aplicado", f"plugin recarregado: {msg}") if ok else ("falhou", f"não recarregou: {msg}")

    def _t_recriar_pasta(self, inc, _f):
        m = re.search(r"['\"]([^'\"]+)['\"]", inc.get("mensagem", ""))
        if not m:
            return "falhou", "não achei o caminho na mensagem de erro"
        p = Path(m.group(1))
        p = p if p.is_absolute() else self.org.raiz / p
        try:
            p.resolve().relative_to(self.org.raiz.resolve())
        except ValueError:
            return "falhou", f"{p} fica fora da pasta do JARVIS: não mexo"
        alvo = p if not p.suffix else p.parent
        if alvo.exists():
            return "falhou", "a pasta existe; o que falta é um arquivo (não invento conteúdo)"
        alvo.mkdir(parents=True, exist_ok=True)
        return "resolvido", f"pasta recriada: {alvo.relative_to(self.org.raiz)}"

    def _t_reflexo_memoria(self, inc, _f):
        liberados = self.org.coracao.reflexo_memoria() if self.org.coracao else gc.collect()
        return "aplicado", f"memória liberada ({liberados} objetos coletados)"

    def _t_reanimar_orgao(self, inc, _f):
        feitos = self.org.reanimar()
        return ("aplicado", "reanimados: " + ", ".join(feitos)) if feitos else ("falhou", "nada parado para reanimar")

    def _t_pedir_chave(self, inc, _f):
        self._avisar_uma_vez(f"chave:{inc['modulo']}", f"O plugin {inc['modulo']} está sem chave válida ({inc.get('mensagem', '')[:80]}). "
                                                       "Cole a chave em Configurações.")
        return "informado", "avisei você sobre a chave"

    def _t_informar_pacote(self, inc, _f):
        m = re.search(r"No module named ['\"]?([\w.]+)", inc.get("mensagem", "")) \
            or re.search(r"pip install ([\w.\-]+)", inc.get("mensagem", ""))          # 3.6.1: mensagem do carregador
        mod = m.group(1).split(".")[0] if m else ""
        pacote = PACOTE_DE.get(mod, mod.replace("_", "-")) if mod else ""
        texto = (f"O plugin {inc['modulo']} precisa do pacote {pacote}: rode 'pip install {pacote}' e reinicie o JARVIS."
                 if pacote else f"O plugin {inc['modulo']} precisa de um pacote que não está instalado ({inc.get('mensagem', '')[:80]}).")
        if os.environ.get("JARVIS_ANDROID"):              # 3.6.1: no app não há pip; o plugin só fica de fora, sem aviso
            return "informado", "no app do Android este plugin fica desligado: " + texto
        self._avisar_uma_vez(f"pacote:{pacote or inc['modulo']}", texto)
        return "informado", texto

    def _t_sugerir_correcao(self, inc, _f):
        onde = f"{inc.get('arquivo') or 'plugins/' + inc['modulo'] + '.py'}" + (f" linha {inc['linha']}" if inc.get("linha") else "")
        self._avisar_uma_vez(f"bug:{inc.get('impressao')}", f"Erro de código em {onde} ({inc.get('mensagem', '')[:80]}). "
                                                            "Diga 'Jarvis, analisa seus erros' e o auto-melhoria propõe uma correção testada numa cópia.",
                             "baixa")
        return "informado", f"encaminhado ao auto-melhoria: {onde}"

    def _t_avisar_recurso(self, inc, _f):
        self._avisar_uma_vez(f"recurso:{inc['categoria']}", f"Atenção: {inc.get('mensagem', 'falta de recurso')[:160]}", "normal", 3)
        return "informado", "avisei você"

    def _t_pedir_intervencao(self, inc, _f):
        if inc["modulo"] not in self.org.essenciais and inc.get("categoria") not in ("integridade",):
            self.org.imune.isolamento.isolar(inc["modulo"], inc.get("acao"), f"esperando você: {inc['categoria']}", inc.get("id"))
        self._avisar_uma_vez(f"humano:{inc.get('impressao')}", f"Preciso de você: {inc.get('mensagem', '')[:160]}. "
                                                               "Diga 'Jarvis, mostra os incidentes' para ver o que eu já tentei.")
        return "aguardando_humano", "isolado e esperando você"

    # ── com autorização ───────────────────────────────────────────────────────
    def _t_restaurar_json(self, inc, ficha):
        rel = inc.get("arquivo") or ""
        if not rel.endswith(".json"):
            return "falhou", "não sei qual arquivo de dados restaurar"
        boa = self.org.imune.prevencao.ultima_versao_boa(rel)
        if not boa:
            return "aguardando_humano", f"não há versão boa de {rel} nos pontos de restauração"
        escopo = f"restaurar_json:{rel}"
        ficha = ficha or self.org.autorizacoes.ficha_pre_autorizada("restaurar_json", rel)
        if ficha is None:
            p = self.org.autorizacoes.pedir("restaurar_json", f"Restaurar {Path(rel).name}",
                                            f"O arquivo {rel} está corrompido ({inc.get('mensagem', '')[:80]}). Voltar para a versão "
                                            f"do ponto {boa[0]}? O arquivo quebrado fica guardado do lado.", None, alvo=rel,
                                            dados={"incidente": inc.get("id"), "tratamento": "restaurar_json"})
            return "aguardando_autorizacao", f"pedido {p['id']}: restaurar {rel} precisa do seu sim"
        if not self.org.autorizacoes.validar(ficha, escopo):
            return "falhou", "ficha de autorização inválida"
        guardado = self.org.imune.prevencao.restaurar_arquivo(rel, boa[1])
        self._desfazer(f"restaurar {rel}", rel, guardado)
        return "resolvido", f"{rel} voltou para a versão de {boa[0]}" + (f"; o quebrado ficou como {guardado}" if guardado else "")

    def _t_restaurar_codigo(self, inc, ficha):
        rel = inc.get("arquivo") or (f"plugins/{inc['modulo']}.py" if (self.org.raiz / "plugins" / f"{inc['modulo']}.py").exists() else "")
        if not rel or not self.org.banco.ler(rel):
            return "aguardando_humano", "não há cópia confiável desse código no banco de células-tronco"
        ficha = ficha or self.org.autorizacoes.ficha_pre_autorizada("restaurar_codigo", rel)
        if ficha is None:
            p = self.org.autorizacoes.pedir("restaurar_codigo", f"Restaurar {rel}",
                                            f"{rel} está quebrado ({inc.get('mensagem', '')[:80]}). Voltar para a cópia confiável do DNA? "
                                            "O arquivo atual fica guardado como .mutante.", None, alvo=rel,
                                            dados={"incidente": inc.get("id"), "tratamento": "restaurar_codigo"})
            return "aguardando_autorizacao", f"pedido {p['id']}: restaurar {rel} precisa do seu sim"
        ok, msg = self.org.banco.restaurar(rel, ficha, self.org.autorizacoes, self.org.dna.genoma)
        if not ok:
            return "falhou", msg
        guardado = re.search(r"como (\S+?\.mutante-\S+?)[).]", msg)
        self._desfazer(f"restaurar {rel}", rel, guardado.group(1) if guardado else "")
        if rel.startswith("plugins/"):
            try:
                from core import registro_ferramentas
                registro_ferramentas.carregar_plugin(self.org.raiz / rel)
            except Exception:
                pass
        return "resolvido", msg

    def _desfazer(self, rotulo: str, rel: str, guardado: str) -> None:
        """'Jarvis, desfaz' volta o arquivo que estava lá antes do reparo."""
        if not guardado:
            return
        raiz = self.org.raiz

        def voltar() -> str:
            import os
            alvo = raiz / rel
            antigo = alvo.with_name(guardado)
            if not antigo.exists():
                return "não achei mais o arquivo antigo"
            reparado = alvo.with_name(f"{alvo.name}.reparado-{time.strftime('%Y%m%d-%H%M%S')}")
            if alvo.exists():
                os.replace(alvo, reparado)
            os.replace(antigo, alvo)
            return f"{rel} voltou a ser o arquivo de antes do reparo (o reparado ficou como {reparado.name})"
        try:
            from core.undo import push_undo
            push_undo(rotulo, voltar)
        except Exception:
            pass
