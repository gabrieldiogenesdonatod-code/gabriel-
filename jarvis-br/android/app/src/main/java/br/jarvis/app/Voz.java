package br.jarvis.app;

import android.content.Context;
import android.content.Intent;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.speech.RecognitionListener;
import android.speech.RecognizerIntent;
import android.speech.SpeechRecognizer;
import android.speech.tts.TextToSpeech;
import android.speech.tts.UtteranceProgressListener;
import android.webkit.JavascriptInterface;
import android.webkit.WebView;

import org.json.JSONObject;

import java.util.ArrayList;
import java.util.Locale;

/**
 * Ouvir e falar com o Android. A página do JARVIS acha que está no Chrome: este objeto aparece para ela como
 * window.JarvisVoz, e o trecho de JavaScript que o Python põe no topo da página transforma isso em
 * SpeechRecognition e speechSynthesis — o resto da interface não muda nada.
 */
public class Voz {
    private static Voz unica;

    private final Context ctx;
    private final Handler principal = new Handler(Looper.getMainLooper());
    private TextToSpeech tts;
    private boolean ttsPronto = false, ttsFalhou = false;
    private final ArrayList<String[]> naFila = new ArrayList<>();      // {texto, velocidade, id} antes do TTS ficar pronto
    private SpeechRecognizer ouvinte;
    private boolean ouvindo = false, terminou = true;
    private WebView pagina;

    static synchronized Voz instancia(Context ctx) {
        if (unica == null) unica = new Voz(ctx.getApplicationContext());
        return unica;
    }

    private Voz(Context ctx) {
        this.ctx = ctx;
        principal.post(this::criarTts);
    }

    void ligarNaPagina(WebView w) {
        pagina = w;
    }

    private void criarTts() {
        tts = new TextToSpeech(ctx, status -> {
            if (status == TextToSpeech.SUCCESS) {
                Locale br = new Locale("pt", "BR");
                if (tts.isLanguageAvailable(br) >= TextToSpeech.LANG_AVAILABLE) tts.setLanguage(br);
                ttsPronto = true;
                for (String[] f : naFila) dizer(f[0], Float.parseFloat(f[1]), f[2]);
            } else {
                ttsFalhou = true;
                for (String[] f : naFila) evento("fala_erro", f[2]);
            }
            naFila.clear();
        });
        tts.setOnUtteranceProgressListener(new UtteranceProgressListener() {
            @Override public void onStart(String id) { evento("fala_inicio", id); }
            @Override public void onDone(String id) { evento("fala_fim", id); }
            @Override public void onError(String id) { evento("fala_erro", id); }
            @Override public void onStop(String id, boolean interrompida) { evento("fala_erro", id); }
        });
    }

    private void dizer(String texto, float vel, String id) {
        tts.setSpeechRate(Math.max(0.5f, Math.min(2f, vel)));
        Bundle b = new Bundle();
        tts.speak(texto, TextToSpeech.QUEUE_ADD, b, id);
    }

    /** Fala pedida pelo Python (plugin celular_android "falar"). */
    void falarSistema(String texto) {
        principal.post(() -> falar(texto, 1f, "sistema"));
    }

    // ───────────────────────────── chamados pela página ─────────────────────────────
    @JavascriptInterface
    public void falar(String texto, float vel, String id) {
        principal.post(() -> {
            if (ttsFalhou) { evento("fala_erro", id); return; }
            if (!ttsPronto) { naFila.add(new String[]{texto, String.valueOf(vel), id}); return; }
            dizer(texto, vel, id);
        });
    }

    @JavascriptInterface
    public void parar() {
        principal.post(() -> { naFila.clear(); if (tts != null) tts.stop(); });
    }

    @JavascriptInterface
    public void ouvir(String idioma, boolean parciais) {
        principal.post(() -> comecarAOuvir(idioma, parciais));
    }

    @JavascriptInterface
    public void pararOuvir() {
        principal.post(() -> { if (ouvinte != null && ouvindo) ouvinte.stopListening(); });
    }

    // ───────────────────────────── reconhecimento de voz ─────────────────────────────
    private void comecarAOuvir(String idioma, boolean parciais) {
        if (!SpeechRecognizer.isRecognitionAvailable(ctx)) {
            evento("ouvir_erro", "service-not-allowed");
            evento("ouvir_fim", "");
            return;
        }
        if (ouvinte == null) {
            ouvinte = SpeechRecognizer.createSpeechRecognizer(ctx);
            ouvinte.setRecognitionListener(new RecognitionListener() {
                @Override public void onReadyForSpeech(Bundle p) { evento("ouvir_inicio", ""); }
                @Override public void onBeginningOfSpeech() {}
                @Override public void onRmsChanged(float db) {}
                @Override public void onBufferReceived(byte[] b) {}
                @Override public void onEndOfSpeech() {}
                @Override public void onPartialResults(Bundle r) {
                    String t = primeiro(r);
                    if (!t.isEmpty()) evento("ouvir_parcial", t);
                }
                @Override public void onResults(Bundle r) {
                    evento("ouvir_final", primeiro(r));
                    fim();
                }
                @Override public void onError(int erro) {
                    String e = erro == SpeechRecognizer.ERROR_INSUFFICIENT_PERMISSIONS ? "not-allowed"
                            : (erro == SpeechRecognizer.ERROR_NO_MATCH || erro == SpeechRecognizer.ERROR_SPEECH_TIMEOUT) ? "no-speech"
                            : erro == SpeechRecognizer.ERROR_NETWORK || erro == SpeechRecognizer.ERROR_NETWORK_TIMEOUT ? "network"
                            : "aborted";
                    evento("ouvir_erro", e);
                    fim();
                }
                @Override public void onEvent(int tipo, Bundle p) {}
            });
        }
        if (ouvindo) ouvinte.cancel();
        Intent i = new Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH)
                .putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
                .putExtra(RecognizerIntent.EXTRA_LANGUAGE, idioma)
                .putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, parciais)
                .putExtra(RecognizerIntent.EXTRA_MAX_RESULTS, 1);
        ouvindo = true;
        terminou = false;
        ouvinte.startListening(i);
    }

    private void fim() {
        ouvindo = false;
        if (!terminou) {
            terminou = true;
            evento("ouvir_fim", "");
        }
    }

    private static String primeiro(Bundle r) {
        ArrayList<String> l = r == null ? null : r.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION);
        return l == null || l.isEmpty() || l.get(0) == null ? "" : l.get(0);
    }

    private void evento(String tipo, String dado) {
        principal.post(() -> {
            if (pagina == null) return;
            pagina.evaluateJavascript("window.__jarvisVoz&&window.__jarvisVoz(" + JSONObject.quote(tipo) + ","
                    + JSONObject.quote(dado == null ? "" : dado) + ")", null);
        });
    }

    void desligar() {
        if (ouvinte != null) { ouvinte.destroy(); ouvinte = null; }
    }
}
