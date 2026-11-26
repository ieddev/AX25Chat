package nl.ied.ax25chat

import android.content.Context
import android.net.ConnectivityManager
import android.net.Network
import android.net.NetworkCapabilities
import android.net.NetworkRequest
import org.json.JSONArray
import org.json.JSONObject
import java.io.BufferedReader
import java.io.InputStreamReader
import java.net.HttpURLConnection
import java.net.URL

/**
 * Praten met de Pi: dezelfde /api als de webpagina (chat/ax25chat_web.py).
 *
 * De hotspot van de Pi heeft geen internet. Android stuurt verkeer dan liever via mobiele data, en dan is
 * 10.42.0.1 onbereikbaar. Daarom bindt de app zich aan de wifi zodra die er is: dan gaat alles van de app
 * (ook de kaart en de BBS-pagina) via de wifi naar de Pi. Andere apps houden gewoon internet via 4G.
 */
object Pi {
    const val STANDAARD_ADRES = "10.42.0.1"
    private const val PREFS = "ax25chat"

    @Volatile var wifi: Network? = null
        private set

    fun adres(ctx: Context): String =
        ctx.getSharedPreferences(PREFS, Context.MODE_PRIVATE).getString("adres", STANDAARD_ADRES) ?: STANDAARD_ADRES

    fun zetAdres(ctx: Context, adres: String) {
        val schoon = adres.trim().removePrefix("http://").removePrefix("https://").trimEnd('/')
        ctx.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit()
            .putString("adres", schoon.ifEmpty { STANDAARD_ADRES }).apply()
    }

    fun meldingenAan(ctx: Context): Boolean =
        ctx.getSharedPreferences(PREFS, Context.MODE_PRIVATE).getBoolean("meldingen", true)

    fun zetMeldingen(ctx: Context, aan: Boolean) {
        ctx.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit().putBoolean("meldingen", aan).apply()
    }

    /** GPS van de telefoon naar de Pi sturen, als positie voor het APRS-baken. */
    fun gpsAan(ctx: Context): Boolean =
        ctx.getSharedPreferences(PREFS, Context.MODE_PRIVATE).getBoolean("gps", false)

    fun zetGps(ctx: Context, aan: Boolean) {
        ctx.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit().putBoolean("gps", aan).apply()
    }

    fun basis(ctx: Context) = "http://" + adres(ctx)

    /** Eén keer bij het starten: volg de wifi en bind de app eraan. */
    fun volgWifi(ctx: Context) {
        val cm = ctx.getSystemService(ConnectivityManager::class.java)
        val vraag = NetworkRequest.Builder().addTransportType(NetworkCapabilities.TRANSPORT_WIFI)
            .removeCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET).build()
        cm.registerNetworkCallback(vraag, object : ConnectivityManager.NetworkCallback() {
            override fun onAvailable(network: Network) {
                wifi = network
                cm.bindProcessToNetwork(network)
            }

            override fun onLost(network: Network) {
                if (wifi == network) {
                    wifi = null
                    cm.bindProcessToNetwork(null)
                }
            }
        })
    }

    private fun open(ctx: Context, pad: String, timeoutMs: Int): HttpURLConnection {
        val url = URL(basis(ctx) + pad)
        val c = (wifi?.openConnection(url) ?: url.openConnection()) as HttpURLConnection
        c.connectTimeout = 5000
        c.readTimeout = timeoutMs
        return c
    }

    fun haal(ctx: Context, pad: String): JSONObject {
        val c = open(ctx, pad, 15000)
        try {
            val tekst = c.inputStream.bufferedReader(Charsets.UTF_8).use { it.readText() }
            return JSONObject(tekst)
        } finally {
            c.disconnect()
        }
    }

    fun haalLijst(ctx: Context, pad: String): JSONArray {
        val c = open(ctx, pad, 15000)
        try {
            return JSONArray(c.inputStream.bufferedReader(Charsets.UTF_8).use { it.readText() })
        } finally {
            c.disconnect()
        }
    }

    fun stuur(ctx: Context, pad: String, data: JSONObject): JSONObject {
        val c = open(ctx, pad, 15000)
        try {
            c.requestMethod = "POST"
            c.doOutput = true
            c.setRequestProperty("Content-Type", "application/json; charset=utf-8")
            c.outputStream.use { it.write(data.toString().toByteArray(Charsets.UTF_8)) }
            val stroom = if (c.responseCode in 200..299) c.inputStream else c.errorStream
            val tekst = stroom?.bufferedReader(Charsets.UTF_8)?.use { it.readText() } ?: "{}"
            return JSONObject(tekst.ifBlank { "{}" })
        } finally {
            c.disconnect()
        }
    }

    /**
     * Server-sent events van /api/live lezen tot de verbinding wegvalt of stop() true geeft.
     * Per gebeurtenis: opGebeurtenis(soort, data). De Pi stuurt elke 20 s een hartslag.
     */
    fun luister(ctx: Context, stop: () -> Boolean, opGebeurtenis: (String, JSONObject) -> Unit) {
        val c = open(ctx, "/api/live", 60000)
        try {
            c.setRequestProperty("Accept", "text/event-stream")
            BufferedReader(InputStreamReader(c.inputStream, Charsets.UTF_8)).use { lezer ->
                var soort = "message"
                val data = StringBuilder()
                while (!stop()) {
                    val regel = lezer.readLine() ?: break
                    when {
                        regel.isEmpty() -> {
                            if (data.isNotEmpty()) {
                                try {
                                    opGebeurtenis(soort, JSONObject(data.toString()))
                                } catch (_: Exception) {
                                }
                            }
                            soort = "message"
                            data.setLength(0)
                        }
                        regel.startsWith("event:") -> soort = regel.substring(6).trim()
                        regel.startsWith("data:") -> data.append(regel.substring(5).trim())
                    }
                }
            }
        } finally {
            c.disconnect()
        }
    }
}
