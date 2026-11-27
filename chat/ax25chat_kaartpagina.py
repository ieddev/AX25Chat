"""
ax25chat_kaartpagina.py - tabblad Kaart: de stations die de Pi hoort met een APRS-positie, op de offline kaart.

Stations zonder APRS-positie (bijv. een node of BBS) staan er ook op als hun locator bekend is: uit hun baken
(gewone tekst) of zelf ingevuld onder de kaart. Die krijgen een vierkant symbool op het midden van het
locatorvak, plus het vak zelf, omdat het geen precieze positie is. Een echte APRS-positie gaat altijd voor.

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
.stn.loc .s{border-radius:5px;border:2px dashed #6a3fa0;color:#6a3fa0;font-size:15px}
.stn.loc.oud .s{border-color:#777;color:#777}
.legenda i.loc{border-radius:3px;border:2px dashed #6a3fa0}
#locators{margin-top:14px}#locators h2{margin:0 0 4px;font-size:18px}
.locrij{display:flex;gap:8px;flex-wrap:wrap;align-items:flex-end;margin:8px 0}
.locrij label{margin:0;flex:1 1 140px}.locrij input{width:100%;text-transform:uppercase}
.loclijst{list-style:none;padding:0;margin:8px 0 0}
.loclijst li{display:flex;gap:8px;align-items:center;padding:6px 0;border-top:1px solid var(--lijn)}
.loclijst li b{min-width:110px}.loclijst li .mono{flex:1}
.loclijst button{padding:4px 10px;font-size:14px}
#loc_melding{min-height:1.4em;margin:4px 0 0}
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
var laag = L.layerGroup().addTo(map), stations = {}, locs = {}, zonder = [], eigen = null, eerste = true;
function esc(t) { var d = document.createElement('div'); d.textContent = t == null ? '' : t; return d.innerHTML; }
function geleden(t) {
  var s = Math.max(0, Date.now() / 1000 - t);
  if (s < 90) return 'net';
  if (s < 3600) return Math.round(s / 60) + ' min geleden';
  if (s < 86400) return Math.round(s / 3600) + ' uur geleden';
  return Math.round(s / 86400) + ' dag(en) geleden';
}
function icoon(s, soort) {
  var code = (s.symbool || '/.').charAt(1), teken = soort.indexOf('loc') >= 0 ? '▦' : (TEKEN[code] || '•');
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
  Object.keys(locs).forEach(function (c) {           // stations met alleen een locator
    var l = locs[c], s = stations[c];
    if (s && s.tijd >= grens) return;                // een echte APRS-positie gaat voor
    if (l.bron !== 'handmatig' && !(l.tijd >= grens)) return;
    n++;
    var oud = !l.tijd || Date.now() / 1000 - l.tijd > 3600;
    var v = l.vak, km = function (a) { return Math.round(a * 10) / 10; };
    var hoog = km((v[2] - v[0]) * 111.2), breed = km((v[3] - v[1]) * 111.2 * Math.cos(l.lat * Math.PI / 180));
    L.rectangle([[v[0], v[1]], [v[2], v[3]]], {color: oud ? '#777' : '#6a3fa0', weight: 1.5, dashArray: '5 4',
      fillOpacity: 0.07, interactive: false}).addTo(laag);
    L.marker([l.lat, l.lon], {icon: icoon({call: c}, 'loc' + (oud ? ' oud' : '')), zIndexOffset: oud ? 0 : 400}).addTo(laag)
      .bindPopup('<b>' + esc(c) + '</b> · ' + (l.tijd ? geleden(l.tijd) : 'nog niet gehoord') +
        '<br>Locator <b>' + esc(l.locator) + '</b> (' + (l.bron === 'handmatig' ? 'zelf ingevuld' : 'uit zijn baken') + ')' +
        '<br>Geen precieze positie: ergens in dit vak van ca. ' + breed + ' × ' + hoog + ' km' +
        (l.tekst ? '<br><span class="mono">' + esc(l.tekst) + '</span>' : '') +
        '<br><a href="#locators" class="loc_wijzig" data-call="' + esc(c) + '" data-loc="' + esc(l.locator) +
        '">Locator wijzigen</a> · <a href="/?aan=' + encodeURIComponent(c) + '">Bericht sturen</a>');
    punten.push([l.lat, l.lon]);
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
    stations = {}; locs = {};
    (d.stations || []).forEach(function (s) { stations[s.call] = s; });
    (d.locators || []).forEach(function (l) { locs[l.call] = l; });
    zonder = d.zonder || [];
    eigen = d.mij || null;
    teken(); lijst();
  }).catch(function () {});
}
function toepassen() { eerste = true; teken(); }                    // nieuwe periode: tekenen en inzoomen op wat je ziet
document.getElementById('kaart_uren').addEventListener('change', toepassen);
document.getElementById('kaart_toepassen').addEventListener('click', toepassen);
// -- locator per station zelf invullen (bijv. als het baken de locator in getekende letters stuurt) --
var fcall = document.getElementById('loc_call'), floc = document.getElementById('loc_loc');
function meld(t, fout) { var m = document.getElementById('loc_melding'); m.textContent = t; m.style.color = fout ? 'var(--rood)' : ''; }
function lijst() {
  var ul = document.getElementById('loc_lijst'), dl = document.getElementById('loc_gehoord');
  var zelf = Object.keys(locs).filter(function (c) { return locs[c].bron === 'handmatig'; }).sort();
  ul.innerHTML = zelf.length ? zelf.map(function (c) {
    return '<li><b>' + esc(c) + '</b><span class="mono">' + esc(locs[c].locator) + '</span>' +
      '<button type="button" class="licht" data-weg="' + esc(c) + '">Verwijderen</button></li>';
  }).join('') : '<li class="uitleg">Nog geen stations met een zelf ingevulde locator.</li>';
  var namen = zonder.concat(Object.keys(locs).filter(function (c) { return locs[c].bron !== 'handmatig'; }));
  dl.innerHTML = namen.map(function (c) { return '<option value="' + esc(c) + '">'; }).join('');
}
function zet(call, loc) {
  return fetch('/api/locator', {method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({call: call, locator: loc})}).then(function (r) { return r.json(); }).then(function (d) {
    if (d.fout) { meld(d.fout, true); return false; }
    eerste = false; laad(); return true;
  }).catch(function () { meld('De Pi antwoordt niet.', true); return false; });
}
document.getElementById('loc_opslaan').addEventListener('click', function () {
  var call = fcall.value.trim().toUpperCase(), loc = floc.value.trim().toUpperCase();
  if (!call || !loc) { meld('Vul een roepnaam en een locator in.', true); return; }
  zet(call, loc).then(function (ok) {
    if (!ok) return;
    meld(call + ' staat nu op de kaart in ' + loc + '.');
    fcall.value = ''; floc.value = '';
    map.closePopup();
  });
});
document.addEventListener('click', function (ev) {
  var t = ev.target;
  if (t.dataset && t.dataset.weg) {
    zet(t.dataset.weg, '').then(function (ok) { if (ok) meld(t.dataset.weg + ' verwijderd.'); });
  } else if (t.classList && t.classList.contains('loc_wijzig')) {
    ev.preventDefault();
    fcall.value = t.dataset.call; floc.value = t.dataset.loc;
    document.getElementById('locators').scrollIntoView({behavior: 'smooth'}); floc.focus();
  }
});
laad();
setInterval(teken, 60000);                                         // "x min geleden" en vervagen bijwerken
setInterval(laad, 300000);                                         // eigen positie (GPS) bijwerken
if (window.EventSource) {
  var bron = new EventSource('/api/live');
  bron.addEventListener('station', function (ev) {
    var s = JSON.parse(ev.data); stations[s.call] = s; teken();
  });
  bron.addEventListener('locator', laad);
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
<span><i class="mij"></i>jouw eigen positie</span><span><i class="loc"></i>alleen locator (ongeveer)</span></div>
<div id="kaart"></div>
<section id="locators"><h2>Locator per station</h2>
<p class="uitleg">Een station zonder APRS-positie (bijv. een node of BBS) komt vanzelf op de kaart als het zijn
locator als gewone tekst in het baken zet, zoals <span class="mono">JO32CD</span>. Staat de locator er in grote
getekende letters (ASCII-art) of helemaal niet in, vul hem dan hier zelf in. Een echte APRS-positie gaat altijd voor.</p>
<div class="locrij"><label>Roepnaam<input type="text" id="loc_call" list="loc_gehoord" placeholder="PD4R-12" autocomplete="off"
 autocapitalize="characters" maxlength="10"></label>
<label>Locator<input type="text" id="loc_loc" placeholder="JO32CD" autocomplete="off" autocapitalize="characters" maxlength="8"></label>
<button type="button" id="loc_opslaan">Opslaan</button></div>
<datalist id="loc_gehoord"></datalist>
<p id="loc_melding" class="uitleg"></p>
<ul class="loclijst" id="loc_lijst"></ul></section>
<script src="/leaflet/leaflet.js"></script>
<script>window.KAART = {json.dumps(kaart_info, ensure_ascii=False).replace("</", "<\\/")};</script>
<script>{JS}</script>"""
