"""
ax25chat_bbspagina.py - tabblad BBS: met één tik verbinden met een BBS uit je eigen lijst, en een terminal
met snelknoppen voor de standaardcommando's. Werkt live via /api/live (event 'bbs') en /api/bbs.
"""

import html as _html
import json

import ax25chat_rig as rig

CSS = """
.bbs-stand{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.bbs-stand b{flex:1;min-width:180px}
.bbs-kies{display:flex;gap:8px;flex-wrap:wrap;margin-top:12px}
.bbs-kies select,.bbs-kies input{flex:1 1 100%;min-width:0}.bbs-kies input{text-transform:uppercase}
.bbs-kies .info{flex-basis:100%;margin:0;color:var(--zacht);font-size:14px}
.term{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:13px;line-height:1.35;background:var(--bg);
 border:1px solid var(--lijn);border-radius:8px;padding:10px;height:min(52vh,460px);overflow:auto;white-space:pre-wrap;word-break:break-word}
.term .uit{color:var(--blauw);font-weight:600}.term .info{color:var(--zacht);font-style:italic}
.snel{display:flex;gap:6px;flex-wrap:wrap;margin:10px 0}.snel button{padding:8px 12px;font-size:15px}
.snel button b{margin-right:4px}.snel .soort{align-self:center;font-size:13px;color:var(--zacht);margin-right:2px}
.invoer{display:flex;gap:8px}.invoer input{flex:1;min-width:0;font-family:ui-monospace,Menlo,Consolas,monospace}
button:disabled{opacity:.45;cursor:default}
"""

JS = r"""
(function(){
var $ = function (s) { return document.querySelector(s); }, st = {stand: 'verbroken', tegen: ''}, lijst = [], laatste = 0;
function txt(s) { var d = document.createElement('div'); d.textContent = s == null ? '' : s; return d.innerHTML; }
function post(d) {
  return fetch('/api/bbs', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(d)})
    .then(function (r) { return r.json(); }).then(function (x) { if (x.fout) { alert(x.fout); } return x; });
}
var STAND = {verbroken: ['p-uit', 'Niet verbonden'], verbinden: ['p-let', 'Verbinden met '], verbonden: ['p-ok', 'Verbonden met '],
  verbreken: ['p-let', 'Verbreken met ']};
function tekenStand() {
  var s = STAND[st.stand] || STAND.verbroken, bezig = st.stand !== 'verbroken';
  $('.bbs-stand').innerHTML = '<span class="punt ' + s[0] + '"></span><b>' + s[1] + (bezig ? txt(st.tegen) : '') + '</b>' +
    (bezig ? '<button type="button" class="gevaar" data-verbreek>' + (st.stand === 'verbonden' ? 'Verbreken' : 'Afbreken') + '</button>' : '');
  document.querySelectorAll('.bbs-kies button[type=submit],.bbs-kies select,.bbs-kies input').forEach(function (b) { b.disabled = bezig; });
  document.querySelectorAll('.snel button[data-cmd],.invoer button,.invoer input').forEach(function (b) { b.disabled = st.stand !== 'verbonden'; });
}
// Keuzelijst met je BBS'en; de laatst gekozen blijft staan (per telefoon/laptop).
var gekozen = '';
try { gekozen = localStorage.getItem('ax25chat-bbs') || ''; } catch (e) {}
function tekenLijst() {
  var sel = $('.bbs-kies select');
  if (sel.value) gekozen = sel.value;
  if (!lijst.some(function (x) { return x.id === gekozen; })) gekozen = lijst.length ? lijst[0].id : '';
  sel.innerHTML = lijst.map(function (x) {
    return '<option value="' + txt(x.id) + '"' + (x.id === gekozen ? ' selected' : '') + '>' + txt(x.call) +
      (x.naam ? ' ' + txt(x.naam) : '') + ' · ' + txt(x.tekst) + '</option>';
  }).join('') + '<option value=""' + (gekozen ? '' : ' selected') + '>Andere roepnaam…</option>';
  kijkKeuze();
}
function kijkKeuze() {
  var v = $('.bbs-kies select').value, inp = $('.bbs-kies input');
  inp.style.display = v ? 'none' : '';
  $('.bbs-kies [data-weg]').style.display = v ? '' : 'none';
  $('.bbs-kies .info').textContent = v ? '' : 'Een nieuwe roepnaam wordt na het verbinden in de lijst bewaard (op de huidige frequentie).';
  try { if (v) localStorage.setItem('ax25chat-bbs', v); } catch (e) {}
  tekenStand();
}
// Snelknoppen passend bij wat er aan de andere kant zit: een node (BPQ e.d.), een BBS of een chatserver.
var KNOPPEN = SNEL_KNOPPEN, UITLEG = NODE_UITLEG, modus = 'bbs', nodeCmds = [], staart = '';
function tekenSnel() {
  var lijst = modus === 'node' ? nodeCmds.map(function (c) {
    var u = UITLEG[c] || ['', true];
    return [c, u[0], u[1], u[0] ? c + ': ' + u[0] : c];
  }) : KNOPPEN[modus];
  $('.snel .knoppen').innerHTML = '<span class="soort">' + {node: 'Node', bbs: 'BBS', chat: 'Chat'}[modus] + '</span>' +
    lijst.map(function (k) {
      return '<button type="button" class="licht" data-cmd="' + txt(k[0]) + '"' + (k[2] ? ' data-direct="1"' : '') +
        ' title="' + txt(k[3]) + '"><b>' + txt(k[0]) + '</b>' + (modus === 'node' ? '' : txt(k[1])) + '</button>';
    }).join('');
  tekenStand();
}
function herken(tekst) {
  staart = (staart + tekst).slice(-600);
  var regels = staart.replace(/\r\n?/g, '\n').split('\n').map(function (x) { return x.trim(); }).filter(Boolean);
  var l = regels[regels.length - 1] || '', m = l.match(/^\S+\s*\}\s*(.+)$/), oud = modus + nodeCmds.join();
  if (m) {
    var w = m[1].trim().split(/\s+/);
    if (w.length >= 3 && w.every(function (x) { return /^[A-Z][A-Z?]*$/.test(x); })) { modus = 'node'; nodeCmds = w; }
  } else if (/\/h(elp)?\b.*command|type \/h/i.test(staart.slice(-300)) && modus !== 'chat') { modus = 'chat'; }
  else if (/>\s*$/.test(l) && modus !== 'chat') { modus = 'bbs'; }
  if (modus + nodeCmds.join() !== oud) tekenSnel();
}
function regel(r) {
  if (!r || r.n <= laatste) return;
  laatste = r.n;
  if (r.soort === 'in') herken(String(r.tekst));
  if (r.soort === 'uit' && modus === 'chat' && /^\/(b|q)/i.test(r.tekst)) { modus = nodeCmds.length ? 'node' : 'bbs'; staart = ''; tekenSnel(); }
  if (r.soort === 'info' && /^Verbonden met|heeft verbinding/.test(r.tekst)) { modus = 'bbs'; nodeCmds = []; staart = ''; tekenSnel(); }
  var t = $('.term'), onder = t.scrollHeight - t.scrollTop - t.clientHeight < 40, s = document.createElement('span');
  var tekst = String(r.tekst).replace(/\r\n?/g, '\n');
  if (r.soort === 'uit') { s.className = 'uit'; s.textContent = '> ' + tekst + '\n'; }
  else if (r.soort === 'info') { s.className = 'info'; s.textContent = (t.textContent && !/\n$/.test(t.textContent) ? '\n' : '') + '— ' + tekst + '\n'; }
  else { s.textContent = tekst; }
  t.appendChild(s);
  if (onder) t.scrollTop = t.scrollHeight;
}
function haal() {
  fetch('/api/bbs').then(function (r) { return r.json(); }).then(function (d) {
    st = d; lijst = d.lijst; tekenLijst(); d.regels.forEach(regel); $('.term').scrollTop = 1e9;
  }).catch(function () {});
}
tekenSnel();
haal();
var bron = new EventSource('/api/live');
bron.addEventListener('bbs', function (e) {
  var d = JSON.parse(e.data);
  if (d.gewist) { $('.term').textContent = ''; }
  st.stand = d.stand; st.tegen = d.tegen; tekenStand(); regel(d.regel);
});
bron.addEventListener('bbslijst', function (e) { lijst = JSON.parse(e.data); tekenLijst(); });
bron.onerror = function () { $('.verbinding').textContent = 'geen verbinding met de Pi, opnieuw proberen...'; };
bron.onopen = function () { $('.verbinding').textContent = ''; haal(); };
function zend(t) { post({actie: 'stuur', tekst: t}); }
document.addEventListener('click', function (e) {
  var w = e.target.closest('[data-weg]'), k = e.target.closest('[data-cmd]'), c = $('.bbs-kies select').value,
      x = lijst.filter(function (b) { return b.id === c; })[0];
  if (w && x && confirm(x.call + ' (' + x.tekst + ') uit je lijst halen?')) { post({actie: 'weg', call: x.call, hz: x.hz}); }
  if (e.target.closest('[data-verbreek]')) { post({actie: 'verbreek'}); }
  if (e.target.closest('[data-leeg]')) { post({actie: 'wis'}); }
  if (k) {
    var c = k.dataset.cmd, inv = $('.invoer input');
    if (k.dataset.direct) { zend(c); } else { inv.value = c + ' '; inv.focus(); }
  }
});
$('.bbs-kies select').addEventListener('change', function () { gekozen = this.value; kijkKeuze(); if (!gekozen) $('.bbs-kies input').focus(); });
$('.bbs-kies').addEventListener('submit', function (e) {
  e.preventDefault();
  var c = $('.bbs-kies select').value, x = lijst.filter(function (b) { return b.id === c; })[0];
  if (x) { post({actie: 'verbind', call: x.call, hz: x.hz}); return; }
  var n = $('.bbs-kies input').value.trim().toUpperCase();
  if (n) post({actie: 'verbind', call: n, onthoud: true}).then(function (r) { if (!r.fout) { gekozen = n + '@0'; $('.bbs-kies input').value = ''; } });
});
$('.invoer').addEventListener('submit', function (e) {
  e.preventDefault(); var inv = $('.invoer input'), t = inv.value;
  post({actie: 'stuur', tekst: t}).then(function (x) { if (!x.fout) inv.value = ''; });
});
$('.bbs-nieuw').addEventListener('submit', function (e) {
  e.preventDefault(); var f = e.target;
  post({actie: 'toevoegen', call: f.call.value, hz: +f.hz.value, naam: f.naam.value}).then(function (x) {
    if (!x.fout) { gekozen = f.call.value.trim().toUpperCase() + '@' + (+f.hz.value); $('.bbs-kies select').value = ''; lijst = x.lijst || lijst;
      f.call.value = ''; f.naam.value = ''; f.closest('details').open = false; tekenLijst(); }
  });
});
})();
"""

SNEL = {
    "bbs": [("L", "lijst", True, "Lijst van berichten"), ("R", "lezen", False, "Bericht lezen: R en het nummer"),
            ("S", "sturen", False, "Bericht sturen: S en de roepnaam"), ("K", "wissen", False, "Bericht wissen: K en het nummer"),
            ("B", "afmelden", True, "Afmelden (Bye)")],
    "chat": [("/U", "wie", True, "Wie er in de chat zitten"), ("/H", "hulp", True, "Alle chatcommando's"),
             ("/B", "verlaten", True, "De chat verlaten, terug naar de node")],
}
# Uitleg bij de commando's van een node (BPQ); de knoppen zelf komen uit de prompt van de node.
NODE_UITLEG = {
    "CONNECT": ("verbinden met een ander station: CONNECT en de roepnaam", False), "C": ("verbinden: C en de roepnaam", False),
    "BYE": ("afmelden", True), "INFO": ("informatie over deze node", True), "NODES": ("andere bereikbare nodes", True),
    "ROUTES": ("routes naar buurnodes", True), "PORTS": ("poorten (frequenties) van de node", True),
    "USERS": ("wie er nu verbonden is", True), "MHEARD": ("welke stations de node gehoord heeft (MHEARD en poortnummer)", True),
    "DX": ("DX-meldingen", True), "CHAT": ("naar de chatserver", True), "CONV": ("conferentie (chat)", True),
    "BBS": ("naar de BBS", True), "MAIL": ("naar de BBS", True), "EMAIL": ("e-mail via de node", True),
    "TALK": ("praten met een gebruiker", False), "?": ("hulp", True), "HELP": ("hulp", True),
}


def html(melding_boven=""):
    keuze = rig.html_frequentie_keuze(0, "hz").replace(
        "Zelf instellen op de set (geen CAT, of een andere band)", "Frequentie niet wisselen")
    return f"""{melding_boven}<style>{CSS}</style>
<section><h2>BBS</h2>
<p class="uitleg">Verbinden met een BBS, node of ander packetstation (connected mode). Kies uit je lijst; de set gaat dan
eerst naar de frequentie die erbij hoort.</p>
<div class="bbs-stand"></div>
<form class="bbs-kies" autocomplete="off"><select aria-label="BBS"></select>
<input type="text" placeholder="Roepnaam, bijv. PD4R-12" maxlength="9" aria-label="Roepnaam">
<button type="submit">Verbinden</button><button type="button" class="licht" data-weg title="Uit de lijst halen">Verwijderen</button>
<p class="info"></p></form>
<details><summary>BBS toevoegen</summary>
<form class="bbs-nieuw" autocomplete="off">
<div class="rij"><div><label>Roepnaam <small>met SSID, bijv. PD4R-1</small></label><input type="text" name="call" maxlength="9"
 style="text-transform:uppercase" required></div>
<div><label>Naam <small>mag leeg</small></label><input type="text" name="naam" maxlength="30"></div></div>
<label>Frequentie <small>mode en snelheid komen van Mijn frequenties (tabblad Radio)</small></label>{keuze}
<div class="balk"><button type="submit">Toevoegen</button></div></form></details></section>
<section><div class="term" aria-live="polite"></div>
<div class="snel"><span class="knoppen" style="display:contents"></span><button type="button" class="licht" data-leeg style="margin-left:auto" title="Scherm leegmaken">Scherm wissen</button></div>
<form class="invoer" autocomplete="off"><input type="text" maxlength="250" placeholder="Typ een commando of tekst"
 aria-label="Invoer" enterkeyhint="send"><button type="submit">Zenden</button></form>
<p class="uitleg verbinding" style="margin:8px 0 0"></p></section>
<script>{JS.replace("SNEL_KNOPPEN", json.dumps(SNEL)).replace("NODE_UITLEG", json.dumps(NODE_UITLEG))}</script>"""
