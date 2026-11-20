package br.jarvis.app;

import android.content.Context;
import android.content.SharedPreferences;
import android.content.pm.PackageInfo;

import java.io.BufferedOutputStream;
import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.util.zip.ZipEntry;
import java.util.zip.ZipInputStream;

/**
 * Copia o projeto J.A.R.V.I.S BR (que vem dentro do APK como assets/jarvis-br.zip) para a pasta do app.
 * Roda na primeira vez e a cada atualização do app. As SUAS coisas ficam: o que está em memory/ e config/
 * e já existe no celular não é sobrescrito (memórias, listas, chave do Gemini, livro-razão…).
 */
final class Instalador {
    private Instalador() {}

    static File raiz(Context ctx) {
        return new File(ctx.getFilesDir(), "jarvis-br");
    }

    static File pastaPublica(Context ctx) {
        File f = ctx.getExternalFilesDir(null);
        return new File(f != null ? f : ctx.getFilesDir(), "JARVIS");
    }

    static void preparar(Context ctx) throws Exception {
        PackageInfo info = ctx.getPackageManager().getPackageInfo(ctx.getPackageName(), 0);
        String versao = info.versionName + "/" + info.lastUpdateTime;
        SharedPreferences prefs = ctx.getSharedPreferences("instalador", Context.MODE_PRIVATE);
        File destino = raiz(ctx);
        if (versao.equals(prefs.getString("versao", "")) && new File(destino, "celular/jarvis_celular.py").isFile()) {
            return;
        }
        extrair(ctx, ctx.getFilesDir());
        prefs.edit().putString("versao", versao).apply();
    }

    private static boolean dadoDoUsuario(String nome) {
        return nome.startsWith("jarvis-br/memory/") || nome.startsWith("jarvis-br/config/");
    }

    private static void extrair(Context ctx, File base) throws IOException {
        String raizCanonica = base.getCanonicalPath() + File.separator;
        byte[] buf = new byte[64 * 1024];
        try (InputStream in = ctx.getAssets().open("jarvis-br.zip"); ZipInputStream zip = new ZipInputStream(in)) {
            ZipEntry e;
            while ((e = zip.getNextEntry()) != null) {
                File alvo = new File(base, e.getName());
                if (!alvo.getCanonicalPath().startsWith(raizCanonica)) {
                    continue;                                     // nunca escreve fora da pasta do app
                }
                if (e.isDirectory()) {
                    alvo.mkdirs();
                    continue;
                }
                if (alvo.exists() && dadoDoUsuario(e.getName()) && !e.getName().endsWith(".py")) {
                    continue;                                     // não apaga o que é seu
                }
                File pai = alvo.getParentFile();
                if (pai != null) pai.mkdirs();
                try (OutputStream out = new BufferedOutputStream(new FileOutputStream(alvo))) {
                    int n;
                    while ((n = zip.read(buf)) > 0) out.write(buf, 0, n);
                }
            }
        }
        apagarCaches(new File(base, "jarvis-br"));
    }

    /** __pycache__ de uma versão antiga poderia esconder o código novo. */
    private static void apagarCaches(File pasta) {
        File[] filhos = pasta.listFiles();
        if (filhos == null) return;
        for (File f : filhos) {
            if (f.isDirectory()) {
                if (f.getName().equals("__pycache__")) apagar(f);
                else apagarCaches(f);
            }
        }
    }

    private static void apagar(File f) {
        File[] filhos = f.listFiles();
        if (filhos != null) for (File x : filhos) apagar(x);
        //noinspection ResultOfMethodCallIgnored
        f.delete();
    }
}
