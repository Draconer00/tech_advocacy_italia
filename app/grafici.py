"""
Grafici del radar: funzioni pure dati -> figura Plotly (o HTML del grafo).
Usate identiche da dashboard Streamlit ed export HTML; lo stile viene da app/tema.py.
"""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

try:
    from . import tema
    from .tema import COLORI
except ImportError:  # eseguito come script / da Streamlit (cartella app nel path)
    import tema
    from tema import COLORI

ALTEZZA = 340


def _asse_mesi(fig: go.Figure) -> go.Figure:
    """Mesi 'YYYY-MM' mostrati come 05/2026 (Plotly li leggerebbe come date in inglese)."""
    fig.update_xaxes(type='category', categoryorder='category ascending')
    return fig


def timeline_giornaliera(df: pd.DataFrame) -> go.Figure:
    """Eventi per giorno: in rosso la quota con allarme alto (livello 3)."""
    d = df.dropna(subset=['data']).copy()
    d['serie'] = (d['livello_allarme'].fillna(1) >= 3).map({True: 'Allarme alto', False: 'Altri documenti'})
    g = d.groupby(['data', 'serie']).size().reset_index(name='conteggio')
    fig = px.bar(g, x='data', y='conteggio', color='serie', barmode='stack',
                 category_orders={'serie': ['Altri documenti', 'Allarme alto']},
                 color_discrete_map={'Altri documenti': COLORI['accent'], 'Allarme alto': COLORI['alarm']},
                 labels={'data': '', 'conteggio': 'Documenti', 'serie': ''})
    fig.update_traces(hovertemplate='%{x|%d/%m/%Y}<br>%{y} documenti<extra>%{fullData.name}</extra>')
    fig.update_xaxes(type='date', tickformat='%d/%m')
    fig.update_layout(hovermode='x unified')
    return tema.stile(fig, ALTEZZA)


def geografia_per_tipo(df: pd.DataFrame, ordine_tipi: list[str]) -> go.Figure:
    d = df.copy()
    d['tipo'] = tema.piega_categorie(d['tipo'], ordine_tipi)
    g = d.groupby(['ambito_geografico', 'tipo']).size().reset_index(name='conteggio')
    ordine_aree = [a for a in ['Italia', 'Europa', 'USA / Internazionale', 'Asia']
                   if a in set(g['ambito_geografico'])] + \
        sorted(set(g['ambito_geografico']) - {'Italia', 'Europa', 'USA / Internazionale', 'Asia'})
    fig = px.bar(g, x='ambito_geografico', y='conteggio', color='tipo', barmode='stack',
                 color_discrete_map=tema.colori_per(ordine_tipi),
                 category_orders={'ambito_geografico': ordine_aree, 'tipo': ordine_tipi + ['Altro']},
                 labels={'conteggio': 'Documenti', 'ambito_geografico': '', 'tipo': ''})
    fig.update_traces(hovertemplate='%{x}<br>%{y} documenti<extra>%{fullData.name}</extra>')
    return tema.stile(fig, 380)


def posizionamento(df_notizie: pd.DataFrame, centroidi: pd.DataFrame) -> go.Figure:
    """Piano Italia<->Mondo (x) / Tecnico<->Legale (y): notizie in grigio, ONG etichettate."""
    fig = go.Figure()
    fig.add_scatter(
        x=df_notizie['score_geografia'], y=df_notizie['score_tech_legale'], mode='markers',
        name='Notizie', text=df_notizie['titolo'],
        marker=dict(color=COLORI['muted'], size=6, opacity=0.35, line=dict(width=0)),
        hovertemplate='%{text}<extra>Notizia</extra>')
    n_tutti = pd.to_numeric(centroidi['numero_articoli'], errors='coerce').fillna(0)
    senza = centroidi[n_tutti <= 0]
    attive = centroidi[n_tutti > 0]
    n = n_tutti[n_tutti > 0]
    fig.add_scatter(
        x=attive['score_geografia'], y=attive['score_tech_legale'], mode='markers+text',
        name='ONG (centroide)', text=attive['nome'], textposition='top center',
        customdata=n, textfont=dict(size=11, color=COLORI['ink']),
        marker=dict(color=COLORI['ong'], size=(10 + n.clip(upper=120) ** 0.5 * 2.2), opacity=0.8,
                    line=dict(width=2, color=COLORI['surface'])),
        hovertemplate='<b>%{text}</b><br>%{customdata:.0f} articoli<extra></extra>')
    if not senza.empty:
        # ONG del profilo senza articoli: al centro per convenzione, senza etichetta
        # (si sovrapporrebbero), nome nel tooltip.
        fig.add_scatter(
            x=senza['score_geografia'], y=senza['score_tech_legale'], mode='markers',
            name=f'ONG senza articoli ({len(senza)}, al centro)', text=senza['nome'],
            marker=dict(color='rgba(0,0,0,0)', size=10, line=dict(width=1.5, color=COLORI['ong'])),
            hovertemplate='<b>%{text}</b><br>nessun articolo raccolto<extra></extra>')
    for asse in ('h', 'v'):
        kw = dict(line_dash='dash', line_color=COLORI['muted'], line_width=1)
        (fig.add_hline(y=0, **kw) if asse == 'h' else fig.add_vline(x=0, **kw))
    fig.update_xaxes(range=[-1.1, 1.1], title_text='Geografia: Italia (−1) ↔ Mondo (+1)', showgrid=True,
                     gridcolor=COLORI['line'], zeroline=False)
    fig.update_yaxes(range=[-1.1, 1.1], title_text='Tecnico (−1) ↔ Legale (+1)', zeroline=False)
    return tema.stile(fig, 640)


def mensile_per_fonte(df_conteggi: pd.DataFrame, ordine_fonti: list[str]) -> go.Figure:
    d = df_conteggi.copy()
    d['fonte'] = tema.piega_categorie(d['fonte'], ordine_fonti)
    d = d.groupby(['mese', 'fonte'], as_index=False)['conteggio'].sum()
    fig = px.bar(d, x='mese', y='conteggio', color='fonte', barmode='stack',
                 color_discrete_map=tema.colori_per(ordine_fonti),
                 category_orders={'fonte': ordine_fonti + ['Altro']},
                 labels={'mese': '', 'conteggio': 'Documenti', 'fonte': ''})
    fig.update_traces(hovertemplate='%{x}<br>%{y} documenti<extra>%{fullData.name}</extra>')
    fig.update_layout(hovermode='x unified')
    return tema.stile(_asse_mesi(fig), 380)


def sanzioni(df_sanzioni: pd.DataFrame) -> go.Figure:
    fig = px.line(df_sanzioni, x='mese', y='importo_eur', markers=True,
                  labels={'mese': '', 'importo_eur': 'Importo totale (€)'})
    fig.update_traces(line_color=COLORI['accent'], marker_color=COLORI['accent'],
                      hovertemplate='%{x}<br>%{y:,.0f} €<extra></extra>')
    return tema.stile(_asse_mesi(fig), 300)


def trend_temi(df_kw: pd.DataFrame, ordine_temi: list[str]) -> go.Figure:
    """Linee mese x tema. Massimo 8 serie (palette categorica): i temi oltre
    l'ottavo per volume sono esclusi dal grafico e restano nella tabella."""
    tenuti = ordine_temi[:len(tema.CATEGORICI)]
    d = df_kw[df_kw['tema'].isin(tenuti)]
    fig = px.line(d, x='mese', y='conteggio', color='tema', markers=True,
                  color_discrete_map=tema.colori_per(tenuti), category_orders={'tema': tenuti},
                  labels={'mese': '', 'conteggio': 'Documenti che trattano il tema', 'tema': ''})
    fig.update_traces(hovertemplate='%{y}<extra>%{fullData.name}</extra>')
    fig.update_layout(hovermode='x unified')
    return tema.stile(_asse_mesi(fig), 400)


def trend_topic(df_t: pd.DataFrame, ordine: list[str]) -> go.Figure:
    fig = px.line(df_t.sort_values('mese'), x='mese', y='conteggio', color='Topic', markers=True,
                  color_discrete_map=tema.colori_per(ordine), category_orders={'Topic': ordine},
                  labels={'mese': '', 'conteggio': 'Documenti', 'Topic': ''})
    fig.update_traces(hovertemplate='%{y}<extra>%{fullData.name}</extra>')
    fig.update_layout(hovermode='x unified', legend=dict(orientation='v', y=1, yanchor='top',
                                                         x=1.01, xanchor='left'))
    return tema.stile(_asse_mesi(fig), 380)


# --- GRAFO (pyvis / vis-network) ---------------------------------------------
_OPZIONI_GRAFO = """
{
  "nodes": {"shape": "dot", "borderWidth": 1.5, "borderWidthSelected": 3,
    "font": {"size": 12, "face": "IBM Plex Sans, system-ui, sans-serif", "color": "#17212b",
             "strokeWidth": 3, "strokeColor": "#ffffff"}},
  "edges": {"color": {"inherit": false, "color": "#c9cfcb", "highlight": "#1d5a7a", "hover": "#1d5a7a"},
    "width": 1, "smooth": false},
  "layout": {"randomSeed": 42},
  "physics": {"enabled": true, "solver": "forceAtlas2Based",
    "forceAtlas2Based": {"gravitationalConstant": -150, "centralGravity": 0.01,
      "springLength": 200, "springConstant": 0.05, "avoidOverlap": 1},
    "stabilization": {"enabled": true, "iterations": 1000, "updateInterval": 100}},
  "interaction": {"hover": true, "multiselect": true, "navigationButtons": false,
    "tooltipDelay": 50, "zoomView": true, "zoomSpeed": 0.25, "dragView": true}
}
"""


def html_grafo(G, altezza_px: int = 700) -> str:
    """Pagina HTML autonoma (JS di vis-network inline) del grafo: la stessa va
    in components.html (Streamlit) e in un iframe srcdoc (export)."""
    from pyvis.network import Network

    net = Network(height=f'{altezza_px}px', width='100%', bgcolor=COLORI['surface'],
                  font_color=COLORI['ink'], select_menu=False, filter_menu=False,
                  directed=False, cdn_resources='in_line')
    net.from_nx(G)
    # vis-network applica lo stile del gruppo sopra il colore del singolo nodo:
    # i colori della palette vanno quindi dichiarati per gruppo.
    import json
    try:
        from .dati import GRUPPI_GRAFO
    except ImportError:
        from dati import GRUPPI_GRAFO
    opzioni = json.loads(_OPZIONI_GRAFO)
    forme = {'ONG': 'dot', 'Tema': 'dot', 'Notizia': 'diamond', 'NotiziaGenerale': 'diamond'}
    opzioni['groups'] = {
        g: {'shape': forme[g], 'color': {'background': c, 'border': COLORI['surface'],
                                          'highlight': {'background': c, 'border': COLORI['ink']},
                                          'hover': {'background': c, 'border': COLORI['ink']}}}
        for g, (c, _) in GRUPPI_GRAFO.items()}
    net.set_options(json.dumps(opzioni))
    pagina = net.generate_html(notebook=False)
    # Il grafo può nascere in una scheda nascosta (larghezza 0): quando il
    # contenitore prende dimensione, ricentra la vista su tutto il grafo.
    ricentra = ('<script>(function(){var c=document.getElementById("mynetwork");'
                'if(!c||!window.ResizeObserver)return;var t;new ResizeObserver(function(){'
                'clearTimeout(t);t=setTimeout(function(){if(window.network&&c.offsetWidth>0)'
                '{network.fit();}},150);}).observe(c);})();</script>')
    pagina = pagina.replace('</body>', ricentra + '</body>', 1)
    # niente bordo/margini della pagina pyvis: il pannello fa da cornice
    return pagina.replace('<head>', '<head><style>body{margin:0}#mynetwork{border:0!important}'
                          '.card{border:0!important}</style>', 1)
