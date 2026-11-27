"""
Sistema visivo condiviso del Radar Diritti Digitali.

Un'unica fonte per token di colore, font, CSS dei componenti, template Plotly e
generatori HTML. La usano sia la dashboard Streamlit (app/dashboard.py) sia
l'export statico per i beta tester (app/export_html.py): così le due viste
restano allineate per costruzione e una modifica estetica si fa in un posto solo.

Nessuna dipendenza da Streamlit: qui ci sono solo stringhe HTML/CSS e Plotly.
"""
from __future__ import annotations

import html
import math

import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio

# --- TOKEN -------------------------------------------------------------------
COLORI = {
    'bg': '#f5f6f4', 'surface': '#ffffff', 'ink': '#17212b', 'muted': '#5b6670',
    'line': '#dde1de', 'accent': '#1d5a7a', 'accent_soft': '#dce9f0',
    'ong': '#5a4a8a', 'geo': '#2f6f5b', 'alarm': '#b3261e', 'alarm_soft': '#f8e1de',
    'pos': '#2f6f3e', 'pos_soft': '#e0efe3', 'neu_soft': '#eceeec',
}

# Palette categorica (identità delle serie), validata con il validator del
# metodo dataviz su superficie bianca: separazione CVD tra adiacenti >= 8.9,
# visione normale >= 21.6. Lo slot 4 (giallo) è sotto 3:1 di contrasto, quindi
# i grafici hanno sempre legenda + tooltip. Ordine fisso: mai ciclare oltre 8,
# le serie in eccesso si piegano in "Altro" (vedi piega_categorie).
CATEGORICI = ['#2f78b5', '#e07034', '#1f9e78', '#d99a0b',
              '#d0679a', '#3a8a2e', '#6a58c9', '#cf4a46']
COLORE_ALTRO = '#9aa3ab'

FONT_DISPLAY = '"Source Serif 4", Georgia, "Times New Roman", serif'
FONT_BODY = '"IBM Plex Sans", system-ui, -apple-system, "Segoe UI", sans-serif'
FONT_MONO = '"IBM Plex Mono", ui-monospace, Consolas, monospace'
GOOGLE_FONTS = ('https://fonts.googleapis.com/css2?family=Source+Serif+4:opsz,wght@8..60,500;'
                '8..60,650&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:'
                'wght@400;500&display=swap')

TITOLO = 'Radar Diritti Digitali'
LEDE = ('Privacy, intelligenza artificiale e diritti digitali in Italia e in Europa: '
        'cosa pubblicano istituzioni, ONG e stampa, raccolto e classificato in automatico.')

# Etichette delle schede: identiche in Streamlit e nell'export.
SCHEDE = [
    ('home', 'Panoramica'),
    ('ong', 'Campagne ONG'),
    ('geografia', 'Geografia'),
    ('network', 'Network temi'),
    ('posizionamento', 'Posizionamento'),
    ('tempo', 'Temi nel tempo'),
    ('topic', 'Topic emergenti'),
    ('metodo', 'Metodo'),
]

# --- CSS ---------------------------------------------------------------------
# Tutti i componenti sono sotto .rd così non collidono con le classi di Streamlit.
CSS_COMPONENTI = """
.rd{--bg:#f5f6f4;--surface:#ffffff;--ink:#17212b;--muted:#5b6670;--line:#dde1de;
  --accent:#1d5a7a;--accent-soft:#dce9f0;--ong:#5a4a8a;--geo:#2f6f5b;
  --alarm:#b3261e;--alarm-soft:#f8e1de;--pos:#2f6f3e;--pos-soft:#e0efe3;--neu-soft:#eceeec;
  --f-display:"Source Serif 4",Georgia,"Times New Roman",serif;
  --f-body:"IBM Plex Sans",system-ui,-apple-system,"Segoe UI",sans-serif;
  --f-mono:"IBM Plex Mono",ui-monospace,Consolas,monospace;
  color:var(--ink);font-family:var(--f-body);font-size:15px;line-height:1.5}
.rd *{box-sizing:border-box}
.rd a{color:var(--accent)}
.rd h1,.rd h2,.rd h3,.rd h4{text-wrap:balance;margin:0;padding:0;color:var(--ink)}
.rd h1{font-family:var(--f-display);font-weight:650;font-size:clamp(2rem,5vw,3.1rem);line-height:1.05;letter-spacing:-.01em}
.rd h2{font-family:var(--f-display);font-weight:650;font-size:1.65rem;line-height:1.15}
.rd h3{font-family:var(--f-body);font-size:.95rem;font-weight:600;line-height:1.35}
.rd p{margin:0}
.rd .eyebrow{font-family:var(--f-mono);font-size:.72rem;letter-spacing:.08em;text-transform:uppercase;color:var(--muted)}
.rd .masthead{display:flex;flex-direction:column;gap:14px;border-bottom:2px solid var(--ink);padding-bottom:18px}
.rd .mh-row{display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap}
.rd .stamp{font-family:var(--f-mono);font-size:.72rem;color:var(--muted)}
.rd .lede{max-width:65ch;color:var(--muted);font-size:1.05rem}
.rd .kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:1px;background:var(--line);border:1px solid var(--line)}
.rd .kpi{background:var(--surface);padding:14px 16px;display:flex;flex-direction:column;gap:2px}
.rd .kpi-n{font-family:var(--f-display);font-size:2rem;font-weight:650;font-variant-numeric:tabular-nums;line-height:1.1}
.rd .kpi-small{font-size:1.05rem;padding-top:.5rem;font-family:var(--f-mono);font-weight:500}
.rd .kpi-l{font-size:.8rem;color:var(--muted)}
.rd .kpi-alto .kpi-n{color:var(--alarm)}
.rd .sec-head{display:flex;flex-direction:column;gap:6px;padding-top:6px}
.rd .sec-head p{max-width:72ch;color:var(--muted)}
.rd .sub{font-family:var(--f-body);font-size:.95rem;font-weight:600;margin-top:6px}
.rd .panel-h{display:flex;flex-direction:column;gap:2px}
.rd .panel-h p{font-size:.8rem;color:var(--muted)}
.rd .nota{font-size:.8rem;color:var(--muted)}
.rd .callout{border-left:3px solid var(--accent);background:var(--surface);padding:10px 14px;border-radius:0 4px 4px 0;font-size:.88rem;color:var(--ink)}
.rd .callout-warn{border-left-color:var(--alarm);background:var(--alarm-soft)}
.rd .callout code,.rd .nota code{font-family:var(--f-mono);font-size:.85em}
.rd .vuoto{color:var(--muted);font-style:italic;font-size:.88rem}
.rd .hbars{display:flex;flex-direction:column;gap:7px}
.rd .hbar{display:grid;grid-template-columns:minmax(0,11rem) minmax(0,1fr) 2.8rem;gap:10px;align-items:center;font-size:.84rem}
.rd .hbar-lbl{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.rd .hbar-track{height:10px;background:var(--neu-soft);border-radius:2px;overflow:hidden}
.rd .hbar-fill{display:block;height:100%;border-radius:2px}
.rd .b-accent{background:var(--accent)} .rd .b-ong{background:var(--ong)} .rd .b-geo{background:var(--geo)}
.rd .hbar-val{text-align:right;font-family:var(--f-mono);font-variant-numeric:tabular-nums}
.rd .docs{display:grid;grid-template-columns:repeat(auto-fill,minmax(min(100%,320px),1fr));gap:12px}
.rd .docs-1{grid-template-columns:minmax(0,1fr)}
.rd .doc{background:var(--surface);border:1px solid var(--line);border-left:4px solid var(--line);border-radius:4px;padding:12px 14px;display:flex;flex-direction:column;gap:8px;min-width:0}
.rd .doc-alto{border-left-color:var(--alarm)}
.rd .doc-top{display:flex;justify-content:space-between;gap:8px;font-family:var(--f-mono);font-size:.72rem;color:var(--muted)}
.rd .doc-src{text-transform:uppercase;letter-spacing:.04em;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.rd .doc h4{font-family:var(--f-display);font-weight:500;font-size:1.02rem;line-height:1.3;overflow-wrap:anywhere}
.rd .doc h4 a{color:var(--ink);text-decoration:none} .rd .doc h4 a:hover{text-decoration:underline}
.rd .doc-txt{font-size:.84rem;color:var(--muted);overflow-wrap:anywhere}
.rd .doc-tags,.rd .ents{display:flex;flex-wrap:wrap;gap:5px}
.rd .chip{font-size:.72rem;padding:2px 8px;border-radius:3px;background:var(--accent-soft);color:var(--accent);font-weight:500}
.rd .chip-vuoto{background:var(--neu-soft);color:var(--muted)}
.rd .pill{font-size:.72rem;padding:2px 8px;border-radius:999px;border:1px solid var(--line);color:var(--muted);white-space:nowrap}
.rd .p-neg{background:var(--alarm-soft);color:var(--alarm);border-color:transparent}
.rd .p-pos{background:var(--pos-soft);color:var(--pos);border-color:transparent}
.rd .p-neu{background:var(--neu-soft)}
.rd .p-alto{background:var(--alarm);color:var(--surface);border-color:var(--alarm);font-weight:600}
.rd .p-coperto{background:var(--accent-soft);color:var(--accent);border-color:transparent}
.rd .p-candidato_sottotema{background:var(--pos-soft);color:var(--pos);border-color:transparent}
.rd .p-fuori_lessico{background:var(--neu-soft)}
.rd .p-manuale{background:var(--accent-soft);color:var(--accent);border-color:transparent}
.rd .ent{font-size:.72rem;color:var(--muted);font-family:var(--f-mono)}
.rd .ent+.ent::before{content:"· ";color:var(--line)}
.rd .doc-foot{font-size:.74rem;color:var(--muted)}
.rd .tbl-wrap{overflow:auto;max-width:100%}
.rd .tbl-scroll{max-height:460px}
.rd table{border-collapse:collapse;width:100%;font-size:.82rem}
.rd th{font-weight:600;text-align:left}
.rd .heat th,.rd .heat td{padding:6px 8px;border-bottom:1px solid var(--line);white-space:nowrap}
.rd .heat thead th{font-size:.74rem;color:var(--muted);font-weight:500}
.rd .hm{text-align:center;font-family:var(--f-mono);font-variant-numeric:tabular-nums;color:var(--muted)}
.rd .hm-on{color:var(--ink)}
.rd .dati th,.rd .dati td{padding:6px 8px;border-bottom:1px solid var(--line);vertical-align:top;text-align:left}
.rd .dati thead th{position:sticky;top:0;background:var(--bg);font-size:.74rem;color:var(--muted);font-weight:500;z-index:1}
.rd .dati td.num{font-family:var(--f-mono);text-align:right;font-variant-numeric:tabular-nums}
.rd .trends{display:flex;flex-direction:column}
.rd .trend{display:grid;grid-template-columns:minmax(0,1fr) 120px auto;gap:14px;align-items:center;padding:8px 0;border-bottom:1px solid var(--line)}
.rd .trend:last-child{border-bottom:0}
.rd .trend-n{font-weight:500}
.rd .trend-v{white-space:nowrap;text-align:right;font-family:var(--f-mono);font-variant-numeric:tabular-nums;font-size:.86rem}
.rd .trend-v small{color:var(--muted);font-size:.75rem}
.rd .delta-su{color:var(--pos);font-weight:600} .rd .delta-giu{color:var(--alarm);font-weight:600}
.rd .spark{width:120px;height:30px;display:block}
.rd .topics .spark{width:110px;height:28px}
.rd .spark-area{fill:var(--accent-soft)} .rd .spark-line{fill:none;stroke:var(--accent);stroke-width:1.6}
.rd .spark-dot{fill:var(--accent)}
.rd .topics th,.rd .topics td{padding:9px 8px;border-bottom:1px solid var(--line);vertical-align:top}
.rd .topics thead th{font-size:.74rem;color:var(--muted);font-weight:500}
.rd .topics td.num{font-family:var(--f-mono);text-align:right}
.rd .es{color:var(--muted);font-size:.76rem;margin-top:2px;max-width:52ch}
.rd .legenda{margin-top:12px;display:flex;flex-wrap:wrap;gap:6px 18px;font-size:.82rem;color:var(--muted)}
.rd .legenda span{display:inline-flex;align-items:center;gap:6px}
.rd .legenda i{display:inline-block;width:10px;height:10px;border-radius:50%}
.rd .assi{border-collapse:collapse;font-size:.84rem;width:auto;margin-top:12px}
.rd .assi th,.rd .assi td{padding:6px 12px;border-bottom:1px solid var(--line);text-align:left}
.rd .assi thead th{font-size:.74rem;color:var(--muted);font-weight:500}
.rd .metodo ul{margin:0;padding-left:1.2rem;max-width:78ch;display:flex;flex-direction:column;gap:6px;color:var(--muted)}
.rd .metodo strong{color:var(--ink)}
.rd code{font-family:var(--f-mono);font-size:.85em}
@media (max-width:820px){
  .rd .trend{grid-template-columns:minmax(0,1fr) 110px}
  .rd .trend-v{grid-column:1/-1}
  .rd .hbar{grid-template-columns:minmax(0,8rem) minmax(0,1fr) 2.6rem}
}
"""

# Override degli elementi Streamlit per farli coincidere con i pannelli,
# le schede e i <details> dell'export HTML.
CSS_STREAMLIT = """
.block-container{max-width:1180px;padding-top:2.2rem;padding-bottom:4rem}
header[data-testid="stHeader"]{background:transparent}
[data-testid="stMarkdownContainer"] .rd p{margin:0}
/* schede = barra di navigazione dell'export */
.stTabs [data-baseweb="tab-list"]{gap:4px 22px;flex-wrap:wrap;border-bottom:1px solid #dde1de}
.stTabs [data-baseweb="tab"]{height:auto;padding:8px 0;background:transparent}
.stTabs [data-baseweb="tab"] p{font-family:"IBM Plex Sans",system-ui,sans-serif;font-size:.88rem;font-weight:500;color:#17212b}
.stTabs [aria-selected="true"] p{color:#1d5a7a}
.stTabs [data-baseweb="tab-highlight"]{background:#1d5a7a;height:2px}
.stTabs [data-baseweb="tab-border"]{display:none}
.stTabs [data-baseweb="tab-panel"]{padding-top:22px}
/* pannelli = st.container(border=True, key="pannello_N") */
[class*="st-key-pannello_"]{background:#ffffff;border-color:#dde1de;border-radius:6px}
/* niente icone-ancora sui titoli dei componenti */
.rd [data-testid="stHeaderActionElements"]{display:none}
/* filtri: tag tenui come le chip, multiselect a altezza contenuta */
span[data-baseweb="tag"]{background:#dce9f0!important;color:#1d5a7a!important}
span[data-baseweb="tag"] svg{fill:#1d5a7a}
.stMultiSelect [data-baseweb="select"]>div{max-height:6.5rem;overflow-y:auto}
/* expander = <details> */
[data-testid="stExpander"] details{background:#ffffff;border:1px solid #dde1de;border-radius:4px}
[data-testid="stExpander"] summary p{font-size:.9rem;font-weight:500}
/* strumenti operatore: bordo tratteggiato, non fanno parte della vista condivisa */
[class*="st-key-operatore"] [data-testid="stExpander"] details{border:1px dashed #1d5a7a;background:rgba(220,233,240,.35)}
[class*="st-key-operatore"] [data-testid="stExpander"] summary p{font-family:"IBM Plex Mono",monospace;font-size:.78rem;letter-spacing:.06em;text-transform:uppercase;color:#1d5a7a}
[data-testid="stWidgetLabel"] p{font-size:.82rem;color:#5b6670}
"""


def css_streamlit() -> str:
    """Blocco <style> da iniettare una volta in cima alla dashboard."""
    return f'<style>{CSS_COMPONENTI}{CSS_STREAMLIT}</style>'


# --- PLOTLY ------------------------------------------------------------------
def _registra_template() -> None:
    t = go.layout.Template()
    t.layout = go.Layout(
        font=dict(family=FONT_BODY, size=12, color=COLORI['ink']),
        paper_bgcolor=COLORI['surface'], plot_bgcolor=COLORI['surface'],
        colorway=CATEGORICI,
        margin=dict(l=8, r=8, t=12, b=8),
        hoverlabel=dict(bgcolor=COLORI['surface'], bordercolor=COLORI['line'],
                        font=dict(family=FONT_BODY, size=12, color=COLORI['ink'])),
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='left', x=0,
                    font=dict(size=11, color=COLORI['muted']), title_text=''),
        xaxis=dict(showgrid=False, linecolor=COLORI['line'], ticks='outside',
                   tickcolor=COLORI['line'], ticklen=4,
                   tickfont=dict(family=FONT_MONO, size=10.5, color=COLORI['muted']),
                   title_font=dict(size=11, color=COLORI['muted']), automargin=True),
        yaxis=dict(gridcolor=COLORI['line'], zeroline=False, linecolor=COLORI['line'],
                   tickfont=dict(family=FONT_MONO, size=10.5, color=COLORI['muted']),
                   title_font=dict(size=11, color=COLORI['muted']), automargin=True),
        bargap=0.25,
    )
    # 2px di superficie tra segmenti/barre adiacenti
    t.data.bar = [go.Bar(marker=dict(line=dict(color=COLORI['surface'], width=1.5)))]
    t.data.scatter = [go.Scatter(line=dict(width=2), marker=dict(size=7))]
    pio.templates['radar'] = t


_registra_template()


def stile(fig: go.Figure, altezza: int = 340) -> go.Figure:
    """Applica il template del radar e un'altezza fissa (uguale nei due target)."""
    fig.update_layout(template='radar', height=altezza, title=None)
    return fig


def colori_per(entita: list[str]) -> dict[str, str]:
    """Colore stabile per entità, nell'ordine dato (mai per rank del filtro)."""
    mappa = {e: CATEGORICI[i] for i, e in enumerate(entita[:len(CATEGORICI)])}
    mappa['Altro'] = COLORE_ALTRO
    return mappa


def piega_categorie(serie: pd.Series, ordine: list[str], massimo: int = 8) -> pd.Series:
    """Tiene le prime `massimo - 1` categorie di `ordine` e piega il resto in 'Altro'
    (se servono più di `massimo` slot): nessun nono colore generato."""
    presenti = [c for c in ordine if c in set(serie.dropna())]
    if len(presenti) <= massimo:
        return serie
    tenute = set(ordine[:massimo - 1])
    return serie.where(serie.isin(tenute), 'Altro')


# --- GENERATORI HTML -----------------------------------------------------------
def esc(valore) -> str:
    if valore is None or (isinstance(valore, float) and math.isnan(valore)):
        return ''
    return html.escape(str(valore), quote=True)


def rd(contenuto: str) -> str:
    """Avvolge un frammento nel contenitore dei componenti."""
    return f'<div class="rd">{contenuto}</div>'


def fmt_int(n) -> str:
    return f'{int(n):,}'.replace(',', '.')


def kpi_row(voci: list[tuple]) -> str:
    """voci: (valore, etichetta) o (valore, etichetta, 'alto'|'small')."""
    celle = []
    for voce in voci:
        valore, etichetta = voce[0], voce[1]
        variante = voce[2] if len(voce) > 2 else ''
        cls_kpi = ' kpi-alto' if variante == 'alto' else ''
        cls_n = ' kpi-small' if variante == 'small' else ''
        celle.append(f'<div class="kpi{cls_kpi}"><span class="kpi-n{cls_n}">{esc(valore)}</span>'
                     f'<span class="kpi-l">{esc(etichetta)}</span></div>')
    return f'<div class="kpis">{"".join(celle)}</div>'


def masthead(stamp: str, kpis: list[tuple], eyebrow: str = 'Tech Advocacy Italia') -> str:
    return (f'<header class="masthead"><div class="mh-row"><span class="eyebrow">{esc(eyebrow)}</span>'
            f'<span class="stamp">{esc(stamp)}</span></div><h1>{esc(TITOLO)}</h1>'
            f'<p class="lede">{esc(LEDE)}</p>{kpi_row(kpis)}</header>')


def sec_head(eyebrow: str, titolo: str, testo: str = '') -> str:
    p = f'<p>{testo}</p>' if testo else ''
    return f'<header class="sec-head"><span class="eyebrow">{esc(eyebrow)}</span><h2>{esc(titolo)}</h2>{p}</header>'


def panel_head(titolo: str, sottotitolo: str = '') -> str:
    p = f'<p>{sottotitolo}</p>' if sottotitolo else ''
    return f'<div class="panel-h"><h3>{esc(titolo)}</h3>{p}</div>'


def sottotitolo(testo: str) -> str:
    return f'<h3 class="sub">{esc(testo)}</h3>'


def nota(testo_html: str) -> str:
    return f'<p class="nota">{testo_html}</p>'


def callout(testo_html: str, tipo: str = 'info') -> str:
    cls = ' callout-warn' if tipo == 'warn' else ''
    return f'<div class="callout{cls}">{testo_html}</div>'


def vuoto(testo: str) -> str:
    return f'<p class="vuoto">{esc(testo)}</p>'


def legenda(voci: list[tuple[str, str]]) -> str:
    return '<div class="legenda">' + ''.join(
        f'<span><i style="background:{c}"></i>{esc(t)}</span>' for c, t in voci) + '</div>'


def hbars(serie: pd.Series, colore: str = 'accent', massimo: int | None = None) -> str:
    """Barre orizzontali HTML da una Series etichetta -> conteggio (già ordinata)."""
    if serie.empty:
        return vuoto('Nessun documento.')
    if massimo:
        serie = serie.head(massimo)
    top = max(float(serie.max()), 1.0)
    righe = []
    for etichetta, valore in serie.items():
        larghezza = 100.0 * float(valore) / top
        righe.append(f'<div class="hbar" title="{esc(etichetta)}: {fmt_int(valore)}">'
                     f'<span class="hbar-lbl">{esc(etichetta)}</span>'
                     f'<span class="hbar-track"><span class="hbar-fill b-{colore}" style="width:{larghezza:.1f}%"></span></span>'
                     f'<span class="hbar-val">{fmt_int(valore)}</span></div>')
    return f'<div class="hbars">{"".join(righe)}</div>'


def heat_table(pivot: pd.DataFrame, colore: str = COLORI['accent']) -> str:
    """Tabella a intensità (righe x colonne di conteggi)."""
    if pivot.empty:
        return vuoto('Nessun dato.')
    massimo = max(float(pivot.values.max()), 1.0)
    testa = ''.join(f'<th>{esc(c)}</th>' for c in pivot.columns)
    righe = []
    for indice, riga in pivot.iterrows():
        celle = []
        for valore in riga.values:
            v = int(valore)
            if v <= 0:
                celle.append('<td class="hm">·</td>')
            else:
                alfa = 0.08 + 0.85 * (v / massimo)
                celle.append(f'<td class="hm hm-on" style="background:color-mix(in srgb,{colore} '
                             f'{alfa * 100:.0f}%,transparent)">{fmt_int(v)}</td>')
        righe.append(f'<tr><th scope="row">{esc(indice)}</th>{"".join(celle)}</tr>')
    return (f'<div class="tbl-wrap"><table class="heat"><thead><tr><th></th>{testa}</tr></thead>'
            f'<tbody>{"".join(righe)}</tbody></table></div>')


def sparkline(valori: list[float], larghezza: int = 120, altezza: int = 30) -> str:
    if not valori:
        return ''
    top = max(max(valori), 1)
    n = len(valori)
    passo = (larghezza - 6) / max(n - 1, 1)
    punti = [(3 + i * passo, altezza - 4 - (v / top) * (altezza - 8)) for i, v in enumerate(valori)]
    linea = ' '.join(f'{x:.1f},{y:.1f}' for x, y in punti)
    area = f'3,{altezza - 4} {linea} {punti[-1][0]:.1f},{altezza - 4}'
    ux, uy = punti[-1]
    return (f'<svg class="spark" viewBox="0 0 {larghezza} {altezza}" aria-hidden="true">'
            f'<polygon points="{area}" class="spark-area"/><polyline points="{linea}" class="spark-line"/>'
            f'<circle cx="{ux:.1f}" cy="{uy:.1f}" r="2.6" class="spark-dot"/></svg>')


SENTIMENT = {
    'neg': ('Libertà ristrette', 'p-neg'),
    'pos': ('Diritti tutelati', 'p-pos'),
    'neu': ('Neutrale', 'p-neu'),
}


def classe_sentiment(valore) -> str:
    v = str(valore or '').upper()
    if v.startswith('NEG'):
        return 'neg'
    if v.startswith('POS'):
        return 'pos'
    return 'neu'


def _data_it(valore) -> str:
    try:
        d = pd.to_datetime(valore, errors='coerce')
    except Exception:
        d = pd.NaT
    return '' if pd.isna(d) else d.strftime('%d/%m/%Y')


def doc_card(r: dict, estratto: int = 0) -> str:
    """Scheda di un documento. `r` usa le colonne della vista unificata
    (dati.carica_dati_unificati): canale, sottofonte, data, titolo, url, temi,
    sentiment, ambito_geografico, livello_allarme, entita, ong_collegata, ong_link_score."""
    alto = pd.to_numeric(r.get('livello_allarme'), errors='coerce') >= 3
    sorgente = ' · '.join(x for x in [esc(r.get('canale')), esc(r.get('sottofonte'))] if x)
    titolo = esc(r.get('titolo')) or '(senza titolo)'
    url = str(r.get('url') or '').strip()
    h4 = (f'<a href="{esc(url)}" target="_blank" rel="noopener">{titolo}</a>'
          if url.lower().startswith('http') else titolo)
    temi = [t for t in str(r.get('temi') or '').split('|') if t.strip()]
    chips = ''.join(f'<span class="chip">{esc(t)}</span>' for t in temi) or \
        '<span class="chip chip-vuoto">Nessun tema</span>'
    s_lbl, s_cls = SENTIMENT[classe_sentiment(r.get('sentiment'))]
    pills = f'<span class="pill {s_cls}">{s_lbl}</span>'
    if r.get('ambito_geografico'):
        pills += f'<span class="pill">{esc(r.get("ambito_geografico"))}</span>'
    if alto:
        pills += '<span class="pill p-alto">Allarme alto</span>'
    if r.get('manuale'):
        pills += '<span class="pill p-manuale">Inserito a mano</span>'
    ents = ''
    entita = r.get('entita') or []
    if entita:
        ents = '<div class="ents">' + ''.join(
            f'<span class="ent" title="{esc(cat)}">{esc(nome)}</span>' for nome, cat in entita[:4]) + '</div>'
    txt = ''
    if estratto:
        testo = str(r.get('testo') or '').strip()
        if testo:
            txt = f'<p class="doc-txt">{esc(testo[:estratto])}{"…" if len(testo) > estratto else ""}</p>'
    piede = ''
    ong = str(r.get('ong_collegata') or '').strip()
    if ong and ong.lower() != 'nan':
        score = pd.to_numeric(r.get('ong_link_score'), errors='coerce')
        s = f' (score {int(score)})' if pd.notna(score) else ''
        piede = f'ONG collegata: {esc(ong)}{s}'
    return (f'<article class="doc{" doc-alto" if alto else ""}"><div class="doc-top">'
            f'<span class="doc-src">{sorgente}</span><time>{_data_it(r.get("data"))}</time></div>'
            f'<h4>{h4}</h4>{txt}<div class="doc-tags">{chips}{pills}</div>{ents}'
            f'<div class="doc-foot">{piede}</div></article>')


def doc_cards(df: pd.DataFrame, n: int | None = 12, una_colonna: bool = False, estratto: int = 0) -> str:
    if df.empty:
        return vuoto('Nessun documento con i filtri correnti.')
    righe = df.head(n) if n else df
    cls = 'docs docs-1' if una_colonna else 'docs'
    return f'<div class="{cls}">' + ''.join(doc_card(r, estratto) for r in righe.to_dict('records')) + '</div>'


def tabella_dati(df: pd.DataFrame, formati: dict | None = None, scroll: bool = True) -> str:
    """Tabella HTML semplice per l'export (equivalente di st.dataframe).
    formati: colonna -> 'data' | 'dataora' | 'pct' | 'int'."""
    formati = formati or {}
    if df.empty:
        return vuoto('Nessun dato.')
    testa = ''.join(f'<th>{esc(c)}</th>' for c in df.columns)
    righe = []
    for riga in df.itertuples(index=False):
        celle = []
        for col, val in zip(df.columns, riga):
            f = formati.get(col)
            if f == 'data':
                celle.append(f'<td>{_data_it(val)}</td>')
            elif f == 'dataora':
                d = pd.to_datetime(val, errors='coerce')
                celle.append(f'<td>{"" if pd.isna(d) else d.strftime("%d/%m/%Y %H:%M")}</td>')
            elif f == 'pct':
                v = pd.to_numeric(val, errors='coerce')
                celle.append(f'<td class="num">{"" if pd.isna(v) else f"{v * 100:.0f}%"}</td>')
            elif isinstance(val, (int, float)) and not isinstance(val, bool):
                celle.append(f'<td class="num">{"" if pd.isna(val) else (fmt_int(val) if float(val).is_integer() else f"{val:.2f}")}</td>')
            else:
                celle.append(f'<td>{esc(val)}</td>')
        righe.append(f'<tr>{"".join(celle)}</tr>')
    cls = 'tbl-wrap tbl-scroll' if scroll else 'tbl-wrap'
    return (f'<div class="{cls}"><table class="dati"><thead><tr>{testa}</tr></thead>'
            f'<tbody>{"".join(righe)}</tbody></table></div>')
