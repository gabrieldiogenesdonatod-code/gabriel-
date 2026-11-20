package br.jarvis.app;

import android.Manifest;
import android.app.Activity;
import android.content.pm.PackageManager;
import android.graphics.Color;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.text.Html;
import android.view.Window;
import android.webkit.WebChromeClient;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;

import java.io.File;
import java.lang.ref.WeakReference;
import java.util.ArrayList;

/** A tela: a mesma interface do JARVIS do celular (reator, conversa, modos, plugins, corpo, avisos, ajustes). */
public class MainActivity extends Activity {
    private static WeakReference<MainActivity> atual = new WeakReference<>(null);
    private final Handler principal = new Handler(Looper.getMainLooper());
    private WebView web;
    private boolean carregou = false, limparHistorico = false;
    private String ultimoDetalhe = "";

    static MainActivity atual() {
        return atual.get();
    }

    @Override
    protected void onCreate(Bundle b) {
        super.onCreate(b);
        atual = new WeakReference<>(this);
        Window w = getWindow();
        w.setStatusBarColor(Color.parseColor("#02070d"));
        w.setNavigationBarColor(Color.parseColor("#02070d"));

        web = new WebView(this);
        web.setBackgroundColor(Color.parseColor("#02070d"));
        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);                  // a interface guarda voz, velocidade e preferências
        s.setMediaPlaybackRequiresUserGesture(false);
        s.setAllowFileAccess(true);                    // relatórios e painel OMEGA abrem dentro do app
        web.setWebChromeClient(new WebChromeClient());
        web.setWebViewClient(new WebViewClient() {
            @Override
            public void onPageFinished(WebView v, String url) {
                if (limparHistorico && url != null && url.startsWith("http://127.0.0.1")) {
                    limparHistorico = false;
                    v.clearHistory();                  // o "voltar" não volta para a tela de carregando
                }
            }
        });
        Voz voz = Voz.instancia(this);
        voz.ligarNaPagina(web);
        web.addJavascriptInterface(voz, "JarvisVoz");
        setContentView(web);

        pedirPermissoes();
        JarvisService.iniciar(this);
        tela("Ligando o J.A.R.V.I.S…", "");
        principal.post(this::esperar);
    }

    private void pedirPermissoes() {
        ArrayList<String> p = new ArrayList<>();
        if (checkSelfPermission(Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) p.add(Manifest.permission.RECORD_AUDIO);
        if (Build.VERSION.SDK_INT >= 33 && checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED)
            p.add(Manifest.permission.POST_NOTIFICATIONS);
        if (!p.isEmpty()) requestPermissions(p.toArray(new String[0]), 1);
    }

    /** Espera o Python terminar de carregar e então abre a interface. */
    private void esperar() {
        if (carregou) return;
        String e = JarvisService.estado;
        if ("pronto".equals(e)) {
            carregou = true;
            limparHistorico = true;
            web.loadUrl("http://127.0.0.1:" + JarvisService.PORTA + "/");
            return;
        }
        if ("erro".equals(e)) {
            tela("O JARVIS não conseguiu ligar.", "Mande uma foto desta tela para corrigir:\n\n" + JarvisService.detalhe);
            return;
        }
        if (!JarvisService.detalhe.equals(ultimoDetalhe)) {
            ultimoDetalhe = JarvisService.detalhe;
            tela("Ligando o J.A.R.V.I.S…", ultimoDetalhe + "\n\nNa primeira vez demora um pouco.");
        }
        principal.postDelayed(this::esperar, 400);
    }

    private void tela(String titulo, String texto) {
        String h = "<html><head><meta name='viewport' content='width=device-width,initial-scale=1'></head>"
                + "<body style='margin:0;background:#02070d;color:#9fe8ff;font-family:sans-serif;display:flex;flex-direction:column;"
                + "align-items:center;justify-content:center;min-height:100vh;text-align:center;padding:24px;box-sizing:border-box'>"
                + "<div style='width:120px;height:120px;border-radius:50%;border:3px solid #22d3ee;box-shadow:0 0 40px #22d3ee88;"
                + "display:flex;align-items:center;justify-content:center;font-size:40px;font-weight:bold;margin-bottom:28px'>J</div>"
                + "<h2 style='font-weight:600'>" + Html.escapeHtml(titulo) + "</h2>"
                + "<pre style='white-space:pre-wrap;color:#7aa8b8;font-size:13px;text-align:left;max-width:100%'>"
                + Html.escapeHtml(texto) + "</pre></body></html>";
        web.loadDataWithBaseURL(null, h, "text/html", "utf-8", null);
    }

    /** Arquivo criado pelo JARVIS (relatório, painel OMEGA, recibo): abre aqui; o botão voltar retorna à conversa. */
    void mostrarArquivo(File f) {
        web.loadUrl(Uri.fromFile(f).toString());
    }

    @Override
    public void onBackPressed() {
        if (web != null && web.canGoBack()) web.goBack();
        else moveTaskToBack(true);                     // continua rodando (timers, lembretes)
    }

    @Override
    protected void onDestroy() {
        if (atual.get() == this) atual = new WeakReference<>(null);
        if (web != null) web.destroy();
        super.onDestroy();
    }
}
