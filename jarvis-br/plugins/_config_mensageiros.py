"""Configurações do Telegram e do Discord (2.0). Começa com "_": não é ferramenta."""

PLUGIN_SETTINGS = {
    "namespace": "mensageiros",
    "title": "Telegram e Discord do JARVIS",
    "fields": [
        {"key": "telegram_token", "label": "Telegram: token do bot (do @BotFather)", "type": "password", "default": ""},
        {"key": "discord_token", "label": "Discord: token do bot", "type": "password", "default": ""},
        {"key": "discord_dono_id", "label": "Discord: o SEU ID (número; Modo desenvolvedor → Copiar ID)", "type": "text",
         "default": ""},
        {"key": "ligar_ao_abrir", "label": "Ligar o Telegram e o Discord quando o JARVIS abrir", "type": "toggle",
         "default": True},
    ],
}
