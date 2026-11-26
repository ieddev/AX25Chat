package nl.ied.ax25chat

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.os.Build
import android.os.IBinder

/**
 * Houdt de verbinding met de Pi open (/api/live), ook als de app op de achtergrond staat of het scherm uit is.
 * Een nieuw bericht aan jou of aan CQ geeft een melding. Valt de verbinding weg (buiten bereik van de hotspot),
 * dan probeert de service het elke 10 seconden opnieuw.
 *
 * Android eist bij zo'n achtergronddienst een vaste melding ("AX25Chat luistert"); die kun je in de
 * instellingen van Android verbergen.
 */
class LiveService : Service() {
    @Volatile private var stoppen = false
    private var draad: Thread? = null
    private var volgendeId = 100

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (intent?.action == STOP) {
            stoppen = true
            stopForeground(STOP_FOREGROUND_REMOVE)
            stopSelf()
            return START_NOT_STICKY
        }
        kanalen(this)
        val vast = vasteMelding("Verbinden met de Pi…")
        if (Build.VERSION.SDK_INT >= 34) {
            startForeground(VAST_ID, vast, ServiceInfo.FOREGROUND_SERVICE_TYPE_REMOTE_MESSAGING)
        } else {
            startForeground(VAST_ID, vast)
        }
        if (draad?.isAlive != true) {
            stoppen = false
            draad = Thread({ lus() }, "ax25chat-live").also { it.start() }
        }
        return START_STICKY
    }

    override fun onDestroy() {
        stoppen = true
        super.onDestroy()
    }

    private fun lus() {
        while (!stoppen) {
            try {
                Chat.laad(this)
                Chat.zetVerbonden(true)
                werkVastBij("Verbonden met " + Pi.adres(this))
                Pi.luister(this, { stoppen }) { soort, data -> gebeurtenis(soort, data) }
            } catch (_: Exception) {
            }
            Chat.zetVerbonden(false)
            if (stoppen) break
            werkVastBij("Geen verbinding met " + Pi.adres(this) + ". Ben je verbonden met de wifi van de Pi?")
            try {
                Thread.sleep(10000)
            } catch (_: InterruptedException) {
            }
        }
    }

    private fun gebeurtenis(soort: String, data: org.json.JSONObject) {
        when (soort) {
            "bericht" -> {
                val b = Bericht.van(data)
                val nieuw = !Chat.berichten.containsKey(b.id)
                Chat.voegToe(b)
                if (nieuw && b.richting == "in" && Pi.meldingenAan(this) &&
                    !(Chat.zichtbaar && Chat.actief == b.gesprek)) {
                    meldBericht(b)
                }
            }
            "monitor" -> Chat.monitorRegel(data)
        }
    }

    private fun open(gesprek: String?): PendingIntent {
        val i = Intent(this, MainActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP)
        if (gesprek != null) i.putExtra(MainActivity.GESPREK, gesprek)
        return PendingIntent.getActivity(this, gesprek?.hashCode() ?: 0, i,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
    }

    private fun vasteMelding(tekst: String): Notification =
        Notification.Builder(this, KANAAL_VAST)
            .setSmallIcon(R.drawable.ic_melding)
            .setContentTitle("AX25Chat luistert")
            .setContentText(tekst)
            .setOngoing(true)
            .setContentIntent(open(null))
            .build()

    private fun werkVastBij(tekst: String) {
        getSystemService(NotificationManager::class.java).notify(VAST_ID, vasteMelding(tekst))
    }

    private fun meldBericht(b: Bericht) {
        val titel = if (b.aan == "CQ") "CQ van ${b.van}" else b.van
        val n = Notification.Builder(this, KANAAL_BERICHT)
            .setSmallIcon(R.drawable.ic_melding)
            .setContentTitle(titel)
            .setContentText(b.tekst)
            .setStyle(Notification.BigTextStyle().bigText(b.tekst))
            .setAutoCancel(true)
            .setContentIntent(open(b.gesprek))
            .build()
        getSystemService(NotificationManager::class.java).notify(volgendeId++, n)
    }

    companion object {
        const val STOP = "nl.ied.ax25chat.STOP"
        private const val VAST_ID = 1
        private const val KANAAL_VAST = "verbinding"
        private const val KANAAL_BERICHT = "berichten"

        fun kanalen(ctx: Context) {
            val nm = ctx.getSystemService(NotificationManager::class.java)
            nm.createNotificationChannel(NotificationChannel(KANAAL_VAST, "Verbinding met de Pi",
                NotificationManager.IMPORTANCE_MIN).apply { description = "Vaste melding zolang AX25Chat luistert" })
            nm.createNotificationChannel(NotificationChannel(KANAAL_BERICHT, "Berichten",
                NotificationManager.IMPORTANCE_HIGH).apply { description = "Nieuwe berichten aan jou en aan CQ" })
        }

        fun start(ctx: Context) {
            ctx.startForegroundService(Intent(ctx, LiveService::class.java))
        }

        fun stop(ctx: Context) {
            ctx.startService(Intent(ctx, LiveService::class.java).setAction(STOP))
        }
    }
}
