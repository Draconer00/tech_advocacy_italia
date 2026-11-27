"""
Export del Radar Diritti Digitali in un unico file HTML statico, da condividere
con i beta tester senza installare nulla.

Rende gli stessi blocchi della dashboard (app/viste.py) con lo stesso stile
(app/tema.py): stesse schede, stessi grafici Plotly interattivi (zoom, tooltip),
stesso grafo vis-network. I filtri sono fissati ai valori indicati in ogni scheda
e gli strumenti operatore (correzioni, inserimenti manuali) non sono inclusi.

Sola lettura: non modifica nessun dataset. Ogni export è un file nuovo con
data e ora nel nome, quindi gli export precedenti restano come archivio.

Uso:
    python app/export_html.py                 # file autonomo, funziona anche offline (~5 MB)
    python app/export_html.py --cdn           # plotly.js da CDN: file più leggero, serve internet
    python app/export_html.py --output percorso/file.html
"""
from __future__ import annotations

import argparse
import html
import os
import sys
from datetime import datetime

CARTELLA_APP = os.path.dirname(os.path.abspath(__file__))
for _p in (CARTELLA_APP, os.path.abspath(os.path.join(CARTELLA_APP, '..'))):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import plotly.offline  # noqa: E402

import dati  # noqa: E402
import grafici  # noqa: E402
import tema  # noqa: E402
import viste as V  # noqa: E402
from scrapers.scraper_ong import PROFILI_ONG  # noqa: E402
from utils.ong_profile import carica_profilo_keywords_ong  # noqa: E402

CARTELLA_EXPORT = os.path.join(dati.CARTELLA_ROOT, 'export')

# Layout della pagina: replica container, schede, pannelli ed expander di Streamlit.
CSS_PAGINA = """
html{background:#f5f6f4;color-scheme:light}
body{margin:0;background:#f5f6f4}
.wrap{max-width:1180px;margin:0 auto;padding:36px max(16px,env(safe-area-inset-left,0px)) 64px;display:flex;flex-direction:column;gap:1rem}
.stack{display:flex;flex-direction:column;gap:1rem;min-width:0}
.rd .panel{background:#fff;border:1px solid #dde1de;border-radius:6px;padding:16px;display:flex;flex-direction:column;gap:1rem;min-width:0}
.rd .cols{display:grid;gap:1.5rem;align-items:start}
.rd .cols>.stack{min-width:0}
.rd details.det{background:#fff;border:1px solid #dde1de;border-radius:4px}
.rd details.det>summary{cursor:pointer;padding:12px 16px;font-size:.9rem;font-weight:500;list-style:none;display:flex;gap:10px;align-items:center}
.rd details.det>summary::-webkit-details-marker{display:none}
.rd details.det>summary::before{content:"";width:7px;height:7px;border-right:1.5px solid #5b6670;border-bottom:1.5px solid #5b6670;transform:rotate(-45deg);transition:transform .15s}
.rd details.det[open]>summary::before{transform:rotate(45deg)}
.rd details.det>.stack{padding:0 16px 16px}
.rd nav.tabs{display:flex;flex-wrap:wrap;gap:4px 22px;border-bottom:1px solid #dde1de;margin-top:8px}
.rd nav.tabs button{background:none;border:0;border-bottom:2px solid transparent;margin-bottom:-1px;padding:8px 0;font:500 .88rem var(--f-body);color:var(--ink);cursor:pointer}
.rd nav.tabs button:hover{color:var(--accent)}
.rd nav.tabs button[aria-selected="true"]{color:var(--accent);border-bottom-color:var(--accent)}
.rd nav.tabs button:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.rd .scheda{padding-top:22px}
.rd .scheda[hidden]{display:none}
.rd .sel{display:flex;flex-direction:column;gap:4px;max-width:420px}
.rd .sel label{font-size:.82rem;color:var(--muted)}
.rd .sel select{font:400 .9rem var(--f-body);padding:8px 10px;border:1px solid #dde1de;border-radius:4px;background:#fff;color:var(--ink)}
.rd .grafo{width:100%;border:0;display:block}
.rd .plotly-graph-div{width:100%!important}
@media (max-width:820px){.rd .cols{grid-template-columns:minmax(0,1fr)!important}}
"""

JS_PAGINA = """
(function(){
  var bottoni=document.querySelectorAll('nav.tabs button');
  function mostra(id){
    bottoni.forEach(function(b){var on=b.dataset.tab===id;b.setAttribute('aria-selected',on);b.tabIndex=on?0:-1;});
    document.querySelectorAll('.scheda').forEach(function(s){
      var on=s.id==='tab-'+id; s.hidden=!on;
      if(on){s.querySelectorAll('iframe[data-srcdoc]').forEach(function(f){if(!f.srcdoc){f.srcdoc=f.dataset.srcdoc;}});}
    });
    window.dispatchEvent(new Event('resize'));
    if(history.replaceState){history.replaceState(null,'','#'+id);}
  }
  bottoni.forEach(function(b,i){
    b.addEventListener('click',function(){mostra(b.dataset.tab);});
    b.addEventListener('keydown',function(e){
      var d=e.key==='ArrowRight'?1:e.key==='ArrowLeft'?-1:0; if(!d)return;
      var n=bottoni[(i+d+bottoni.length)%bottoni.length]; n.focus(); mostra(n.dataset.tab);
    });
  });
  document.querySelectorAll('select[data-sel]').forEach(function(s){
    s.addEventListener('change',function(){
      document.querySelectorAll('[data-grp="'+s.dataset.sel+'"]').forEach(function(g){g.hidden=g.dataset.opt!==s.value;});
    });
  });
  window.addEventListener('hashchange',function(){
    var h=(location.hash||'').slice(1); if(document.getElementById('tab-'+h)){mostra(h);window.scrollTo(0,0);}
  });
  var iniziale=(location.hash||'').slice(1);
  mostra(document.getElementById('tab-'+iniziale)?iniziale:bottoni[0].dataset.tab);
})();
"""


class Renderer:
    """Blocchi di app/viste.py -> HTML (controparte statica di dashboard.rendi)."""

    def __init__(self):
        self.n_selettori = 0

    def __call__(self, blocchi: list) -> str:
        return ''.join(self.blocco(b) for b in blocchi)

    def stack(self, blocchi: list, cls: str = 'stack') -> str:
        return f'<div class="{cls}">{self(blocchi)}</div>'

    def blocco(self, b) -> str:
        if isinstance(b, V.Html):
            return b.html
        if isinstance(b, V.Grafico):
            altezza = b.fig.layout.height or grafici.ALTEZZA
            return b.fig.to_html(full_html=False, include_plotlyjs=False, default_width='100%',
                                 default_height=f'{altezza}px',
                                 config={'displaylogo': False, 'responsive': True})
        if isinstance(b, V.Pannello):
            testa = tema.panel_head(b.titolo, b.sottotitolo) if b.titolo else ''
            nota = tema.nota(b.nota) if b.nota else ''
            return f'<div class="rd"><section class="panel">{testa}{self(b.blocchi)}{nota}</section></div>'
        if isinstance(b, V.Colonne):
            pesi = b.pesi or [1] * len(b.colonne)
            griglia = ' '.join(f'minmax(0,{p}fr)' for p in pesi)
            return (f'<div class="rd"><div class="cols" style="grid-template-columns:{griglia}">'
                    + ''.join(self.stack(c) for c in b.colonne) + '</div></div>')
        if isinstance(b, V.Dettagli):
            aperto = ' open' if b.aperto else ''
            return (f'<div class="rd"><details class="det"{aperto}><summary>{tema.esc(b.titolo)}</summary>'
                    f'{self.stack(b.blocchi)}</details></div>')
        if isinstance(b, V.Tabella):
            formati = {b.etichette.get(k, k): v for k, v in b.formati.items()}
            return tema.rd(tema.tabella_dati(b.df.rename(columns=b.etichette), formati))
        if isinstance(b, V.Grafo):
            return (f'<iframe class="grafo" title="Grafo delle relazioni" style="height:{b.altezza}px" '
                    f'data-srcdoc="{html.escape(b.html, quote=True)}"></iframe>')
        if isinstance(b, V.Selettore):
            self.n_selettori += 1
            sid = f'sel{self.n_selettori}'
            opzioni = list(b.opzioni)
            sel = ''.join(f'<option value="{i}">{tema.esc(o)}</option>' for i, o in enumerate(opzioni))
            gruppi = ''.join(
                f'<div class="stack" data-grp="{sid}" data-opt="{i}"{"" if i == 0 else " hidden"}>'
                f'{self(b.opzioni[o])}</div>' for i, o in enumerate(opzioni))
            return (f'<div class="rd"><div class="sel"><label for="{sid}">{tema.esc(b.etichetta)}</label>'
                    f'<select id="{sid}" data-sel="{sid}">{sel}</select></div></div>{gruppi}')
        raise TypeError(f'Blocco non gestito: {type(b).__name__}')


def costruisci_schede(stamp: str) -> dict[str, list]:
    """Stesse viste della dashboard, con i valori predefiniti dei filtri."""
    df_master = dati.prepara_master(dati.carica_dati_unificati())
    df_ong = dati.carica_dati_ong()
    schede: dict[str, list] = {}

    # 1. Panoramica
    nome_int, giorni = dati.INTERVALLI_HOME[dati.INTERVALLO_EXPORT]
    df_home = dati.filtra_master(df_master, giorni)
    schede['home'] = [V.testata_home(), V.filtri_attivi([
        ('Intervallo', nome_int), ('Categorie, fonti e aree', 'tutte'), ('Allarme minimo', '1'),
    ])] + V.vista_home(df_home, dati.carica_dati_raw_per_fonte())

    # 2. Campagne ONG
    ong_con_doc = set(df_ong['nome_organizzazione'].unique()) if not df_ong.empty else set()
    ong_tutte = sorted(ong_con_doc)
    schede['ong'] = ([V.testata_ong()] + V.avviso_ong_mancanti(sorted(set(PROFILI_ONG) - ong_con_doc))
                     + ([V.filtri_attivi([('Organizzazioni', 'tutte')])] if ong_tutte else [])
                     + V.vista_ong(dati.ong_come_unificato(df_ong), len(ong_tutte)))

    # 3. Geografia
    ordine_tipi = df_master['tipo'].value_counts().index.tolist()
    schede['geografia'] = [V.testata_geo(), V.filtri_attivi([('Tipo di contenuto', 'tutti'),
                                                             ('Area geografica', 'tutte')])] \
        + V.vista_geo(df_master, ordine_tipi)

    # 4. Network
    if df_ong.empty:
        schede['network'] = [V.testata_network(), V.Html(tema.rd(tema.callout('Nessun dato ONG disponibile.', 'warn')))]
    else:
        fonti_generaliste = {
            "GNews": dati.carica_dati_gnews(), "Tech News Italiane": dati.carica_dati_tech_news(),
            "RSS Regolatori Europei": dati.carica_dati_rss_eu(), "Parlamento Europeo": dati.carica_dati_eu_parl(),
            "AGCOM": dati.carica_dati_agcom(),
        }
        G = dati.costruisci_grafo(df_ong, fonti_generaliste, carica_profilo_keywords_ong(),
                                  dati.correzioni_ong_manuali())
        schede['network'] = [V.testata_network()] + V.vista_network(grafici.html_grafo(G), dati.statistiche_grafo(G))

    # 5. Posizionamento (salva=False: l'export non scrive file di stato)
    if df_ong.empty:
        schede['posizionamento'] = [V.testata_posizionamento()]
    else:
        notizie, centroidi = dati.prepara_posizionamento(df_ong, salva=False)
        schede['posizionamento'] = [V.testata_posizionamento()] + V.vista_posizionamento(notizie, centroidi)

    # 6. Temi nel tempo
    df_temp = dati.carica_dati_per_analisi_temporale()
    nome_per, giorni_per = dati.INTERVALLI_TEMPO[0]
    livello = dati.LIVELLI_TEMI[0]
    blocchi = [V.testata_tempo()]
    if not df_temp.empty:
        df_per = dati.filtra_periodo(df_temp, giorni_per)
        registro = dati.carica_registro()
        attivi = registro[registro['stato'] == 'attivo']
        blocchi += [V.filtri_attivi([('Periodo di analisi', nome_per)])]
        blocchi += V.vista_tempo_a(df_per, df_temp['fonte'].value_counts().index.tolist(),
                                   dati.sanzioni_mensili(df_per))
        blocchi += [V.filtri_attivi([('Livello dei temi', livello)])]
        blocchi += V.vista_tempo_b(dati.conteggio_temi_mensile(df_per, dati.temi_ammessi(livello, registro)),
                                   livello, attivi[attivi['padre'] != ''])
    schede['tempo'] = blocchi

    # 7. Topic emergenti
    df_topic, df_trend = dati.carica_topic_emergenti()
    blocchi = [V.testata_topic()] + V.vista_topic(df_topic, df_trend)
    if not df_topic.empty and not df_trend.empty:
        scelti = df_topic.nlargest(5, 'dimensione')['topic_id'].astype(int).tolist()
        blocchi += [V.filtri_attivi([('Topic a confronto', 'i 5 più grandi')])]
        blocchi += V.vista_topic_trend(df_topic, df_trend, scelti)
    schede['topic'] = blocchi + V.vista_registro(dati.carica_registro())

    # 8. Metodo
    schede['metodo'] = V.vista_metodo(df_master, stamp, statico=True)
    return schede, df_master


def genera_pagina(cdn: bool = False) -> str:
    ora = datetime.now()
    agg = dati.data_aggiornamento()
    stamp = (f"Fotografia del {ora:%d/%m/%Y %H:%M}"
             + (f" · dati al {agg:%d/%m/%Y %H:%M}" if agg else ''))
    schede, df_master = costruisci_schede(stamp)
    r = Renderer()

    nav = ''.join(f'<button type="button" role="tab" data-tab="{sid}" aria-controls="tab-{sid}" '
                  f'id="btn-{sid}">{tema.esc(nome)}</button>' for sid, nome in tema.SCHEDE)
    sezioni = ''.join(f'<section class="scheda stack" id="tab-{sid}" role="tabpanel" aria-labelledby="btn-{sid}">'
                      f'{r(schede[sid])}</section>' for sid, _ in tema.SCHEDE)
    if cdn:
        plotly_js = f'<script src="https://cdn.plot.ly/plotly-{plotly.offline.get_plotlyjs_version()}.min.js" charset="utf-8"></script>'
    else:
        plotly_js = f'<script type="text/javascript">{plotly.offline.get_plotlyjs()}</script>'

    return f"""<!doctype html>
<html lang="it">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{tema.esc(tema.TITOLO)}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="{tema.GOOGLE_FONTS}">
<style>{tema.CSS_COMPONENTI}{CSS_PAGINA}</style>
{plotly_js}
</head>
<body>
<div class="wrap rd">
{V.masthead(df_master, stamp).html}
<nav class="tabs" role="tablist" aria-label="Schede">{nav}</nav>
{sezioni}
</div>
<script>{JS_PAGINA}</script>
</body>
</html>
"""


def _percorso_libero(percorso: str) -> str:
    """Non sovrascrive mai un export esistente: aggiunge un suffisso numerico."""
    base, ext = os.path.splitext(percorso)
    n, candidato = 1, percorso
    while os.path.exists(candidato):
        n += 1
        candidato = f'{base}_{n}{ext}'
    return candidato


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    p.add_argument('--output', help='percorso del file HTML (default: export/radar_diritti_digitali_<data>.html)')
    p.add_argument('--cdn', action='store_true', help='carica plotly.js da CDN invece di includerlo')
    args = p.parse_args()

    percorso = args.output or os.path.join(
        CARTELLA_EXPORT, f'radar_diritti_digitali_{datetime.now():%Y%m%d_%H%M}.html')
    percorso = _percorso_libero(os.path.abspath(percorso))
    os.makedirs(os.path.dirname(percorso), exist_ok=True)
    pagina = genera_pagina(cdn=args.cdn)
    with open(percorso, 'w', encoding='utf-8') as f:
        f.write(pagina)
    print(f'Export scritto: {percorso} ({os.path.getsize(percorso) / 1_048_576:.1f} MB)')


if __name__ == '__main__':
    main()
