"""Colinha do dev (2.18): status HTTP, comandos git/pip/PowerShell e atalhos do VS Code/Windows por assunto."""
from __future__ import annotations

from plugins._lote2 import P, norm, rodar

PLUGIN = P("colinha_dev", "Dev cheat sheet: HTTP status codes, git/pip/venv/PowerShell commands, VS Code and Windows shortcuts by topic.",
           "http | git | comando | atalho",
           "http: codigo (e.g. 404). git/comando/atalho: assunto (e.g. 'desfazer commit', 'venv', 'duplicar linha').",
           "codigo assunto")

HTTP = {200: "OK", 201: "Criado", 204: "Sem conteúdo", 301: "Movido permanente", 302: "Redirecionamento temporário",
        304: "Não modificado (cache)", 400: "Requisição inválida", 401: "Não autenticado", 403: "Proibido (sem permissão)",
        404: "Não encontrado", 405: "Método não permitido", 408: "Tempo esgotado", 409: "Conflito", 413: "Corpo grande demais",
        422: "Dados inválidos", 429: "Muitas requisições (rate limit)", 500: "Erro interno do servidor",
        502: "Bad gateway (servidor de trás caiu)", 503: "Serviço indisponível", 504: "Gateway timeout"}
GIT = {"desfazer commit": "git reset --soft HEAD~1 (mantém as mudanças)", "desfazer arquivo": "git restore arquivo",
       "nova branch": "git switch -c nome", "trocar branch": "git switch nome", "guardar": "git stash / git stash pop",
       "ver historico": "git log --oneline --graph -15", "mudar mensagem": "git commit --amend -m \"nova\"",
       "remoto": "git remote add origin URL && git push -u origin main", "tirar do git": "git rm --cached arquivo",
       "atualizar": "git pull --rebase", "conflito": "edite os <<<< >>>>, depois git add . && git rebase --continue",
       "tag": "git tag v1.0 && git push --tags", "quem mudou": "git blame arquivo"}
CMD = {"venv": "python -m venv .venv  →  .venv\\Scripts\\activate (Windows) | source .venv/bin/activate",
       "instalar requisitos": "pip install -r requirements.txt", "congelar": "pip freeze > requirements.txt",
       "desatualizados": "pip list --outdated", "matar porta": "netstat -ano | findstr :8000  →  taskkill /PID n /F",
       "ip": "ipconfig (Windows) | ip a (Linux)", "servidor rapido": "python -m http.server 8000",
       "exe": "pyinstaller --onefile --noconsole main.py", "politica ps": "Set-ExecutionPolicy -Scope CurrentUser RemoteSigned",
       "variavel ambiente": "setx NOME valor (Windows) | export NOME=valor", "espaco disco": "Get-PSDrive C",
       "docker rodando": "docker ps  (todos: docker ps -a)", "docker logs": "docker logs -f nome", "docker entrar": "docker exec -it nome sh",
       "docker compose subir": "docker compose up -d --build", "docker limpar": "docker system prune  (apaga o que não está em uso)",
       "npm instalar": "npm install  (um pacote: npm i nome)", "npm scripts": "npm run  (lista) / npm run dev",
       "npm desatualizados": "npm outdated", "node versao": "node -v && npm -v",
       "linux permissao": "chmod +x arquivo.sh", "linux procurar arquivo": "find . -name '*.py'", "linux procurar texto": "grep -rn 'texto' .",
       "linux log ao vivo": "tail -f arquivo.log", "linux disco": "df -h  (pastas: du -sh *)", "linux processos": "ps aux | grep nome  (matar: kill -9 PID)",
       "ssh chave": "ssh-keygen -t ed25519 -C \"seu@email\"  →  copie ~/.ssh/id_ed25519.pub", "pytest um teste": "pytest caminho/test_x.py::test_nome -q"}
ATALHO = {"duplicar linha": "Shift+Alt+↓", "mover linha": "Alt+↑/↓", "comentar": "Ctrl+;  ou Ctrl+/",
          "multi cursor": "Ctrl+Alt+↑/↓ ou Alt+clique", "selecionar ocorrencias": "Ctrl+D (próxima) / Ctrl+Shift+L (todas)",
          "renomear simbolo": "F2", "ir para arquivo": "Ctrl+P", "paleta": "Ctrl+Shift+P", "terminal": "Ctrl+'",
          "formatar": "Shift+Alt+F", "print parte da tela": "Win+Shift+S", "area transferencia": "Win+V",
          "emoji": "Win+.", "bloquear pc": "Win+L", "area de trabalho nova": "Win+Ctrl+D", "gerenciador tarefas": "Ctrl+Shift+Esc"}


def _http(t) -> str:
    import re
    m = re.search(r"\d{3}", str(t or ""))
    if not m:
        return "Qual código? Ex.: 404."
    c = int(m.group(0))
    return f"{c}: {HTTP.get(c, 'código incomum')}."


def procurar(tabela: dict, assunto: str) -> str:
    q = set(norm(assunto).split())
    melhor = max(tabela, key=lambda k: len(q & set(norm(k).split())), default=None)
    if not melhor or not q & set(norm(melhor).split()):
        return "Não tenho esse. Assuntos: " + ", ".join(tabela)
    return f"{melhor}: {tabela[melhor]}"


def run(parameters, player=None, session_memory=None):
    s = lambda p: p.get("assunto") or p.get("codigo") or ""  # noqa: E731
    return rodar(parameters, {
        "http": lambda p, pl: _http(p.get("codigo") or p.get("assunto")),
        "git": lambda p, pl: procurar(GIT, s(p)), "comando": lambda p, pl: procurar(CMD, s(p)),
        "atalho": lambda p, pl: procurar(ATALHO, s(p))}, player)
