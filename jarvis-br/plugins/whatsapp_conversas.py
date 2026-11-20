"""
O JARVIS nas SUAS conversas do WhatsApp (fork PT-BR 2.3).

    "Jarvis, o que me mandaram no whats?"          (resumo das não lidas; não marca como lida)
    "Jarvis, o que a Ana falou?" / "lê a conversa com o João"
    "Jarvis, manda pra Ana que eu chego às 8"      (com as SUAS palavras, sem 🤖; pede confirmação)
    "Jarvis, responde a Ana por mim"               (rascunho; você aprova com "aprovar 3")
    "Jarvis, modo ausente por 2 horas"             (ele responde como seu assistente)
    "Jarvis, libera resposta automática para a Ana" / "tira a Ana da resposta automática"
    "Jarvis, liga a secretária do whats"           (recusa ligações e anota recado)
    "Jarvis, tem recado?"

    2.16 — ver, ouvir, falar e mandar:
    "Jarvis, o que a Ana falou no áudio?"           (baixa, transcreve e resume o último áudio dela)
    "Jarvis, o que tem na foto que o João mandou?"  (descreve e copia o texto da foto)
    "Jarvis, lê em voz alta as mensagens da Ana"
    "Jarvis, quais áudios eu recebi hoje?"
    "Jarvis, liga a leitura em voz alta"            (avisa por voz quem mandou e o resumo)
    "Jarvis, me manda no whats: comprar leite"      (mensagem para VOCÊ mesmo)
    "Jarvis, me manda o PDF do contrato"            (acha no PC e manda para você; funciona pelo celular)
    "Jarvis, manda a planilha de vendas para a Ana" (para outra pessoa: com confirmação na tela)

Precisa do WhatsApp do JARVIS ligado NO SEU NÚMERO (é ele que vê as suas
conversas). Ler e resumir só acontece quando você pede; para o JARVIS te avisar
das mensagens que chegam, ligue o "Modo pessoal" em ⚙ → WhatsApp do JARVIS.
Grupos ficam de fora. Automação do WhatsApp Web não é oficial: use com calma.
"""

from __future__ import annotations

from plugins import _recados
from plugins import _whatsapp as W
from plugins import _whatsapp_pessoal as P
from plugins._comum import confirmar, mostrar, registrar, salvar_cfg

PLUGIN = {
    "name": "whatsapp_conversas",
    "brief": "The user's own WhatsApp chats: read/summarize, send in his name, reply drafts, away mode, call secretary, "
             "voicemail-style messages.",
    "description": (
        "The user's personal WhatsApp conversations (private chats only). action='novas' summarizes unread chats; "
        "'ler' with contato reads that conversation (optional n); 'mandar' with contato + texto sends a message in the "
        "user's own words (asks on-screen confirmation; use only when he clearly dictates it); 'rascunho' with contato "
        "(optional texto = what he wants to say) prepares a reply draft he approves later with whatsapp_jarvis "
        "aprovar id; 'ausente' with valor ligar/desligar (optional minutos) = away mode, JARVIS auto-replies as his "
        "assistant; 'liberar' / 'bloquear' with contato add/remove a contact from automatic replies; 'secretaria' "
        "with valor ligar/desligar = reject WhatsApp calls and take a message; 'pessoal' with valor ligar/desligar = "
        "get notified of incoming messages with drafts; 'recados' lists messages people left (valor 'lidos' marks "
        "read, 'apagar' deletes); 'status'. Read content only when asked; summarize. 'ouvir'/'ver' + contato: "
        "transcribe+summarize their last voice note / describe their last photo; 'voz_alta' + contato: recent messages "
        "to READ ALOUD (with valor ligar/desligar instead: announce incoming ones by voice); 'midias' lists received "
        "audios/photos; 'para_mim' + texto: note to the user's own WhatsApp; 'arquivo' + busca (+ para = 'mim' or a "
        "contact): find a PC file and send it (others need on-screen confirmation)."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "description": "novas | ler | mandar | rascunho | ausente | liberar | bloquear "
                                                        "| secretaria | pessoal | recados | status | ouvir | ver | "
                                                        "voz_alta | midias | para_mim | arquivo"},
            "busca": {"type": "STRING", "description": "for arquivo: what file to find (e.g. 'pdf do contrato')"},
            "para": {"type": "STRING", "description": "for arquivo: 'mim' (the user) or a contact name"},
            "contato": {"type": "STRING", "description": "name or number"},
            "texto": {"type": "STRING"}, "valor": {"type": "STRING"}, "minutos": {"type": "NUMBER"},
            "n": {"type": "INTEGER"},
        },
        "required": [],
    },
}


def _ligar(valor) -> bool:
    return W._dobrar(str(valor or "ligar")) not in ("desligar", "desliga", "off", "nao", "false", "0", "parar")


def _escolher(contato: str) -> tuple[dict | None, str]:
    if not str(contato or "").strip():
        return None, "Com quem? Diga o nome do contato."
    achados = P.achar(contato)
    if not achados:
        return None, f"Não achei '{contato}' nos seus contatos do WhatsApp."
    if len(achados) > 1:
        return None, "Achei mais de um: " + ", ".join(c.get("nome") or c.get("numero") for c in achados[:5]) + \
            ". Qual deles?"
    return achados[0], ""


def _lista_auto(c: dict) -> list[str]:
    return [x.strip() for x in str(c.get("auto_contatos") or "").split(",") if x.strip()]


# ── 2.16: ouvir, ver, mandar para você e mandar arquivos ─────────────────────
def _ultima_midia(contato: dict, tipos: tuple[str, ...]) -> dict | None:
    """Baixa e entende a última mídia (dos tipos pedidos) que o contato mandou."""
    from plugins import _mensagens_midia as MM
    for m in reversed(P.mensagens(contato["id"], 30)):
        if m.get("deMim") or m.get("tipo") not in tipos or not m.get("id"):
            continue
        r = W._http("GET", "/midia?id=" + __import__("urllib.parse").parse.quote(m["id"]), None, 90)
        if r.get("erro") or not r.get("arquivo"):
            return {"erro": r.get("erro") or "não consegui baixar"}
        info = MM.entender(r["arquivo"], m.get("tipo"), contato.get("nome") or "")
        MM.guardar(contato["id"], contato.get("nome") or "", info, r["arquivo"])
        return {**info, "ts": m.get("ts")}
    return None


def achar_arquivo(busca: str) -> list:
    """Os arquivos do PC que combinam com a busca, os mais prováveis primeiro."""
    import re as _re

    from plugins.controle_sistema import buscar
    termos = str(busca or "").lower()
    ext = None
    for nome, exts in (("pdf", (".pdf",)), ("planilha", (".xlsx", ".xls", ".csv")), ("excel", (".xlsx", ".xls")),
                       ("word", (".docx", ".doc")), ("documento", (".docx", ".doc", ".pdf")), ("foto", (".jpg", ".jpeg", ".png")),
                       ("imagem", (".jpg", ".jpeg", ".png")), ("video", (".mp4", ".mov")), ("vídeo", (".mp4", ".mov")),
                       ("apresenta", (".pptx", ".pdf")), ("zip", (".zip", ".rar"))):
        if nome in termos:
            ext = exts
            termos = termos.replace(nome, " ")
    termos = _re.sub(r"\b(o|a|os|as|do|da|de|dos|das|meu|minha|arquivo|aquele|aquela|ultimo|último)\b", " ", termos)
    termos = " ".join(termos.split())
    achados = buscar(termos or busca, limite=25, segundos=10) if termos or busca else []
    if ext:
        achados = [a for a in achados if a.suffix.lower() in ext] or achados
    achados = [a for a in achados if a.is_file()]
    return sorted(achados, key=lambda a: -a.stat().st_mtime)


def _mandar_arquivo(arq, para: str, player) -> str:
    from pathlib import Path as _P
    arq = _P(arq)
    tam = arq.stat().st_size
    if tam > 60 * 1024 * 1024:
        return f"{arq.name} tem {tam // (1024 * 1024)} MB; o WhatsApp não aceita tão grande."
    if W._dobrar(para) in ("", "mim", "eu", "me", "para mim", "pra mim", "comigo"):
        if W.pronto() and W.para_donos(f"📎 {arq.name}", arq):
            registrar(player, f"WhatsApp: mandei {arq.name} para você.")
            return f"Mandei {arq.name} no seu WhatsApp."
        try:
            from plugins._notificar import enviar_arquivo
            if enviar_arquivo(arq, arq.name, "Arquivo do PC"):
                return f"O WhatsApp está desligado; mandei {arq.name} pela notificação do celular."
        except Exception:
            pass
        return "Não consegui mandar: o WhatsApp do JARVIS está desligado e não há notificação de celular configurada."
    if not W.pronto():
        return "O WhatsApp não está conectado."
    contato, erro = _escolher(para)
    if erro:
        return erro
    nome = contato.get("nome") or contato.get("numero")

    def enviar_agora() -> str:
        if W.enviar(contato["id"], "", arq, sem_prefixo=True):
            registrar(player, f"WhatsApp: mandei {arq.name} para {nome}.")
            return f"Mandei {arq.name} para {nome}."
        return "Não consegui mandar agora."
    return confirmar(f"wa_arquivo_{contato['id']}", f"Mandar arquivo para {nome}",
                     f"{arq.name} ({tam // 1024} KB)\n{arq}", enviar_agora)


def run(parameters: dict, player=None, session_memory=None) -> str:
    p = parameters or {}
    acao = W._dobrar(str(p.get("action") or "status"))
    try:
        c = W.config()
        if acao in ("secretaria", "pessoal"):
            chave = "secretaria" if acao == "secretaria" else "modo_pessoal"
            ligar = _ligar(p.get("valor"))
            salvar_cfg("whatsapp", {chave: ligar})
            W.enviar_donos_para_ponte()
            if acao == "secretaria":
                return ("Secretária ligada: ligações no WhatsApp são recusadas e eu peço um recado por mensagem."
                        if ligar else "Secretária desligada: as ligações tocam normalmente.")
            return ("Modo pessoal ligado: eu te aviso das mensagens privadas e preparo rascunhos para você aprovar."
                    if ligar else "Modo pessoal desligado: não leio mais as mensagens que chegam.")
        if acao == "ausente":
            return P.definir_ausente(_ligar(p.get("valor")), float(p.get("minutos") or 0))
        if acao in ("liberar", "bloquear"):
            nome = str(p.get("contato") or "").strip()
            if not nome:
                return "Qual contato?"
            lista = [x for x in _lista_auto(c) if W._dobrar(x) != W._dobrar(nome)]
            if acao == "liberar":
                lista.append(nome)
            salvar_cfg("whatsapp", {"auto_contatos": ", ".join(lista)})
            return (f"{nome} liberado: eu respondo como seu assistente quando ele(a) mandar mensagem."
                    + ("" if c.get("modo_pessoal") else " (Ligue o modo pessoal para isso funcionar.)")
                    if acao == "liberar" else f"{nome} fora da resposta automática.")
        if acao == "recados":
            valor = W._dobrar(str(p.get("valor") or ""))
            if valor in ("lidos", "lido", "marcar"):
                return f"Marquei {_recados.marcar_lidos()} recado(s) como lido(s)."
            if valor in ("apagar", "limpar"):
                n = len(_recados.todos())
                if not n:
                    return "Não há recados."
                return confirmar("recados_apagar", "Apagar recados", f"Apagar os {n} recado(s) guardados?",
                                 lambda: f"Apaguei {_recados.limpar()} recado(s).")
            novos = _recados.novos()
            lista = novos or _recados.todos()[-5:]
            if not lista:
                return "Nenhum recado."
            texto = _recados.texto_lista(lista)
            mostrar(player, "RECADOS", texto)
            return ("Recados novos:\n" if novos else "Nenhum recado novo. Os últimos:\n") + texto
        if acao == "status":
            e = W.estado()
            partes = [f"WhatsApp {'conectado' if e.get('estado') == 'pronto' else e.get('estado', 'desligado')}",
                      f"modo pessoal {'ligado' if c.get('modo_pessoal') else 'desligado'}",
                      f"secretária {'ligada' if c.get('secretaria') else 'desligada'}",
                      f"modo ausente {'ligado' if P.ausente() else 'desligado'}"]
            if _lista_auto(c):
                partes.append("resposta automática para " + ", ".join(_lista_auto(c)))
            n = len(_recados.novos())
            if n:
                partes.append(f"{n} recado(s) novo(s)")
            return "; ".join(partes) + "."
        if acao == "voz_alta" and not p.get("contato"):            # 2.16: ligar/desligar o aviso por voz
            ligar = _ligar(p.get("valor"))
            salvar_cfg("whatsapp", {"ler_em_voz": ligar})
            return ("Pronto: quando chegar mensagem, eu falo quem mandou e o resumo." if ligar else
                    "Pronto: não leio mais as mensagens em voz alta.") + \
                ("" if c.get("modo_pessoal") or not ligar else " (Ligue o modo pessoal para eu ver as mensagens.)")
        if acao == "midias":
            from plugins import _mensagens_midia as MM
            alvo = None
            if p.get("contato"):
                contato, erro = _escolher(p.get("contato"))
                if erro:
                    return erro
                alvo = contato["id"]
            lista = MM.recentes(alvo)[-10:]
            if not lista:
                return "Não tenho áudios nem fotos recebidos anotados (ligue o modo pessoal para eu acompanhar)."
            mostrar(player, "ÁUDIOS E FOTOS RECEBIDOS", "\n\n".join(
                f"{x['quando']} · {x['nome']} · {x['tipo']}\n{x['texto'][:600]}" for x in lista))
            return "Recebidos: " + "; ".join(f"{x['nome']} ({x['tipo']}, {x['quando'][11:]}): {x['resumo']}"
                                             for x in lista[-5:]) + "."
        if acao == "arquivo":
            busca = str(p.get("busca") or p.get("texto") or "").strip()
            if not busca:
                return "Qual arquivo?"
            achados = achar_arquivo(busca)
            if not achados:
                return f"Não achei nenhum arquivo com '{busca}' no PC."
            if len(achados) > 1:
                mostrar(player, "ARQUIVOS ACHADOS", "\n".join(f"{i}. {a}" for i, a in enumerate(achados[:10], 1)))
            r = _mandar_arquivo(achados[0], str(p.get("para") or p.get("contato") or "mim"), player)
            if len(achados) > 1:
                r += f" (Escolhi o mais recente: {achados[0].name}; os outros estão no painel.)"
            return r
        if acao == "para_mim":
            texto = str(p.get("texto") or "").strip()
            if not texto:
                return "O que eu te mando?"
            if W.pronto() and W.para_donos(f"📝 {texto}"):
                return "Mandei no seu WhatsApp."
            try:
                from plugins._notificar import enviar_push
                if enviar_push(texto, "Nota do JARVIS"):
                    return "O WhatsApp está desligado; mandei como notificação no celular."
            except Exception:
                pass
            return "Não consegui mandar: ligue o WhatsApp do JARVIS ou a notificação do celular."
        if not W.pronto():
            return "O WhatsApp não está conectado. Diga 'liga o WhatsApp' (precisa ser no seu número)."
        if acao in ("ouvir", "ver"):
            contato, erro = _escolher(p.get("contato"))
            if erro:
                return erro
            nome = contato.get("nome") or contato.get("numero")
            info = _ultima_midia(contato, ("ptt", "audio") if acao == "ouvir" else ("image", "sticker"))
            if not info:
                return f"{nome} não mandou {'áudio' if acao == 'ouvir' else 'foto'} nas últimas mensagens."
            if info.get("erro"):
                return f"Não consegui baixar: {info['erro']}."
            if acao == "ouvir":
                if not info["texto"]:
                    return f"Baixei o áudio de {nome}, mas não consegui transcrever."
                mostrar(player, f"ÁUDIO DE {nome.upper()}", info["texto"])
                return (f"Áudio de {nome}. Resumo: {info['resumo']}. Transcrição completa (conte o essencial; leia "
                        f"inteira só se ele pedir): {info['texto']}")
            return f"Foto de {nome}: {info['texto'] or 'não consegui descrever (sem a chave do Gemini)'}."
        if acao == "voz_alta":
            contato, erro = _escolher(p.get("contato"))
            if erro:
                return erro
            msgs = P.mensagens(contato["id"], max(3, min(20, int(p.get("n") or 6))))
            texto = P.formatar_conversa(contato.get("nome") or contato.get("numero"), msgs)
            return ("[LER EM VOZ ALTA] Leia estas mensagens para o usuário, em voz natural, dizendo quem falou; "
                    f"para [áudio] ofereça transcrever:\n{texto}")
        if acao in ("novas", "mensagens", "resumo"):
            chats = P.conversas(30)
            texto = P.resumo_chats(chats)
            if not texto:
                return "Nenhuma mensagem nova nas conversas privadas."
            mostrar(player, "WHATSAPP — NÃO LIDAS", texto)
            return "Mensagens não lidas (resuma em poucas frases, sem ler tudo):\n" + texto
        if acao == "ler":
            contato, erro = _escolher(p.get("contato"))
            if erro:
                return erro
            msgs = P.mensagens(contato["id"], max(3, min(40, int(p.get("n") or 15))))
            texto = P.formatar_conversa(contato.get("nome") or contato.get("numero"), msgs)
            if not texto:
                return f"A conversa com {contato.get('nome')} está vazia."
            mostrar(player, f"WHATSAPP — {contato.get('nome') or contato.get('numero')}", texto)
            return f"Conversa com {contato.get('nome')} (mais recente por último; resuma o que importa):\n{texto}"
        if acao == "mandar":
            texto = str(p.get("texto") or "").strip()
            if not texto:
                return "O que eu mando?"
            contato, erro = _escolher(p.get("contato"))
            if erro:
                return erro
            nome = contato.get("nome") or contato.get("numero")

            def enviar_agora() -> str:
                if P.mandar_como_dono(contato["id"], texto):
                    registrar(player, f"WhatsApp: mandei para {nome}: {texto[:120]}")
                    return f"Mandei para {nome}."
                return "Não consegui mandar agora (o WhatsApp está conectado?)."
            return confirmar(f"wa_mandar_{contato['id']}", f"Mandar para {nome}", f"“{texto}”", enviar_agora)
        if acao == "rascunho":
            contato, erro = _escolher(p.get("contato"))
            if erro:
                return erro
            r = P.rascunho_para(contato, str(p.get("texto") or "").strip())
            if not r["texto"]:
                return "Não consegui escrever o rascunho (sem a chave do Gemini). Me diga o que mandar."
            mostrar(player, f"RASCUNHO #{r['id']} — {r['nome']}", r["texto"])
            return (f"Rascunho #{r['id']} para {r['nome']}: “{r['texto']}”. Diga 'aprovar {r['id']}' para mandar, "
                    f"ou 'editar {r['id']}' com o texto novo.")
        return "Ação desconhecida."
    except Exception as e:
        return f"O WhatsApp falhou: {e}"
