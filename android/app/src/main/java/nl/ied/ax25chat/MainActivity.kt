package nl.ied.ax25chat

import android.Manifest
import android.app.Activity
import android.content.Intent
import android.content.pm.PackageManager
import android.graphics.Color
import android.graphics.Typeface
import android.graphics.drawable.GradientDrawable
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.text.Editable
import android.text.Html
import android.text.InputFilter
import android.text.InputType
import android.text.TextWatcher
import android.text.method.LinkMovementMethod
import android.util.TypedValue
import android.view.Gravity
import android.view.View
import android.view.ViewGroup
import android.view.inputmethod.EditorInfo
import android.webkit.WebResourceRequest
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.Button
import android.widget.EditText
import android.widget.FrameLayout
import android.widget.HorizontalScrollView
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.Switch
import android.widget.TextView
import android.widget.Toast
import org.json.JSONObject
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import kotlin.concurrent.thread

/**
 * Het hoofdscherm: tabbladen Chat (in de app zelf), Kaart en BBS (de pagina's van AX25Chat op de Pi of PC) en Instellingen.
 * De schermen worden in code opgebouwd, zonder layoutbestanden of extra bibliotheken.
 */
class MainActivity : Activity() {
    companion object {
        const val GESPREK = "gesprek"
        private const val BLAUW = 0xFF1D4F91.toInt()
        private const val BLAUW_Z = 0xFFE8EEF8.toInt()
        private const val GRIJS = 0xFF5B6470.toInt()
        private const val LIJN = 0xFFDDE1E6.toInt()
        private const val ACHTER = 0xFFF6F7F9.toInt()
        private const val ROOD = 0xFFB3261E.toInt()
        private const val GROEN = 0xFF1E7A3A.toInt()
        private val STAND = mapOf(
            "wacht" to "wacht op zenden", "verzonden" to "verzonden, wacht op bevestiging",
            "bevestigd" to "bevestigd ✓✓", "mislukt" to "niet bevestigd", "gestopt" to "gestopt, niet bevestigd",
            "geweigerd" to "geweigerd", "cq" to "verzonden",
        )
    }

    private lateinit var inhoud: FrameLayout
    private lateinit var tabs: LinearLayout
    private lateinit var kopStand: TextView
    private var verbindingStand: TextView? = null          // regel onder het adres in Instellingen
    private var tab = "chat"

    // chat
    private lateinit var chatScherm: LinearLayout
    private lateinit var gesprekBalk: LinearLayout
    private lateinit var gesprekKop: TextView
    private lateinit var lijst: LinearLayout
    private lateinit var lijstScroll: ScrollView
    private lateinit var aanVeld: EditText
    private lateinit var tekstVeld: EditText
    private lateinit var typen: LinearLayout

    private var web: WebView? = null
    private val ververs: () -> Unit = { tekenChat() }

    private fun dp(v: Int) = TypedValue.applyDimension(TypedValue.COMPLEX_UNIT_DIP, v.toFloat(), resources.displayMetrics).toInt()

    private fun rond(kleur: Int, rand: Int = 0, straal: Int = 12) = GradientDrawable().apply {
        setColor(kleur); cornerRadius = dp(straal).toFloat(); if (rand != 0) setStroke(dp(1), rand)
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        Pi.volgWifi(this)
        window.statusBarColor = BLAUW

        val wortel = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; setBackgroundColor(ACHTER) }
        val kop = LinearLayout(this).apply {
            setBackgroundColor(BLAUW); setPadding(dp(16), dp(12), dp(16), dp(12)); gravity = Gravity.CENTER_VERTICAL
        }
        kop.addView(TextView(this).apply {
            text = "AX25Chat"; setTextColor(Color.WHITE); textSize = 19f; typeface = Typeface.DEFAULT_BOLD
            setOnClickListener { toonOver() }                                   // tik op de naam: Over AX25Chat
        })
        kopStand = TextView(this).apply { setTextColor(0xD9FFFFFF.toInt()); textSize = 14f; setPadding(dp(10), 0, 0, 0) }
        kop.addView(kopStand, LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f))
        kop.addView(Button(this).apply {                                       // frequentie wisselen
            text = "Frequentie"; isAllCaps = false; textSize = 13f; setTextColor(Color.WHITE)
            background = rond(0x33FFFFFF, 0x66FFFFFF, 8); minHeight = 0; minimumHeight = 0
            setPadding(dp(10), dp(4), dp(10), dp(4))
            setOnClickListener { kiesFrequentie() }
        })
        wortel.addView(kop)

        inhoud = FrameLayout(this)
        wortel.addView(inhoud, LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f))

        tabs = LinearLayout(this).apply { setBackgroundColor(Color.WHITE); setPadding(dp(4), dp(4), dp(4), dp(4)) }
        for ((k, t) in listOf("chat" to "Chat", "kaart" to "Kaart", "bbs" to "BBS", "instellingen" to "Instellingen")) {
            tabs.addView(Button(this).apply {
                text = t; tag = k; isAllCaps = false; textSize = 14f
                setOnClickListener { kiesTab(k) }
            }, LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f))
        }
        wortel.addView(tabs)
        setContentView(wortel)

        bouwChat()
        if (Build.VERSION.SDK_INT >= 33 &&
            checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(arrayOf(Manifest.permission.POST_NOTIFICATIONS), 1)
        }
        LiveService.start(this)
        openGesprek(intent)
        kiesTab("chat")
    }

    override fun onRequestPermissionsResult(code: Int, permissions: Array<out String>, uitslag: IntArray) {
        super.onRequestPermissionsResult(code, permissions, uitslag)
        if (code == 2) {
            if (uitslag.isNotEmpty() && uitslag[0] == PackageManager.PERMISSION_GRANTED) LiveService.start(this)
            else {
                Pi.zetGps(this, false)
                Toast.makeText(this, "Zonder toestemming voor de locatie kan de app je positie niet sturen", Toast.LENGTH_LONG).show()
                if (tab == "instellingen") kiesTab("instellingen")
            }
        }
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        openGesprek(intent)
    }

    private fun openGesprek(i: Intent?) {
        val g = i?.getStringExtra(GESPREK) ?: return
        Chat.actief = g
        kiesTab("chat")
    }

    override fun onResume() {
        super.onResume()
        Chat.zichtbaar = true
        Chat.luister(ververs)
        tekenChat()
    }

    override fun onPause() {
        Chat.zichtbaar = false
        Chat.stopLuisteren(ververs)
        super.onPause()
    }

    @Deprecated("Deprecated in Java")
    override fun onBackPressed() {
        val w = web
        if (tab != "chat" && w != null && w.canGoBack()) w.goBack()
        else if (tab != "chat") kiesTab("chat")
        else super.onBackPressed()
    }

    // ------------------------------------------------------------------ tabbladen

    private fun kiesTab(k: String) {
        tab = k
        for (i in 0 until tabs.childCount) {
            val b = tabs.getChildAt(i) as Button
            val aan = b.tag == k
            b.setTextColor(if (aan) BLAUW else 0xFF1B1F24.toInt())
            b.background = rond(if (aan) BLAUW_Z else Color.TRANSPARENT, straal = 8)
        }
        inhoud.removeAllViews()
        when (k) {
            "chat" -> { inhoud.addView(chatScherm); tekenChat() }
            "kaart" -> inhoud.addView(webScherm("/kaart"))
            "bbs" -> inhoud.addView(webScherm("/bbs"))
            else -> inhoud.addView(instellingenScherm())
        }
    }

    /** De pagina's Kaart en BBS van AX25Chat (Pi of PC), zonder de kop en de tabbladen van de webpagina. */
    private fun webScherm(pad: String): View {
        val w = web ?: WebView(this).also { nieuw ->
            nieuw.settings.javaScriptEnabled = true
            nieuw.settings.domStorageEnabled = true
            nieuw.webViewClient = object : WebViewClient() {
                override fun shouldOverrideUrlLoading(view: WebView, req: WebResourceRequest): Boolean {
                    val u = req.url
                    if (u.host == Pi.adres(this@MainActivity).substringBefore(':') && (u.path ?: "/") in setOf("", "/", "/chat")) {
                        val aan = u.getQueryParameter("aan")                  // 'Bericht sturen' op de kaart
                        if (!aan.isNullOrBlank()) Chat.actief = aan.uppercase()
                        kiesTab("chat")
                        return true
                    }
                    return false
                }

                override fun onPageFinished(view: WebView, url: String) {
                    view.evaluateJavascript(
                        "(function(){var h=document.querySelector('header'),n=document.querySelector('nav');" +
                            "if(h)h.style.display='none';if(n)n.style.display='none';})()", null)
                }
            }
            web = nieuw
        }
        (w.parent as? ViewGroup)?.removeView(w)
        w.loadUrl(Pi.basis(this) + pad)
        return w
    }

    private fun instellingenScherm(): View {
        val s = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; setPadding(dp(16), dp(16), dp(16), dp(16)) }
        fun label(t: String) = TextView(this).apply { text = t; typeface = Typeface.DEFAULT_BOLD; setPadding(0, dp(14), 0, dp(4)) }
        fun uitleg(t: String) = TextView(this).apply { text = t; setTextColor(GRIJS); textSize = 13f }

        s.addView(label("Adres van AX25Chat (Pi of PC)"))
        val adres = EditText(this).apply {
            setText(Pi.adres(this@MainActivity)); inputType = InputType.TYPE_TEXT_VARIATION_URI; setSingleLine()
        }
        s.addView(adres)
        verbindingStand = uitleg("").also { s.addView(it) }
        tekenChat()
        s.addView(uitleg("Pi onderweg, via de hotspot van de Pi: 10.42.0.1. Pi thuis op je eigen wifi: het adres dat je router " +
            "de Pi geeft (bijv. 192.168.1.50). PC (Linux of Windows): het adres met poort dat op de PC staat onder " +
            "Status → Telefoon en app (bijv. 192.168.1.20:8080)."))
        s.addView(Button(this).apply {
            text = "Opslaan en opnieuw verbinden"; isAllCaps = false
            setOnClickListener {
                Pi.zetAdres(this@MainActivity, adres.text.toString())
                LiveService.stop(this@MainActivity)
                postDelayed({ LiveService.start(this@MainActivity) }, 500)
                Toast.makeText(this@MainActivity, "Opgeslagen", Toast.LENGTH_SHORT).show()
            }
        })

        s.addView(label("Meldingen"))
        s.addView(Switch(this).apply {
            text = "Melding bij een nieuw bericht"; isChecked = Pi.meldingenAan(this@MainActivity)
            setOnCheckedChangeListener { _, aan -> Pi.zetMeldingen(this@MainActivity, aan) }
        })
        s.addView(uitleg("De app blijft op de achtergrond verbonden met AX25Chat. Android toont daarvoor een vaste melding " +
            "'AX25Chat luistert'; die kun je bij de meldingsinstellingen van Android verbergen."))

        s.addView(label("GPS van de telefoon"))
        val gpsStand = uitleg(Chat.gpsStand)
        s.addView(Switch(this).apply {
            text = "Mijn positie naar AX25Chat sturen (voor het APRS-baken en de kaart)"; isChecked = Pi.gpsAan(this@MainActivity)
            setOnCheckedChangeListener { _, aan ->
                Pi.zetGps(this@MainActivity, aan)
                if (aan && checkSelfPermission(Manifest.permission.ACCESS_FINE_LOCATION) != PackageManager.PERMISSION_GRANTED) {
                    requestPermissions(arrayOf(Manifest.permission.ACCESS_FINE_LOCATION,
                        Manifest.permission.ACCESS_COARSE_LOCATION), 2)
                } else {
                    LiveService.start(this@MainActivity)
                }
                postDelayed({ gpsStand.text = Chat.gpsStand }, 1500)
            }
        })
        s.addView(gpsStand)
        s.addView(uitleg("Zet in AX25Chat bij het APRS-baken (tabblad Radio) 'Positie uit' op 'GPS van de telefoon' en het " +
            "baken aan. De app stuurt elke 10 seconden je positie, ook met het scherm uit. Dan heb je geen GPS-stickje nodig."))

        s.addView(label("AX25Chat instellen"))
        s.addView(uitleg("Set, roepnaam, Mijn frequenties, de BBS-lijst, het baken en de offline kaart stel je eenmalig in op " +
            "de webpagina van de Pi (tabblad Radio, gebruiker beheer) of in het AX25Chat-venster op de PC."))
        s.addView(Button(this).apply {
            text = "Webpagina van AX25Chat openen"; isAllCaps = false
            setOnClickListener { startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(Pi.basis(this@MainActivity) + "/radio"))) }
        })

        s.addView(label("Over"))
        s.addView(Button(this).apply {
            text = "Over AX25Chat…"; isAllCaps = false
            setOnClickListener { toonOver() }
        })

        s.addView(label("Stoppen"))
        s.addView(Button(this).apply {
            text = "Stoppen met luisteren"; isAllCaps = false
            setOnClickListener { LiveService.stop(this@MainActivity); finishAndRemoveTask() }
        })
        s.addView(uitleg("Versie " + packageManager.getPackageInfo(packageName, 0).versionName))
        return ScrollView(this).apply { addView(s) }
    }

    // ------------------------------------------------------------------ over

    /** Venstertje Over AX25Chat, met dezelfde gegevens als de knop Over… op de webpagina (ax25chat_over.py). */
    private fun toonOver() {
        val versie = try { packageManager.getPackageInfo(packageName, 0).versionName ?: "" } catch (_: Exception) { "" }
        val met = when (Pi.toestel(this)) {
            "Pi" -> "Raspberry Pi"
            "PC" -> "PC (Linux of Windows)"
            else -> "nog niet bekend"
        }
        val onderdelen = Over.ONDERDELEN.joinToString("") { (n, wat, lic, url) ->
            "&#8226; <a href=\"$url\">${Html.escapeHtml(n)}</a>: ${Html.escapeHtml(wat)} (${Html.escapeHtml(lic)})<br>"
        }
        val tekst = "${Html.escapeHtml(Over.OMSCHRIJVING)}<br><br>" +
            "<b>Versie app:</b> ${Html.escapeHtml(versie.ifEmpty { "onbekend" })}<br>" +
            "<b>Verbonden met:</b> ${Html.escapeHtml(met)} (${Html.escapeHtml(Pi.adres(this))})<br>" +
            "<b>Gemaakt door:</b> ${Html.escapeHtml(Over.MAKERS)}<br>" +
            "<b>Contact:</b> <a href=\"mailto:${Over.EMAIL}\">${Over.EMAIL}</a><br>" +
            "<b>Broncode:</b> <a href=\"${Over.GITHUB}\">${Over.GITHUB.removePrefix("https://")}</a><br>" +
            "<b>Licentie:</b> ${Html.escapeHtml(Over.LICENTIE)}<br><br>" +
            "<b>Met dank aan</b><br>$onderdelen"
        val inhoud = TextView(this).apply {
            text = Html.fromHtml(tekst, Html.FROM_HTML_MODE_LEGACY)
            movementMethod = LinkMovementMethod.getInstance()
            textSize = 14f; setPadding(dp(22), dp(12), dp(22), dp(4))
        }
        android.app.AlertDialog.Builder(this)
            .setTitle(Over.NAAM)
            .setView(ScrollView(this).apply { addView(inhoud) })
            .setPositiveButton("Sluiten", null)
            .show()
    }

    // ------------------------------------------------------------------ chat

    private fun bouwChat() {
        chatScherm = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }
        gesprekBalk = LinearLayout(this).apply { setPadding(dp(8), dp(8), dp(8), dp(4)) }
        chatScherm.addView(HorizontalScrollView(this).apply { isHorizontalScrollBarEnabled = false; addView(gesprekBalk) })

        val kop = LinearLayout(this).apply { gravity = Gravity.CENTER_VERTICAL; setPadding(dp(14), dp(4), dp(8), dp(4)) }
        gesprekKop = TextView(this).apply { typeface = Typeface.DEFAULT_BOLD; textSize = 15f }
        kop.addView(gesprekKop, LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f))
        kop.addView(Button(this).apply {
            text = "Wissen"; isAllCaps = false; textSize = 13f
            setOnClickListener { wis() }
        })
        chatScherm.addView(kop)

        lijst = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; setPadding(dp(12), dp(8), dp(12), dp(8)) }
        lijstScroll = ScrollView(this).apply { addView(lijst); isFillViewport = true }
        chatScherm.addView(lijstScroll, LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f))

        typen = LinearLayout(this).apply {
            setBackgroundColor(Color.WHITE); setPadding(dp(8), dp(6), dp(8), dp(6)); gravity = Gravity.CENTER_VERTICAL
        }
        aanVeld = EditText(this).apply {
            hint = "Aan"; setSingleLine(); filters = arrayOf(InputFilter.AllCaps(), InputFilter.LengthFilter(9))
            inputType = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_FLAG_CAP_CHARACTERS
        }
        typen.addView(aanVeld, LinearLayout.LayoutParams(dp(104), ViewGroup.LayoutParams.WRAP_CONTENT))
        tekstVeld = EditText(this).apply {
            hint = "Bericht"; setSingleLine(); imeOptions = EditorInfo.IME_ACTION_SEND
            inputType = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_FLAG_CAP_SENTENCES
            setOnEditorActionListener { _, actie, _ -> if (actie == EditorInfo.IME_ACTION_SEND) { verstuur(); true } else false }
        }
        typen.addView(tekstVeld, LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f))
        val teller = TextView(this).apply { setTextColor(GRIJS); textSize = 12f; setPadding(dp(4), 0, dp(4), 0) }
        tekstVeld.addTextChangedListener(object : TextWatcher {
            override fun beforeTextChanged(s: CharSequence?, a: Int, b: Int, c: Int) {}
            override fun onTextChanged(s: CharSequence?, a: Int, b: Int, c: Int) {}
            override fun afterTextChanged(s: Editable?) {
                val n = s?.length ?: 0
                teller.text = if (n > 67) "${(n + 66) / 67} delen" else if (n > 50) "$n/67" else ""
            }
        })
        typen.addView(teller)
        typen.addView(Button(this).apply { text = "Stuur"; isAllCaps = false; setOnClickListener { verstuur() } })
        chatScherm.addView(typen)
    }

    private fun tijd(t: Double) = SimpleDateFormat("HH:mm", Locale("nl", "NL")).format(Date((t * 1000).toLong()))

    private fun tekenChat() {
        if (!::chatScherm.isInitialized) return
        // Regel 1: roepnaam en verbinding; regel 2: frequentie · mode · snelheid (past zo ook op een smal scherm)
        kopStand.text = (Chat.mij.ifEmpty { "" }) + (if (Chat.verbonden) "  ●" else "  ○ geen verbinding met " + Pi.naam(this)) +
            if (Chat.verbonden && Chat.frequentie.isNotEmpty()) "\n" + Chat.frequentie else ""
        verbindingStand?.text = if (Chat.verbonden) "Verbonden met " + Pi.naam(this) + " (" + Pi.adres(this) + ")"
            else Chat.verbindingFout.ifEmpty { "Verbinden met " + Pi.adres(this) + "…" }

        gesprekBalk.removeAllViews()
        for (g in Chat.gesprekken() + "+") {
            gesprekBalk.addView(Button(this).apply {
                text = when (g) { "+" -> "+ Nieuw"; Chat.MONITOR -> "Monitor"; else -> g }
                isAllCaps = false; textSize = 14f
                val aan = g == Chat.actief
                setTextColor(if (aan) BLAUW else 0xFF1B1F24.toInt())
                background = rond(if (aan) BLAUW_Z else Color.WHITE, if (aan) BLAUW else LIJN, 8)
                setPadding(dp(12), 0, dp(12), 0)
                setOnClickListener {
                    if (g == "+") nieuwGesprek() else { Chat.actief = g; tekenChat() }
                }
            }, LinearLayout.LayoutParams(ViewGroup.LayoutParams.WRAP_CONTENT, dp(40)).apply { marginEnd = dp(6) })
        }

        val a = Chat.actief
        gesprekKop.text = when (a) {
            Chat.MONITOR -> "Monitor · alles wat " + Pi.naam(this) + " hoort"
            "CQ" -> "CQ · aan iedereen, zonder bevestiging"
            else -> "$a · bericht met bevestiging"
        }
        typen.visibility = if (a == Chat.MONITOR) View.GONE else View.VISIBLE
        if (!aanVeld.hasFocus()) aanVeld.setText(if (a == Chat.MONITOR) "" else a)

        val onderaan = lijstScroll.scrollY + lijstScroll.height >= lijst.height - dp(40)
        lijst.removeAllViews()
        if (a == Chat.MONITOR) {
            val regels = synchronized(Chat) { Chat.monitor.toList() }
            if (regels.isEmpty()) lijst.addView(leeg("Nog niets gehoord."))
            for (r in regels) lijst.addView(TextView(this).apply {
                text = r; typeface = Typeface.MONOSPACE; textSize = 12f; setPadding(0, dp(3), 0, dp(3))
            })
        } else {
            val berichten = Chat.vanGesprek(a)
            if (berichten.isEmpty()) lijst.addView(leeg(if (Chat.verbonden) "Nog geen berichten." else
                "Geen verbinding met ${Pi.naam(this)} (${Pi.adres(this)}). Pi onderweg: ben je verbonden met de wifi van de Pi? " +
                    "Kies bij de melding 'geen internet' voor Verbonden blijven. PC: staat 'Bereikbaar vanaf telefoon' aan " +
                    "en zitten telefoon en PC op dezelfde wifi?"))
            for (b in berichten) lijst.addView(bel(b))
        }
        if (onderaan) lijstScroll.post { lijstScroll.fullScroll(View.FOCUS_DOWN) }
    }

    private fun leeg(t: String) = TextView(this).apply {
        text = t; setTextColor(GRIJS); gravity = Gravity.CENTER; setPadding(dp(20), dp(40), dp(20), dp(20))
    }

    private fun bel(b: Bericht): View {
        val uit = b.richting == "uit"
        val vak = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL; setPadding(dp(12), dp(8), dp(12), dp(8))
            background = rond(if (uit) BLAUW_Z else Color.WHITE, if (b.status == "mislukt") ROOD else if (uit) 0 else LIJN)
        }
        if (!uit && b.aan == "CQ") vak.addView(TextView(this).apply {
            text = b.van; setTextColor(BLAUW); textSize = 12f; typeface = Typeface.DEFAULT_BOLD
        })
        vak.addView(TextView(this).apply { text = b.tekst; textSize = 16f; setTextColor(0xFF1B1F24.toInt()) })
        val meta = LinearLayout(this).apply { gravity = Gravity.CENTER_VERTICAL }
        val st = STAND[b.status] ?: ""
        meta.addView(TextView(this).apply {
            text = tijd(b.tijd) + if (st.isNotEmpty()) " · $st" else ""
            textSize = 12f; setTextColor(if (b.status == "bevestigd") GROEN else GRIJS)
        })
        fun knop(t: String, pad: String) = Button(this).apply {
            text = t; isAllCaps = false; textSize = 12f; minHeight = 0; minimumHeight = 0; setPadding(dp(8), dp(2), dp(8), dp(2))
            setOnClickListener { actie(pad, JSONObject().put("id", b.id)) }
        }
        if (b.status == "mislukt" || b.status == "gestopt") meta.addView(knop("Opnieuw", "/api/opnieuw"))
        if (uit && b.nummer != null && (b.status == "wacht" || b.status == "verzonden")) meta.addView(knop("Stop", "/api/stop"))
        vak.addView(meta)
        val rij = LinearLayout(this).apply { gravity = if (uit) Gravity.END else Gravity.START; setPadding(0, dp(4), 0, dp(4)) }
        rij.addView(vak, LinearLayout.LayoutParams(ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT).apply {
            if (uit) marginStart = dp(48) else marginEnd = dp(48)
        })
        return rij
    }

    /** Frequentie kiezen uit Mijn frequenties en de 2 m-kanalen (zoals bij Station op de webpagina). */
    private fun kiesFrequentie() {
        thread {
            val d = try { Pi.haal(this, "/api/frequenties") } catch (_: Exception) { null }
            runOnUiThread {
                if (d == null) {
                    Toast.makeText(this, "Geen verbinding met " + Pi.naam(this), Toast.LENGTH_SHORT).show(); return@runOnUiThread
                }
                val lijst = d.optJSONArray("keuzes") ?: return@runOnUiThread
                val huidig = d.optLong("huidig")
                val teksten = Array(lijst.length()) { i ->
                    val k = lijst.getJSONObject(i)
                    (if (k.optBoolean("eigen")) "★ " else "") + k.optString("tekst")
                }
                val gekozen = (0 until lijst.length()).firstOrNull { lijst.getJSONObject(it).optLong("hz") == huidig } ?: -1
                android.app.AlertDialog.Builder(this)
                    .setTitle(if (d.optBoolean("cat")) "Frequentie (" + Pi.naam(this) + " zet de set erop)" else "Frequentie (zet de set zelf goed: geen CAT)")
                    .setSingleChoiceItems(teksten, gekozen) { dlg, i ->
                        dlg.dismiss()
                        zetFrequentie(lijst.getJSONObject(i).optLong("hz"))
                    }
                    .setNegativeButton("Annuleren", null)
                    .show()
            }
        }
    }

    private fun zetFrequentie(hz: Long) {
        thread {
            val melding = try {
                val a = Pi.stuur(this, "/api/frequentie", JSONObject().put("hz", hz))
                if (!a.has("fout") || a.has("kort")) Chat.zetFrequentie(Chat.standVan(a).ifEmpty { Chat.frequentie })
                if (a.has("fout")) a.optString("fout") else "Frequentie: " + Chat.standVan(a)
            } catch (_: Exception) {
                "Geen verbinding met " + Pi.naam(this)
            }
            runOnUiThread { Toast.makeText(this, melding, Toast.LENGTH_LONG).show() }
        }
    }

    private fun nieuwGesprek() {
        val veld = EditText(this).apply {
            hint = "bijv. PA1ABC-9"; filters = arrayOf(InputFilter.AllCaps(), InputFilter.LengthFilter(9)); setSingleLine()
        }
        android.app.AlertDialog.Builder(this)
            .setTitle("Roepnaam van het tegenstation")
            .setView(veld)
            .setPositiveButton("OK") { _, _ ->
                val c = veld.text.toString().trim().uppercase()
                if (c.isNotEmpty()) { Chat.actief = c; tekenChat() }
            }
            .setNegativeButton("Annuleren", null)
            .show()
    }

    private fun verstuur() {
        val aan = aanVeld.text.toString().trim().uppercase().ifEmpty { Chat.actief }
        val tekst = tekstVeld.text.toString().trim()
        if (tekst.isEmpty()) return
        thread {
            try {
                val d = Pi.stuur(this, "/api/berichten", JSONObject().put("aan", aan).put("tekst", tekst))
                val fouten = d.optJSONArray("fouten")
                if (fouten != null && fouten.length() > 0) {
                    runOnUiThread { Toast.makeText(this, fouten.join("; ").replace("\"", ""), Toast.LENGTH_LONG).show() }
                    return@thread
                }
                val uit = d.optJSONArray("berichten")
                if (uit != null) for (i in 0 until uit.length()) Chat.voegToe(Bericht.van(uit.getJSONObject(i)))
                runOnUiThread {
                    tekstVeld.setText("")
                    Chat.actief = if (aan == "CQ") "CQ" else aan
                    tekenChat()
                    lijstScroll.post { lijstScroll.fullScroll(View.FOCUS_DOWN) }
                }
            } catch (e: Exception) {
                runOnUiThread { Toast.makeText(this, "Niet verstuurd: geen verbinding met " + Pi.naam(this), Toast.LENGTH_LONG).show() }
            }
        }
    }

    private fun actie(pad: String, data: JSONObject) {
        thread {
            try {
                Pi.stuur(this, pad, data)
            } catch (_: Exception) {
                runOnUiThread { Toast.makeText(this, "Geen verbinding met " + Pi.naam(this), Toast.LENGTH_SHORT).show() }
            }
        }
    }

    private fun wis() {
        val g = Chat.actief
        val naam = when (g) { Chat.MONITOR -> "de Monitor"; "CQ" -> "CQ (iedereen)"; else -> "het gesprek met $g" }
        android.app.AlertDialog.Builder(this)
            .setMessage("Berichten van $naam wissen? Ook op ${Pi.naam(this)}.")
            .setPositiveButton("Wissen") { _, _ ->
                thread {
                    try {
                        Pi.stuur(this, "/api/wis", JSONObject().put("gesprek", g))
                        Chat.wisLokaal(g)
                    } catch (_: Exception) {
                        runOnUiThread { Toast.makeText(this, "Geen verbinding met " + Pi.naam(this), Toast.LENGTH_SHORT).show() }
                    }
                }
            }
            .setNegativeButton("Annuleren", null)
            .show()
    }
}
