// AX25Chat voor Android: de app voor dagelijks gebruik (chat, kaart, BBS). Instellingen blijven in de webpagina op de Pi.
// Geen extra bibliotheken: alleen Android zelf en Kotlin, zodat de app klein en makkelijk te onderhouden blijft.
plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

android {
    namespace = "nl.ied.ax25chat"
    compileSdk = 34

    defaultConfig {
        applicationId = "nl.ied.ax25chat"
        minSdk = 26
        targetSdk = 34
        versionCode = (System.getenv("VERSIE_CODE") ?: "1").toInt()
        versionName = System.getenv("VERSIE_NAAM") ?: "0.1"
    }

    signingConfigs {
        // Ondertekenen met de sleutel uit de GitHub-secrets (zie docs/PROCEDURE.md, Android-app).
        // Zonder die secrets: de debug-sleutel van de bouwmachine (alleen om te testen).
        val sleutel = System.getenv("AX25CHAT_KEYSTORE")
        if (sleutel != null && file(sleutel).exists()) {
            create("uitgave") {
                storeFile = file(sleutel)
                storePassword = System.getenv("AX25CHAT_KEYSTORE_WACHTWOORD")
                keyAlias = System.getenv("AX25CHAT_KEY_ALIAS") ?: "ax25chat"
                keyPassword = System.getenv("AX25CHAT_KEY_WACHTWOORD") ?: System.getenv("AX25CHAT_KEYSTORE_WACHTWOORD")
            }
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            signingConfig = signingConfigs.findByName("uitgave") ?: signingConfigs.getByName("debug")
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions {
        jvmTarget = "17"
    }
}
