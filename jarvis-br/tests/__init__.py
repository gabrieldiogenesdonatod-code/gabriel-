"""
Testes do J.A.R.V.I.S BR (partes sem interface).

Rodar, da pasta do projeto:
    python -m unittest discover -s tests -v
(ou `pytest tests`, se você tiver o pytest)

Nenhum teste abre janela, usa a câmera, a internet ou mexe nos seus dados:
tudo que grava arquivo usa uma pasta temporária.
"""
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

# Fork PT-BR 1.4: o carregador de plugins anota cada chamada no diário de uso
# (memory/uso.db) e o monitor grava em memory/monitor.db. Nos testes, os dois
# vão para uma pasta temporária, apagada no fim — seus dados nunca são tocados.
import atexit
import shutil
import tempfile

TMP = Path(tempfile.mkdtemp(prefix="jarvis_testes_"))
atexit.register(shutil.rmtree, TMP, True)
import os as _os                                       # 3.9: o MINER AI grava na pasta temporária
_os.environ["MINER_AI_DADOS"] = str(TMP / "miner_ai")
try:
    from core import registro_uso as _ru
    _ru.ARQUIVO = TMP / "uso.db"
except Exception:
    pass
try:
    from plugins import _monitor_db as _mdb
    _mdb.ARQUIVO = TMP / "monitor.db"
except Exception:
    pass
# Fork PT-BR 2.4: memória em grafo, rede neural, evolução, missões, diário e
# segurança também gravam na pasta temporária durante os testes.
try:
    from core import memoria_grafo as _mg
    _mg.ARQ = TMP / "memoria_grafo.db"
    _mg.ARQ_REDE = TMP / "rede_memoria.npz"
except Exception:
    pass
try:
    from core import evolucao as _evo
    _evo.ARQ = TMP / "evolucao.json"
except Exception:
    pass
try:
    from core import missoes as _mis
    _mis.ARQ = TMP / "missoes.json"
    _mis.PASTA_LISTAS = TMP / "missoes"
except Exception:
    pass
for _mod, _attr, _nome in (("plugins.diario", "ARQ", "diario.json"),
                           ("plugins.seguranca_adaptativa", "ARQ", "seguranca_padrao.json"),
                           ("plugins.estudio_rap", "ARQ", "estudio_rap.json"),
                           # Fork PT-BR 2.5: casa, contas, foco, câmera e ESP32
                           ("plugins.contas", "ARQ", "contas.json"),
                           ("plugins.rastreio", "ARQ", "encomendas.json"),
                           ("plugins.garantias", "ARQ", "garantias.json"),
                           ("plugins.garantias", "PASTA_NOTAS", "garantias"),
                           ("plugins.garantias", "PASTA_MANUAIS", "manuais"),
                           ("plugins.ideias", "ARQ", "ideias.json"),
                           ("plugins.plantas", "ARQ", "plantas.json"),
                           ("plugins.objetos_quarto", "ARQ", "objetos_quarto.json"),
                           ("plugins.objetos_quarto", "PASTA", "quarto"),
                           ("plugins._esp32", "ARQ", "esp32.json"),
                           ("plugins.vitrine", "ARQ_ROTEIRO", "vitrine_roteiro.json"),
                           # Fork PT-BR 2.7: dupla, cinema, radionovela, neste dia, campanha
                           ("plugins._dupla", "ARQ_PERSONAGENS", "personagens.json"),
                           ("plugins.jarvis_friday", "ARQ", "jarvis_friday.json"),
                           ("plugins.cinema", "ARQ", "cinema.json"),
                           ("plugins.radionovela", "ARQ", "radionovela.json"),
                           ("plugins.neste_dia", "ARQ", "neste_dia.json"),
                           ("plugins.campanha_heroi", "ARQ", "campanha_heroi.json"),
                           # Fork PT-BR 2.8: modo dormir
                           ("core.sono", "ARQ", "sono_estado.json"),
                           ("plugins.modo_dormir", "ARQ", "modo_dormir.json"),
                           # Fork PT-BR 2.9: segundo cérebro e biblioteca de prompts
                           ("plugins.segundo_cerebro", "ARQ", "segundo_cerebro.json"),
                           ("plugins.biblioteca_prompts", "ARQ", "prompts.json"),
                           # Fork PT-BR 2.10
                           ("plugins.coach_decisao", "ARQ", "decisoes.json"),
                           # Fork PT-BR 2.11
                           ("plugins.organizador_abas", "ARQ", "sessoes_abas.json"),
                           ("plugins.modo_apresentacao", "ARQ", "apresentacao.json"),
                           ("plugins.clone_estudo", "ARQ", "estudo.json"),
                           ("plugins.preencher_form", "ARQ", "meus_dados.json"),
                           # Fork PT-BR 2.13: porteiro de voz
                           ("core.porteiro", "ARQ", "porteiro.json"),
                           # Fork PT-BR 2.18: todos os plugins do lote 2 gravam em PASTA
                           ("plugins._lote2", "PASTA", "lote2"),
                           # Fork PT-BR 3.2: anti-eco e modo anônimo
                           ("core.anti_eco", "ARQ", "anti_eco.json"),
                           ("core.anonimo", "ARQ", "modo_anonimo.json"),
                           # Fork PT-BR 3.3: caixa-preta e cápsulas do tempo (o eu do futuro sela nelas)
                           ("core.caixa_preta", "ARQ", "caixa_preta.json"),
                           ("plugins.capsula_tempo", "_ARQ", "capsulas.json"),
                           ("core.cerebro", "ARQ", "cerebro.json"),                  # 3.4
                           # 3.6: livro-razão, metacognição e OMEGA
                           ("core.livro_razao", "ARQ", "livro_razao.db"), ("core.livro_razao", "CHAVE", "livro_razao.key"),
                           ("core.metacognicao", "ARQ", "metacognicao.json"), ("core.omega", "ARQ", "omega.json")):
    try:
        import importlib as _il
        setattr(_il.import_module(_mod), _attr, TMP / _nome)
    except Exception:
        pass
