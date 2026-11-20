package br.jarvis.app;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Context;
import android.content.Intent;
import android.content.pm.ServiceInfo;
import android.os.Build;
import android.os.IBinder;
import android.os.PowerManager;
import android.util.Log;

import com.chaquo.python.PyObject;
import com.chaquo.python.Python;
import com.chaquo.python.android.AndroidPlatform;

/**
 * Mantém o JARVIS vivo com o app minimizado (timers, lembretes, ciclo OMEGA) e sobe o Python uma vez só.
 * O estado (carregando / pronto / erro) fica em campos estáticos que a tela consulta.
 */
public class JarvisService extends Service {
    static final String CANAL = "jarvis";
    static final int PORTA = 8766;

    static volatile String estado = "parado";      // parado | carregando | pronto | erro
    static volatile String detalhe = "";
    static volatile Ponte ponte;

    private PowerManager.WakeLock trava;

    static void iniciar(Context ctx) {
        Intent i = new Intent(ctx, JarvisService.class);
        if (Build.VERSION.SDK_INT >= 26) ctx.startForegroundService(i);
        else ctx.startService(i);
    }

    static void canais(Context ctx) {
        NotificationManager nm = ctx.getSystemService(NotificationManager.class);
        nm.createNotificationChannel(new NotificationChannel(CANAL, "JARVIS ativo", NotificationManager.IMPORTANCE_LOW));
        nm.createNotificationChannel(new NotificationChannel(Ponte.CANAL_AVISOS, "Avisos do JARVIS", NotificationManager.IMPORTANCE_HIGH));
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        canais(this);
        PendingIntent abrir = PendingIntent.getActivity(this, 0, new Intent(this, MainActivity.class),
                PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT);
        Notification n = new Notification.Builder(this, CANAL)
                .setContentTitle("J.A.R.V.I.S")
                .setContentText("Às suas ordens. Toque para abrir.")
                .setSmallIcon(R.drawable.ic_nucleo)
                .setContentIntent(abrir)
                .setOngoing(true)
                .build();
        if (Build.VERSION.SDK_INT >= 34) startForeground(1, n, ServiceInfo.FOREGROUND_SERVICE_TYPE_SPECIAL_USE);
        else startForeground(1, n);

        if (trava == null) {
            PowerManager pm = (PowerManager) getSystemService(Context.POWER_SERVICE);
            trava = pm.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "jarvis:servidor");
            trava.setReferenceCounted(false);
            trava.acquire();
        }
        synchronized (JarvisService.class) {
            if (estado.equals("parado") || estado.equals("erro")) {
                estado = "carregando";
                detalhe = "";
                new Thread(this::subir, "jarvis-inicio").start();
            }
        }
        return START_STICKY;
    }

    private void subir() {
        try {
            detalhe = "preparando os arquivos…";
            Instalador.preparar(this);
            detalhe = "acordando o Python…";
            if (!Python.isStarted()) Python.start(new AndroidPlatform(getApplicationContext()));
            if (ponte == null) ponte = new Ponte(getApplicationContext());
            detalhe = "carregando os plugins e os modos…";
            PyObject r = Python.getInstance().getModule("jarvis_android").callAttr("iniciar_seguro",
                    Instalador.raiz(this).getAbsolutePath(), ponte, Instalador.pastaPublica(this).getAbsolutePath(), PORTA);
            String s = r.toString();
            if (s.startsWith("ERRO:")) {
                detalhe = s.substring(5);
                estado = "erro";
            } else {
                estado = "pronto";
            }
        } catch (Throwable t) {
            Log.e("JARVIS", "falhou ao iniciar", t);
            detalhe = Log.getStackTraceString(t);
            estado = "erro";
        }
    }

    @Override
    public void onDestroy() {
        if (trava != null && trava.isHeld()) trava.release();
        super.onDestroy();
    }

    @Override
    public IBinder onBind(Intent intent) {
        return null;
    }
}
