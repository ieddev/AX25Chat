"""
ax25chat_kaartpagina.py - tabblad Kaart: de stations die de Pi hoort met een APRS-positie, op de offline kaart.

De kaarttegels staan op de Pi (eenmalig downloaden op het tabblad Radio, zie ax25chat_kaart.py) en Leaflet ook,
dus de kaart werkt zonder internet. Nieuwe posities komen live binnen via /api/live (event 'station').
De Android-app gebruikt dezelfde /api/stations en /tegels.
"""

import html
import json

e = html.escape

CSS = """
#kaart{height:calc(100vh - 190px);min-height:360px;border-radius:12px;border:1px solid var(--lijn);background:#e8ecef}
.kaartbalk{display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin-bottom:8px}
.kaartbalk select{width:auto;padding:6px 8px;font-size:14px}.kaartbalk .uitleg{margin:0}
.kaartbalk button{padding:6px 12px;font-size:14px}
.legenda{display:flex;flex-wrap:wrap;gap:4px 14px;margin:0 0 8px;font-size:14px;color:var(--zacht)}
.legenda span{display:inline-flex;align-items:center;gap:5px}
.legenda i{display:inline-block;width:14px;height:14px;border-radius:50%;background:#fff;border:3px solid #1d4f91}
.legenda i.via{border-color:#a85d00}.legenda i.oud{border-color:#777;opacity:.55}.legenda i.mij{border-color:#1e7a3a;background:#e6f4ea}
.stn{font:600 12px/1 system-ui,sans-serif;white-space:nowrap}
.stn .s{display:inline-flex;align-items:center;justify-content:center;width:24px;height:24px;border-radius:50%;
 background:#fff;border:2px solid #1d4f91;font-size:14px;box-shadow:0 1px 3px rgba(0,0,0,.35)}
.stn.via .s{border-color:#a85d00}.stn.oud .s{opacity:.55;border-color:#777}.stn.mij .s{border-color:#1e7a3a;background:#e6f4ea}
.stn .n{margin-left:3px;background:rgba(255,255,255,.85);color:#1b1f24;padding:1px 4px;border-radius:4px;vertical-align:middle}
.leaflet-popup-content{font:14px/1.4 system-ui,sans-serif}.leaflet-popup-content .mono{font-size:12px}
"""

JS = r"""
(function(){
var D = window.KAART, mij = document.body.dataset.mij;
// Een paar veelvoorkomende APRS-symbolen als teken (werkt zonder internet, geen plaatjes nodig)
var TEKEN = {'>':'🚗','<':'🏍','b':'🚲','[':'🚶','-':'🏠','k':'🚚','v':'🚐','j':'🚙','u':'🚚','s':'🚤','Y':'⛵',
  'U':'🚌','O':'🎈','\'':'✈','^':'✈','X':'🚁','_':'🌤','W':'🌤','#':'📡','&':'📡','r':'📡','y':'🏠','B':'✉',
  ';':'⛺','a':'🚑','f':'🚒','!':'🚓','P':'🚓','=':'🚆','R':'🚐','`':'📡','I':'📡','n':'📡'};
var center = D.midden || [52.2, 5.5];
var map = L.map('kaart', {minZoom: 6, maxZoom: 17}).setView(center, D.kaart ? 10 : 8);
map.attributionControl.setPrefix('Leaflet');
if (D.kaart) {
  L.tileLayer('/tegels/{z}/{x}/{y}.png', {maxNativeZoom: D.max_zoom, maxZoom: 17, attribution: D.bron}).addTo(map);
  if (D.detail_gebied && D.detail_zoom > D.max_zoom) {          // meer detail rond het midden
    var g = D.detail_gebied;
    L.tileLayer('/tegels/{z}/{x}/{y}.png', {minZoom: D.max_zoom + 1, maxNativeZoom: D.detail_zoom, maxZoom: 17,
      bounds: [[g[0], g[1]], [g[2], g[3]]]}).addTo(map);
  }
}
var laag = L.layerGroup().addTo(map), stations = {}, eigen = null, eerste = true;
function esc(t) { var d = document.createElement('div'); d.textContent = t == null ? '' : t; return d.innerHTML; }
function geleden(t) {
  var s = Math.max(0, Date.now() / 1000 - t);
  if (s < 90) return 'net';
  if (s < 3600) return Math.round(s / 60) + ' min geleden';
  if (s < 86400) return Math.round(s / 3600) + ' uur geleden';
  return Math.round(s / 86400) + ' dag(en) geleden';
}
function icoon(s, soort) {
  var code = (s.symbool || '/.').charAt(1), teken = TEKEN[code] || '•';
  return L.divIcon({className: 'stn ' + soort, iconSize: null, iconAnchor: [13, 13],
    html: '<span class="s">' + teken + '</span><span class="n">' + esc(s.call) + '</span>'});
}
function uren() { return Number(document.getElementById('kaart_uren').value); }
function teken() {
  laag.clearLayers();
  var grens = Date.now() / 1000 - uren() * 3600, punten = [], n = 0;
  Object.keys(stations).forEach(function (c) {
    var s = stations[c];
    if (s.tijd < grens) return;
    n++;
    var oud = Date.now() / 1000 - s.tijd > 3600;
    var soort = oud ? 'oud' : (s.direct ? '' : 'via');
    var extra = (s.kmh ? '<br>' + s.kmh + ' km/h, koers ' + s.koers + '°' : '') +
      (s.commentaar ? '<br>' + esc(s.commentaar) : '');
    L.marker([s.lat, s.lon], {icon: icoon(s, soort), zIndexOffset: oud ? 0 : 500}).addTo(laag)
      .bindPopup('<b>' + esc(s.call) + '</b> · ' + geleden(s.tijd) + '<br>' +
        (s.direct ? 'Direct gehoord' : 'Via ' + esc(s.via || 'digipeater')) + extra +
        '<br><span class="mono">' + s.lat.toFixed(5) + ', ' + s.lon.toFixed(5) + '</span>' +
        '<br><a href="/?aan=' + encodeURIComponent(s.call) + '">Bericht sturen</a>');
    punten.push([s.lat, s.lon]);
  });
  if (eigen) {
    L.marker([eigen.lat, eigen.lon], {icon: icoon({call: mij || 'ik', symbool: eigen.symbool}, 'mij'), zIndexOffset: 1000})
      .addTo(laag).bindPopup('<b>' + esc(mij) + '</b> (jij)<br><span class="mono">' + eigen.lat.toFixed(5) + ', ' +
        eigen.lon.toFixed(5) + '</span>');
    punten.push([eigen.lat, eigen.lon]);
  }
  document.getElementById('kaart_aantal').textContent = n === 1 ? '1 station' : n + ' stations';
  if (eerste && punten.length) {
    eerste = false;
    if (punten.length > 1) map.fitBounds(L.latLngBounds(punten), {maxZoom: 12, padding: [40, 40]});
    else map.setView(punten[0], 11);
  }
}
function laad() {
  fetch('/api/stations').then(function (r) { return r.json(); }).then(function (d) {
    stations = {};
    (d.stations || []).forEach(function (s) { stations[s.call] = s; });
    eigen = d.mij || null;
    teken();
  }).catch(function () {});
}
function toepassen() { eerste = true; teken(); }                    // nieuwe periode: tekenen en inzoomen op wat je ziet
document.getElementById('kaart_uren').addEventListener('change', toepassen);
document.getElementById('kaart_toepassen').addEventListener('click', toepassen);
laad();
setInterval(teken, 60000);                                         // "x min geleden" en vervagen bijwerken
setInterval(laad, 300000);                                         // eigen positie (GPS) bijwerken
if (window.EventSource) {
  var bron = new EventSource('/api/live');
  bron.addEventListener('station', function (ev) {
    var s = JSON.parse(ev.data); stations[s.call] = s; teken();
  });
}
})();
"""


def html_pagina(kaart_info):
    leeg = "" if kaart_info.get("kaart") else (
        "<div class='melding let'>Nog geen offline kaart: download hem eenmalig op het tabblad <a href='/radio'>Radio</a> "
        "(met internet). De stations staan er wel al op, maar zonder ondergrond.</div>")
    return f"""<style>{CSS}</style><link rel="stylesheet" href="/leaflet/leaflet.css">{leeg}
<div class="kaartbalk"><b id="kaart_aantal">0 stations</b>
<label for="kaart_uren" style="margin:0;font-weight:400">Toon stations van de</label>
<select id="kaart_uren"><option value="1">laatste uur</option>
<option value="3">laatste 3 uur</option><option value="24" selected>laatste 24 uur</option>
<option value="168">laatste week</option></select>
<button type="button" id="kaart_toepassen" class="licht">Toepassen</button></div>
<div class="legenda"><span>Kleur van het rondje:</span><span><i></i>rechtstreeks gehoord</span>
<span><i class="via"></i>gehoord via een digipeater</span><span><i class="oud"></i>langer dan 1 uur geleden</span>
<span><i class="mij"></i>jouw eigen positie</span></div>
<div id="kaart"></div>
<script src="/leaflet/leaflet.js"></script>
<script>window.KAART = {json.dumps(kaart_info, ensure_ascii=False).replace("</", "<\\/")};</script>
<script>{JS}</script>"""
