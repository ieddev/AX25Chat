package nl.ied.ax25chat

/**
 * De gegevens voor het venster Over AX25Chat. Houd ze gelijk met gemeenschappelijk/ax25chat_over.py
 * (de knop Over… op de webpagina en in het PC-venster).
 */
object Over {
    const val NAAM = "AX25Chat"
    const val OMSCHRIJVING = "Packet-radio chatstation: chat, CQ, APRS-berichten en BBS'en via Direwolf."
    const val MAKERS = "Gert de Haan (PD3PAM) en Claude.AI"
    const val EMAIL = "ieddev@gmail.com"
    const val GITHUB = "https://github.com/ieddev/AX25Chat"
    const val LICENTIE = "EUPL-1.2 (European Union Public Licence)"

    data class Onderdeel(val naam: String, val wat: String, val licentie: String, val url: String)

    /** Onderdelen van anderen die AX25Chat gebruikt: op de Pi of PC (Direwolf, Hamlib) en in de kaart. */
    val ONDERDELEN = listOf(
        Onderdeel("Direwolf", "softwaremodem en TNC", "GPLv2", "https://github.com/wb2osz/direwolf"),
        Onderdeel("Hamlib", "CAT-besturing van de set (rigctl, rigctld)", "LGPL", "https://github.com/Hamlib/Hamlib"),
        Onderdeel("Leaflet", "kaart", "BSD-2", "https://leafletjs.com"),
        Onderdeel("PDOK / Kadaster", "BRT-Achtergrondkaart", "CC BY 4.0", "https://www.pdok.nl"),
    )
}
