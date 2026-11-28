"""
ax25chat_chatpagina.py - de chatpagina op http://10.42.0.1 (stap 2: eenvoudig, op de Pi zelf).

Gesprekken links/boven (CQ, per tegenstation, Monitor), berichten in het midden, typen onderaan.
Nieuwe berichten en de stand (verzonden, bevestigd) komen live binnen via /api/live (server-sent events).
De echte webapp voor telefoon en laptop volgt in stap 3; die gebruikt dezelfde /api.
"""

CSS = """
.chat{display:grid;grid-template-columns:200px 1fr;gap:12px;height:calc(100vh - 150px);min-height:420px}
@media(max-width:640px){.chat{grid-template-columns:1fr;height:auto}}
.gesprekken{display:flex;flex-direction:column;gap:4px;overflow:auto}
@media(max-width:640px){.gesprekken{flex-direction:row;flex-wrap:nowrap;overflow-x:auto;padding-bottom:4px}}
.gesprekken button{background:var(--kaart);color:var(--tekst);border:1px solid var(--lijn);text-align:left;
 font-weight:500;padding:8px 12px;white-space:nowrap;position:relative}
.gesprekken button.actief{background:var(--blauw-z);color:var(--blauw);border-color:var(--blauw)}
.gesprekken .nieuw{display:inline-block;min-width:8px;height:8px;border-radius:4px;background:var(--rood);margin-left:6px}
.venster{display:flex;flex-direction:column;background:var(--kaart);border:1px solid var(--lijn);border-radius:12px;min-height:0;min-width:0}
@media(max-width:640px){.venster{height:calc(100vh - 210px);min-height:380px}}
.kop{padding:10px 14px;border-bottom:1px solid var(--lijn);font-weight:600;display:flex;gap:8px;align-items:center}
.kop small{font-weight:400;color:var(--zacht)}
.kop .wis{margin-left:auto;padding:4px 10px;font-size:13px}
.lijst{flex:1;overflow-y:auto;padding:12px;display:flex;flex-direction:column;gap:8px}
.bel{max-width:80%;padding:8px 12px;border-radius:12px;background:var(--bg);border:1px solid var(--lijn);word-wrap:break-word}
.bel.uit{align-self:flex-end;background:var(--blauw-z);border-color:transparent}
.bel .meta{font-size:12px;color:var(--zacht);margin-top:2px}
.bel .van{font-size:12px;font-weight:600;color:var(--blauw)}
.bel.mislukt{border-color:var(--rood)}
.bel button{padding:2px 8px;font-size:12px;margin-left:6px}
.mon{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:12.5px;border-bottom:1px solid var(--lijn);padding:4px 0;word-break:break-all}
.mon .t{color:var(--zacht)}
.mon .i{white-space:pre-wrap;word-break:break-all}.mon .i.blok{display:block;margin-top:2px;line-height:1.2;white-space:pre;overflow-x:auto;word-break:normal}
.typen{display:flex;gap:8px;padding:10px;border-top:1px solid var(--lijn)}
.typen input[name=aan]{width:104px;flex:0 0 104px;text-transform:uppercase;padding:10px 8px}
.typen input[name=tekst]{flex:1;min-width:0}
.typen button{padding:10px 14px}
.typen .teller{align-self:center;font-size:12px;color:var(--zacht)}.typen .teller:empty{display:none}
.leeg{color:var(--zacht);text-align:center;margin:auto;padding:20px}
"""

JS = r"""
(function(){
var mij = document.body.dataset.mij, berichten = {}, monitor = [], actief = 'MONITOR', laatst = 0, gelezen = {};   // start op de Monitor: wie komt er door
try { gelezen = JSON.parse(localStorage.getItem('ax25chat-gelezen') || '{}'); } catch (e) {}
var gevraagd = (new URLSearchParams(location.search).get('aan') || '').trim().toUpperCase();   // van de kaart: 'Bericht sturen'
if (/^[A-Z0-9]{1,6}(-\d{1,2})?$/.test(gevraagd)) actief = gevraagd;
var $ = function (s) { return document.querySelector(s); };
function tegen(b) { return b.aan === 'CQ' ? 'CQ' : (b.richting === 'uit' ? b.aan : b.van); }
function tijd(t) { var d = new Date(t * 1000); return d.toLocaleTimeString('nl-NL', {hour: '2-digit', minute: '2-digit'}); }
function txt(s) { var d = document.createElement('div'); d.textContent = s == null ? '' : s; return d.innerHTML; }
function info(s) {    // regeleinden (CR, zoals in BBS-banners) als echte regels tonen
  s = String(s == null ? '' : s).replace(/\r\n?/g, '\n').replace(/^\n+|\n+$/g, '');
  return '<span class="i' + (s.indexOf('\n') >= 0 ? ' blok' : '') + '">' + txt(s) + '</span>';
}
var WIS = '<button type="button" class="licht wis" data-wis="1" title="Scherm leegmaken">Wissen</button>';
var STAND = {wacht: 'wacht op zenden', verzonden: 'verzonden, wacht op bevestiging', bevestigd: 'bevestigd ✓✓',
  mislukt: 'niet bevestigd', gestopt: 'gestopt, niet bevestigd', geweigerd: 'geweigerd', cq: 'verzonden', ontvangen: ''};
function gesprekken() {
  var g = {CQ: 0};
  Object.keys(berichten).forEach(function (id) { var b = berichten[id], k = tegen(b); g[k] = Math.max(g[k] || 0, b.tijd); });
  if (actief !== 'MONITOR' && !(actief in g)) g[actief] = Date.now() / 1000;   // nieuw gesprek, nog zonder berichten
  return Object.keys(g).sort(function (a, b) { return a === 'CQ' ? -1 : b === 'CQ' ? 1 : g[b] - g[a]; }).map(function (k) { return [k, g[k]]; });
}
function teken() {
  var lijst = gesprekken(), h = '';
  lijst.concat([['MONITOR', 0]]).forEach(function (x) {
    var k = x[0], ongelezen = k !== actief && k !== 'MONITOR' && x[1] > (gelezen[k] || 0) && Object.keys(berichten).some(function (id) {
      var b = berichten[id]; return tegen(b) === k && b.richting === 'in' && b.tijd > (gelezen[k] || 0); });
    h += '<button type="button" data-g="' + txt(k) + '" class="' + (k === actief ? 'actief' : '') + '">' +
      (k === 'CQ' ? 'CQ (iedereen)' : k === 'MONITOR' ? 'Monitor' : txt(k)) + (ongelezen ? '<span class="nieuw"></span>' : '') + '</button>';
  });
  h += '<button type="button" data-g="+">+ Nieuw gesprek</button>';
  $('.gesprekken').innerHTML = h;
  var l = $('.lijst'), onder = l.scrollHeight - l.scrollTop - l.clientHeight < 40, b = '';
  if (actief === 'MONITOR') {
    $('.kop').innerHTML = 'Monitor <small>alles wat AX25Chat hoort</small>' + WIS;
    monitor.forEach(function (m) { b += '<div class="mon"><span class="t">' + tijd(m.tijd) + '</span> ' + txt(m.van) + '&gt;' + txt(m.aan) +
      (m.pad ? ',' + txt(m.pad) : '') + ':' + info(m.info) + '</div>'; });
    $('.typen').style.display = 'none';
  } else {
    $('.kop').innerHTML = (actief === 'CQ' ? 'CQ <small>aan iedereen, zonder bevestiging</small>' : txt(actief) + ' <small>bericht met bevestiging</small>') + WIS;
    $('.typen').style.display = '';
    Object.keys(berichten).map(function (id) { return berichten[id]; }).filter(function (x) { return tegen(x) === actief; })
      .sort(function (a, b) { return a.id - b.id; }).forEach(function (x) {
        var st = STAND.hasOwnProperty(x.status) ? STAND[x.status] : x.status;
        b += '<div class="bel ' + x.richting + (x.status === 'mislukt' || x.status === 'gestopt' ? ' mislukt' : '') + '">' +
          (x.richting === 'in' && actief === 'CQ' ? '<div class="van">' + txt(x.van) + '</div>' : '') + txt(x.tekst) +
          '<div class="meta">' + tijd(x.tijd) + (st ? ' · ' + st : '') +
          (x.status === 'mislukt' || x.status === 'gestopt' ? '<button type="button" class="licht" data-opnieuw="' + x.id + '">Opnieuw</button>' : '') +
          (x.richting === 'uit' && x.nummer != null && (x.status === 'wacht' || x.status === 'verzonden') ?
            '<button type="button" class="licht" data-stop="' + x.id + '">Stop</button>' : '') + '</div></div>';
      });
    var aan = $('.typen input[name=aan]');
    if (document.activeElement !== aan) { aan.value = actief; }
  }
  l.innerHTML = b || '<div class="leeg">' + (actief === 'MONITOR' ? 'Nog niets gehoord.' : 'Nog geen berichten.') + '</div>';
  if (onder) { l.scrollTop = l.scrollHeight; }
  if (actief !== 'MONITOR') { gelezen[actief] = Date.now() / 1000; try { localStorage.setItem('ax25chat-gelezen', JSON.stringify(gelezen)); } catch (e) {} }
}
function haal() {
  fetch('/api/berichten?sinds=' + laatst).then(function (r) { return r.json(); }).then(function (d) {
    laatst = d.nu; d.berichten.forEach(function (b) { berichten[b.id] = b; }); teken();
  }).catch(function () {});
}
fetch('/api/monitor').then(function (r) { return r.json(); }).then(function (d) { monitor = d; teken(); }).catch(function () {});
haal();
function live() {
  var bron = (window.axLive ? axLive() : new EventSource('/api/live'));
  bron.addEventListener('bericht', function (e) { var b = JSON.parse(e.data); berichten[b.id] = b; teken(); });
  bron.addEventListener('gewist', function (e) {
    var d = JSON.parse(e.data);
    if (d.gesprek === 'MONITOR') { monitor = []; } else { d.ids.forEach(function (id) { delete berichten[id]; }); }
    teken();
  });
  bron.addEventListener('monitor', function (e) { monitor.push(JSON.parse(e.data)); if (monitor.length > 300) monitor.shift(); if (actief === 'MONITOR') teken(); });
  bron.onerror = function () { $('.verbinding').textContent = 'geen verbinding met de Pi, opnieuw proberen...'; };
  bron.onopen = function () { $('.verbinding').textContent = ''; haal(); };
}
live();
document.addEventListener('click', function (e) {
  var g = e.target.closest('[data-g]'), o = e.target.closest('[data-opnieuw]'), s = e.target.closest('[data-stop]');
  if (g) {
    if (g.dataset.g === '+') { var c = prompt('Roepnaam van het tegenstation (bijv. PA1ABC-9):'); if (!c) return; actief = c.trim().toUpperCase(); }
    else { actief = g.dataset.g; }
    teken(); $('.lijst').scrollTop = 1e9;
  }
  if (s) { fetch('/api/stop', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({id: +s.dataset.stop})}); }
  if (e.target.closest('[data-wis]')) {
    var naam = actief === 'MONITOR' ? 'de Monitor' : actief === 'CQ' ? 'CQ (iedereen)' : 'het gesprek met ' + actief;
    if (confirm('Alle berichten in ' + naam + ' wissen? Je instellingen en frequenties blijven bewaard.')) {
      fetch('/api/wis', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({gesprek: actief})});
    }
  }
  if (o) { fetch('/api/opnieuw', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({id: +o.dataset.opnieuw})}); }
});
var tekst = $('.typen input[name=tekst]');
tekst.addEventListener('input', function () { var n = tekst.value.length; $('.teller').textContent = n > 67 ? Math.ceil(n / 67) + ' delen' : (67 - n); });
$('.typen').addEventListener('submit', function (e) {
  e.preventDefault();
  var aan = $('.typen input[name=aan]').value.trim().toUpperCase(), t = tekst.value.trim();
  if (!t) return;
  fetch('/api/berichten', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({aan: aan, tekst: t})})
    .then(function (r) { return r.json(); }).then(function (d) {
      if (d.fouten && d.fouten.length) { alert(d.fouten.join('\n')); return; }
      tekst.value = ''; $('.teller').textContent = ''; actief = aan;
      d.berichten.forEach(function (b) { berichten[b.id] = b; }); teken(); $('.lijst').scrollTop = 1e9;
    });
});
})();
"""


def html(melding_boven=""):
    return f"""{melding_boven}<style>{CSS}</style>
<div class="chat"><div class="gesprekken"></div>
<div class="venster"><div class="kop"></div><div class="lijst"></div>
<form class="typen" autocomplete="off"><input type="text" name="aan" value="CQ" aria-label="Aan" maxlength="9">
<input type="text" name="tekst" placeholder="Typ een bericht" aria-label="Bericht" maxlength="600" enterkeyhint="send">
<span class="teller"></span><button type="submit">Zenden</button></form></div></div>
<p class="uitleg verbinding" style="margin-top:8px"></p>
<script>{JS}</script>"""
