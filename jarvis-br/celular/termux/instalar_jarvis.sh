#!/data/data/com.termux/files/usr/bin/bash
# J.A.R.V.I.S BR no celular — instalador para o Termux (Android).
# Uso: bash ~/storage/downloads/jarvis-br/celular/termux/instalar_jarvis.sh
set -e
ORIGEM="$(cd "$(dirname "$0")/../.." && pwd)"
DESTINO="$HOME/jarvis-br"

echo "== J.A.R.V.I.S BR: instalando no celular =="
[ -d "$HOME/storage" ] || termux-setup-storage || true

echo "-> Pacotes do Termux (Python e Termux:API)…"
pkg update -y
pkg install -y python termux-api

echo "-> Pacotes Python opcionais (se algum falhar, o JARVIS funciona igual)…"
pip install --upgrade pip >/dev/null 2>&1 || true
pkg install -y python-psutil >/dev/null 2>&1 && echo "   ok: psutil (pkg)" || true
for p in requests psutil; do pip install "$p" >/dev/null 2>&1 && echo "   ok: $p" || echo "   pulei: $p"; done

if [ "$ORIGEM" != "$DESTINO" ]; then
  echo "-> Copiando o JARVIS para $DESTINO (seus dados antigos ficam)…"
  mkdir -p "$DESTINO"
  cp -r "$ORIGEM"/. "$DESTINO"/
fi

echo "-> Criando o comando 'jarvis'…"
cat > "$PREFIX/bin/jarvis" <<'FIM'
#!/data/data/com.termux/files/usr/bin/bash
termux-wake-lock 2>/dev/null
cd "$HOME/jarvis-br" && exec python celular/jarvis_celular.py "$@"
FIM
chmod +x "$PREFIX/bin/jarvis"

echo "-> Abrir sozinho quando o celular ligar (precisa do app Termux:Boot)…"
mkdir -p "$HOME/.termux/boot"
cat > "$HOME/.termux/boot/jarvis.sh" <<'FIM'
#!/data/data/com.termux/files/usr/bin/bash
termux-wake-lock
cd "$HOME/jarvis-br" && python celular/jarvis_celular.py --nao-abrir > "$HOME/jarvis.log" 2>&1
FIM
chmod +x "$HOME/.termux/boot/jarvis.sh"

echo ""
echo "✔ Pronto! Digite:  jarvis"
echo "  O Chrome abre sozinho em http://localhost:8765"
echo "  Na primeira vez: Ajustes → cole a chave grátis do Gemini → Salvar."
