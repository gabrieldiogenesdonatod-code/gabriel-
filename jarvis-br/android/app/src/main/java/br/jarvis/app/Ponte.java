package br.jarvis.app;

import android.app.Notification;
import android.app.NotificationManager;
import android.content.ClipData;
import android.content.ClipboardManager;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.hardware.camera2.CameraCharacteristics;
import android.hardware.camera2.CameraManager;
import android.media.AudioManager;
import android.net.Uri;
import android.os.BatteryManager;
import android.os.Handler;
import android.os.Looper;
import android.os.VibrationEffect;
import android.os.Vibrator;
import android.widget.Toast;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.File;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicReference;

/**
 * O que o Python pede ao Android. Fala a mesma "língua" dos comandos termux-* que o plugin celular_android
 * já usava no Termux, então o plugin não muda: só quem responde é o app.
 * Resposta começando com "ERRO:" vira uma exceção do lado do Python, com a mensagem.
 */
public class Ponte {
    static final String CANAL_AVISOS = "avisos";
    private static final String NAO_TEM = "ERRO: isso ainda não está no app do JARVIS (funciona na versão do Termux).";

    private final Context ctx;
    private final Handler principal = new Handler(Looper.getMainLooper());
    private int nNotificacao = 100;

    Ponte(Context ctx) {
        this.ctx = ctx.getApplicationContext();
    }

    /** Chamado pelo Python (de outra thread). */
    public String comando(String nome, String json) {
        try {
            JSONObject o = new JSONObject(json == null ? "{}" : json);
            JSONArray a = o.optJSONArray("a");
            String entrada = o.isNull("entrada") ? null : o.optString("entrada", null);
            return executar(nome, a == null ? new JSONArray() : a, entrada);
        } catch (Throwable t) {
            return "ERRO: " + t.getMessage();
        }
    }

    private String executar(String nome, JSONArray a, String entrada) throws Exception {
        switch (nome) {
            case "termux-battery-status": return bateria();
            case "termux-torch": return lanterna("on".equals(a.optString(0, "on")));
            case "termux-vibrate": return vibrar(valorDe(a, "-d", "500"));
            case "termux-notification": return notificar(valorDe(a, "--title", "J.A.R.V.I.S"), valorDe(a, "--content", "Aviso"));
            case "termux-toast": return naTela(() -> Toast.makeText(ctx, entrada != null ? entrada : a.optString(0, "J.A.R.V.I.S"), Toast.LENGTH_LONG).show());
            case "termux-clipboard-set": return copiar(entrada != null ? entrada : a.optString(0, ""));
            case "termux-clipboard-get": return colar();
            case "termux-volume": return volume(a.optInt(1, 8));
            case "termux-tts-speak": {
                Voz v = Voz.instancia(ctx);
                v.falarSistema(entrada != null ? entrada : a.optString(a.length() - 1, ""));
                return "ok";
            }
            case "termux-share": return compartilhar(entrada != null ? entrada : a.optString(a.length() - 1, ""));
            case "termux-open-url":
            case "termux-open":
            case "abrir": return abrir(a.optString(a.length() - 1, ""));
            default: return NAO_TEM;   // localização, contatos, foto, wi-fi, brilho: na próxima versão
        }
    }

    private static String valorDe(JSONArray a, String chave, String padrao) {
        for (int i = 0; i < a.length() - 1; i++) if (chave.equals(a.optString(i))) return a.optString(i + 1, padrao);
        return padrao;
    }

    private String bateria() throws Exception {
        Intent b = ctx.registerReceiver(null, new IntentFilter(Intent.ACTION_BATTERY_CHANGED));
        if (b == null) return "ERRO: não consegui ler a bateria.";
        int nivel = b.getIntExtra(BatteryManager.EXTRA_LEVEL, -1), escala = b.getIntExtra(BatteryManager.EXTRA_SCALE, 100);
        int st = b.getIntExtra(BatteryManager.EXTRA_STATUS, -1);
        String status = st == BatteryManager.BATTERY_STATUS_CHARGING ? "CHARGING" : st == BatteryManager.BATTERY_STATUS_FULL ? "FULL"
                : st == BatteryManager.BATTERY_STATUS_NOT_CHARGING ? "NOT_CHARGING" : "DISCHARGING";
        JSONObject o = new JSONObject();
        o.put("percentage", Math.round(nivel * 100f / Math.max(1, escala)));
        o.put("status", status);
        o.put("plugged", b.getIntExtra(BatteryManager.EXTRA_PLUGGED, 0) != 0 ? "PLUGGED" : "UNPLUGGED");
        o.put("temperature", b.getIntExtra(BatteryManager.EXTRA_TEMPERATURE, 0) / 10.0);
        return o.toString();
    }

    private String lanterna(boolean liga) throws Exception {
        CameraManager cm = (CameraManager) ctx.getSystemService(Context.CAMERA_SERVICE);
        for (String id : cm.getCameraIdList()) {
            Boolean tem = cm.getCameraCharacteristics(id).get(CameraCharacteristics.FLASH_INFO_AVAILABLE);
            if (Boolean.TRUE.equals(tem)) {
                cm.setTorchMode(id, liga);
                return "ok";
            }
        }
        return "ERRO: este celular não tem lanterna.";
    }

    private String vibrar(String ms) {
        Vibrator v = (Vibrator) ctx.getSystemService(Context.VIBRATOR_SERVICE);
        long t = 500;
        try { t = Math.max(50, Math.min(5000, Long.parseLong(ms.replaceAll("[^0-9]", "")))); } catch (Exception ignored) {}
        if (v != null) v.vibrate(VibrationEffect.createOneShot(t, VibrationEffect.DEFAULT_AMPLITUDE));
        return "ok";
    }

    private String notificar(String titulo, String texto) {
        JarvisService.canais(ctx);
        Notification n = new Notification.Builder(ctx, CANAL_AVISOS)
                .setContentTitle(titulo).setContentText(texto)
                .setStyle(new Notification.BigTextStyle().bigText(texto))
                .setSmallIcon(R.drawable.ic_nucleo).setAutoCancel(true).build();
        ctx.getSystemService(NotificationManager.class).notify(nNotificacao++, n);
        return "ok";
    }

    private String copiar(String texto) throws Exception {
        return naTela(() -> ((ClipboardManager) ctx.getSystemService(Context.CLIPBOARD_SERVICE))
                .setPrimaryClip(ClipData.newPlainText("JARVIS", texto)));
    }

    private String colar() throws Exception {
        AtomicReference<String> r = new AtomicReference<>("");
        naTela(() -> {
            ClipboardManager cb = (ClipboardManager) ctx.getSystemService(Context.CLIPBOARD_SERVICE);
            ClipData c = cb.getPrimaryClip();
            if (c != null && c.getItemCount() > 0 && c.getItemAt(0).getText() != null) r.set(c.getItemAt(0).getText().toString());
        });
        return r.get();
    }

    private String volume(int v) {
        AudioManager am = (AudioManager) ctx.getSystemService(Context.AUDIO_SERVICE);
        int max = am.getStreamMaxVolume(AudioManager.STREAM_MUSIC);
        am.setStreamVolume(AudioManager.STREAM_MUSIC, Math.round(Math.max(0, Math.min(15, v)) * max / 15f), 0);
        return "ok";
    }

    private String compartilhar(String texto) {
        Intent s = new Intent(Intent.ACTION_SEND).setType("text/plain").putExtra(Intent.EXTRA_TEXT, texto);
        Intent esc = Intent.createChooser(s, "Compartilhar").addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
        MainActivity m = MainActivity.atual();
        if (m != null) m.runOnUiThread(() -> m.startActivity(esc));
        else ctx.startActivity(esc);
        return "ok";
    }

    /** Link → app certo do Android. Arquivo do JARVIS (relatório, painel OMEGA) → abre dentro do próprio app. */
    private String abrir(String alvo) {
        if (alvo.isEmpty()) return "ERRO: nada para abrir.";
        MainActivity m = MainActivity.atual();
        File f = new File(alvo.startsWith("file://") ? alvo.substring(7) : alvo);
        if (f.isAbsolute() && f.exists()) {
            if (m == null) return "ERRO: abra o app do JARVIS para ver o arquivo.";
            m.runOnUiThread(() -> m.mostrarArquivo(f));
            return "ok";
        }
        Intent i = new Intent(Intent.ACTION_VIEW, Uri.parse(alvo)).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
        try {
            if (m != null) m.runOnUiThread(() -> {
                try { m.startActivity(i); } catch (Exception e) { Toast.makeText(m, "Não tenho app para abrir isso.", Toast.LENGTH_SHORT).show(); }
            });
            else ctx.startActivity(i);
            return "ok";
        } catch (Exception e) {
            return "ERRO: não tenho app para abrir " + alvo;
        }
    }

    /** Roda na thread da tela e espera (no máximo 5 s). */
    private String naTela(Runnable r) throws Exception {
        CountDownLatch fim = new CountDownLatch(1);
        AtomicReference<Throwable> erro = new AtomicReference<>();
        principal.post(() -> {
            try { r.run(); } catch (Throwable t) { erro.set(t); } finally { fim.countDown(); }
        });
        if (!fim.await(5, TimeUnit.SECONDS)) return "ERRO: o Android demorou para responder.";
        if (erro.get() != null) return "ERRO: " + erro.get().getMessage();
        return "ok";
    }
}
