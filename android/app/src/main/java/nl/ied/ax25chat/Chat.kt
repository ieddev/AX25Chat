package nl.ied.ax25chat

import android.content.Context
import android.os.Handler
import android.os.Looper
import org.json.JSONObject

/** Eén bericht, zoals de Pi het geeft (tabel berichten in berichten.db). */
data class Bericht(
    val id: Long, val tijd: Double, val richting: String, val van: String, val aan: String,
    val tekst: String, val nummer: String?, val status: String,
) {
    /** Het gesprek waar dit bericht bij hoort: 'CQ' of de roepnaam van het tegenstation. */
    val gesprek: String get() = if (aan == "CQ") "CQ" else if (richting == "uit") aan else van

    companion object {
        fun van(j: JSONObject) = Bericht(
            j.optLong("id"), j.optDouble("tijd"), j.optString("richting"), j.optString("van"), j.optString("aan"),
            j.optString("tekst"), if (j.isNull("nummer")) null else j.optString("nummer"), j.optString("status"),
        )
    }
}

/**
 * De berichten in het geheugen van de app, bijgehouden door LiveService (live) en MainActivity (bij het openen).
 * Luisteraars worden op de hoofdthread aangeroepen.
 */
object Chat {
    const val MONITOR = "MONITOR"

    val berichten = LinkedHashMap<Long, Bericht>()
    val monitor = ArrayList<String>()
    var mij = ""
    var laatst = 0.0
    @Volatile var verbonden = false
    @Volatile var zichtbaar = false          // MainActivity staat op het scherm: dan geen melding nodig
    var actief = "CQ"
    @Volatile var frequentie = ""            // bijv. '144,925 MHz', van /api/frequenties
    @Volatile var gpsStand = ""              // wat de GPS van de telefoon doet (Instellingen)

    private val hoofd = Handler(Looper.getMainLooper())
    private val luisteraars = ArrayList<() -> Unit>()

    fun luister(f: () -> Unit) { luisteraars.add(f) }
    fun stopLuisteren(f: () -> Unit) { luisteraars.remove(f) }
    private fun meld() = hoofd.post { luisteraars.toList().forEach { it() } }

    @Synchronized
    fun voegToe(b: Bericht) {
        berichten[b.id] = b
        meld()
    }

    @Synchronized
    fun monitorRegel(j: JSONObject, melden: Boolean = true) {
        val pad = j.optString("pad")
        monitor.add(j.optString("van") + ">" + j.optString("aan") + (if (pad.isNotEmpty()) ",$pad" else "") +
            ": " + j.optString("info").replace("\r", "\n").trim())
        while (monitor.size > 300) monitor.removeAt(0)
        if (melden) meld()
    }

    @Synchronized
    fun zetFrequentie(tekst: String) {
        frequentie = tekst
        meld()
    }

    @Synchronized
    fun zetVerbonden(v: Boolean) {
        if (verbonden != v) {
            verbonden = v
            meld()
        }
    }

    /** Alle berichten (opnieuw) ophalen. Op een achtergrondthread aanroepen. */
    fun laad(ctx: Context) {
        val d = Pi.haal(ctx, "/api/berichten?sinds=0")
        synchronized(this) {
            mij = d.optString("mij")
            laatst = d.optDouble("nu", 0.0)
            berichten.clear()
            val lijst = d.optJSONArray("berichten")
            if (lijst != null) for (i in 0 until lijst.length()) {
                val b = Bericht.van(lijst.getJSONObject(i))
                berichten[b.id] = b
            }
        }
        try {
            frequentie = Pi.haal(ctx, "/api/frequenties").optString("tekst")
        } catch (_: Exception) {
        }
        val m = try { Pi.haalLijst(ctx, "/api/monitor") } catch (_: Exception) { null }
        synchronized(this) {
            monitor.clear()
            if (m != null) for (i in 0 until m.length()) monitorRegel(m.getJSONObject(i), false)
        }
        meld()
    }

    @Synchronized
    fun gesprekken(): List<String> {
        val laatste = HashMap<String, Double>()
        laatste["CQ"] = 0.0
        for (b in berichten.values) laatste[b.gesprek] = maxOf(laatste[b.gesprek] ?: 0.0, b.tijd)
        if (actief != MONITOR && actief !in laatste) laatste[actief] = Double.MAX_VALUE
        val lijst = laatste.keys.sortedWith(compareBy<String> { it != "CQ" }.thenByDescending { laatste[it] })
        return lijst + MONITOR
    }

    @Synchronized
    fun vanGesprek(g: String): List<Bericht> = berichten.values.filter { it.gesprek == g }.sortedBy { it.id }

    @Synchronized
    fun wisLokaal(g: String) {
        if (g == MONITOR) monitor.clear()
        else berichten.values.removeAll { it.gesprek == g && !(it.richting == "uit" && it.status in setOf("wacht", "verzonden")) }
        meld()
    }
}
