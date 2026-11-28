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
import android.Manifest
import android.content.pm.PackageManager
import android.location.Location
import android.location.LocationListener
import android.location.LocationManager
import android.os.Bundle
import android.os.Looper
import org.json.JSONObject
import java.net.ConnectException
import java.net.NoRouteToHostException
import java.net.SocketTimeoutException
import java.net.UnknownHostException
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/**
 * Houdt de verbinding met AX25Chat (Pi of PC) open (/api/live), ook als de app op de achtergrond staat of het scherm uit is.
 * Een nieuw bericht aan jou of aan CQ geeft een melding. Valt de verbinding weg (buiten bereik van de hotspot,
 * AX25Chat herstart), dan probeert de service het na 3 seconden opnieuw, na een paar mislukte pogingen elke 10 seconden.
 * Komt de wifi terug, dan meteen. De reden staat in Chat.verbindingFout (Instellingen en de vaste melding).
 *
 * Staat 'GPS van de telefoon' aan, dan stuurt de dienst ook elke 10 seconden de positie naar AX25Chat (/api/positie),
 * voor het APRS-baken (bron 'GPS van de telefoon' in AX25Chat) en de kaart.
 *
 * Android eist bij zo'n achtergronddienst een vaste melding ("AX25Chat luistert"); die kun je in de
 * instellingen van Android verbergen.
 */
class LiveService : Service() {
    @Volatile private var stoppen = false
    private var draad: Thread? = null
    private var volgendeId = 100
    private var gpsLuisteraar: LocationListener? = null
    @Volatile private var laatstVerstuurd = 0L

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (intent?.action == STOP) {
            stoppen = true
            wekker.wek()
            stopForeground(STOP_FOREGROUND_REMOVE)
            stopSelf()
            return START_NOT_STICKY
        }
        kanalen(this)
        val vast = vasteMelding("Verbinden met " + Pi.naam(this) + "…")
        var gps = gpsMag(this)
        if (Build.VERSION.SDK_INT >= 34) {
            try {
                startForeground(VAST_ID, vast, ServiceInfo.FOREGROUND_SERVICE_TYPE_REMOTE_MESSAGING or
                    (if (gps) ServiceInfo.FOREGROUND_SERVICE_TYPE_LOCATION else 0))
            } catch (e: SecurityException) {
                // Locatie mag niet vanaf de achtergrond starten (bijv. na een herstart): zonder GPS verder
                gps = false
                startForeground(VAST_ID, vast, ServiceInfo.FOREGROUND_SERVICE_TYPE_REMOTE_MESSAGING)
                Chat.gpsStand = "GPS start weer als je de app opent"
            }
        } else {
            startForeground(VAST_ID, vast)
        }
        if (gps) startGps() else stopGps()
        if (draad?.isAlive != true) {
            stoppen = false
            draad = Thread({ lus() }, "ax25chat-live").also { it.start() }
        }
        return START_STICKY
    }

    override fun onDestroy() {
        stoppen = true
        wekker.wek()
        stopGps()
        super.onDestroy()
    }

    private fun lus() {
        var mislukt = 0
        Pi.bijWifi = { wekker.wek() }
        while (!stoppen) {
            var reden: String
            try {
                Chat.laad(this)
                mislukt = 0
                Chat.zetFout("")
                Chat.zetVerbonden(true)
                werkVastBij("Verbonden met " + Pi.naam(this) + " (" + Pi.adres(this) + ")")
                Pi.luister(this, { stoppen }) { soort, data -> gebeurtenis(soort, data) }
                reden = Pi.naamHoofd(this) + " heeft de verbinding verbroken (herstart AX25Chat?)"
            } catch (e: Exception) {
                reden = reden(e)
            }
            Chat.zetVerbonden(false)
            if (stoppen) break
            mislukt++
            val wacht = if (mislukt <= 5) 3 else 10
            Chat.zetFout(reden + ". Opnieuw proberen om " + SimpleDateFormat("HH:mm:ss", Locale("nl", "NL"))
                .format(Date(System.currentTimeMillis() + wacht * 1000L)) + ".")
            werkVastBij("Geen verbinding met " + Pi.adres(this) + ": " + reden)
            wekker.slaap(wacht * 1000L)
        }
        Pi.bijWifi = null
    }

    /** Een foutmelding van Java in gewone woorden. */
    private fun reden(e: Exception): String = when (e) {
        is SocketTimeoutException -> Pi.naamHoofd(this) + " reageert niet op tijd"
        is ConnectException -> if (Pi.wifi == null) "Geen wifi. Ben je verbonden met de wifi van de Pi, of thuis met je eigen wifi?"
            else Pi.naamHoofd(this) + " weigert de verbinding op " + Pi.adres(this) + " (draait AX25Chat, klopt het adres? PC: staat 'Bereikbaar vanaf telefoon' aan?)"
        is NoRouteToHostException, is UnknownHostException ->
            "Niets gevonden op " + Pi.adres(this) + ". Ben je verbonden met de wifi van de Pi, of zitten telefoon en PC op dezelfde wifi?"
        is org.json.JSONException -> "Onverwacht antwoord van " + Pi.adres(this) + " (is dit AX25Chat?)"
        else -> "Verbinding mislukt (" + (e.message ?: e.javaClass.simpleName) + ")"
    }

    /** Wachten tot de volgende poging, of eerder als de wifi terugkomt. */
    private val wekker = object {
        private val slot = Object()
        private var gewekt = false
        fun slaap(ms: Long) = synchronized(slot) {
            if (!gewekt) try { slot.wait(ms) } catch (_: InterruptedException) {}
            gewekt = false
        }
        fun wek() = synchronized(slot) { gewekt = true; slot.notifyAll() }
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
            "frequentie" -> Chat.zetFrequentie(data.optString("tekst"))
        }
    }

    // ------------------------------------------------------------ GPS van de telefoon

    private fun startGps() {
        if (gpsLuisteraar != null) return
        val lm = getSystemService(LocationManager::class.java)
        val l = object : LocationListener {
            override fun onLocationChanged(loc: Location) = nieuwePositie(loc)
            override fun onProviderDisabled(provider: String) { Chat.gpsStand = "Locatie staat uit in Android" }
            override fun onProviderEnabled(provider: String) { Chat.gpsStand = "Wacht op een GPS-positie…" }
            @Deprecated("Deprecated in Java")
            override fun onStatusChanged(provider: String?, status: Int, extras: Bundle?) {}
        }
        try {
            lm.requestLocationUpdates(LocationManager.GPS_PROVIDER, 5000L, 0f, l, Looper.getMainLooper())
            gpsLuisteraar = l
            Chat.gpsStand = if (lm.isProviderEnabled(LocationManager.GPS_PROVIDER)) "Wacht op een GPS-positie…"
                else "Locatie staat uit in Android"
        } catch (e: SecurityException) {
            Chat.gpsStand = "Geen toestemming voor de locatie"
        } catch (e: IllegalArgumentException) {
            Chat.gpsStand = "Deze telefoon heeft geen GPS"
        }
    }

    private fun stopGps() {
        val l = gpsLuisteraar ?: return
        getSystemService(LocationManager::class.java).removeUpdates(l)
        gpsLuisteraar = null
        Chat.gpsStand = ""
    }

    private fun nieuwePositie(loc: Location) {
        val nu = System.currentTimeMillis()
        if (nu - laatstVerstuurd < 10000) return
        laatstVerstuurd = nu
        val d = JSONObject().put("lat", loc.latitude).put("lon", loc.longitude)
        if (loc.hasSpeed()) d.put("kmh", loc.speed * 3.6)
        if (loc.hasBearing()) d.put("koers", loc.bearing.toDouble())
        Thread {
            Chat.gpsStand = try {
                val a = Pi.stuur(this, "/api/positie", d)
                if (a.has("fout")) Pi.naamHoofd(this) + " weigert de positie: " + a.optString("fout")
                else "Positie naar " + Pi.naam(this) + " gestuurd (" + String.format("%.5f, %.5f", loc.latitude, loc.longitude) + ")" +
                    if (a.optString("bron") != "telefoon") ". Let op: kies in AX25Chat bij het baken 'GPS van de telefoon'." else ""
            } catch (_: Exception) {
                "GPS werkt, maar geen verbinding met " + Pi.naam(this)
            }
        }.start()
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
            nm.createNotificationChannel(NotificationChannel(KANAAL_VAST, "Verbinding met AX25Chat",
                NotificationManager.IMPORTANCE_MIN).apply { description = "Vaste melding zolang AX25Chat luistert" })
            nm.createNotificationChannel(NotificationChannel(KANAAL_BERICHT, "Berichten",
                NotificationManager.IMPORTANCE_HIGH).apply { description = "Nieuwe berichten aan jou en aan CQ" })
        }

        /** GPS aangezet in de app, en Android geeft toestemming? */
        fun gpsMag(ctx: Context) = Pi.gpsAan(ctx) &&
            ctx.checkSelfPermission(Manifest.permission.ACCESS_FINE_LOCATION) == PackageManager.PERMISSION_GRANTED

        fun start(ctx: Context) {
            ctx.startForegroundService(Intent(ctx, LiveService::class.java))
        }

        fun stop(ctx: Context) {
            ctx.startService(Intent(ctx, LiveService::class.java).setAction(STOP))
        }
    }
}
