"""
Contenuto delle schede descritto come blocchi neutri rispetto al target.

Ogni scheda è una lista di blocchi (HTML, grafico, pannello, colonne, dettagli,
tabella, grafo, selettore). La dashboard li rende con i widget Streamlit,
app/export_html.py con HTML statico: lo stesso contenuto, nello stesso ordine,
con lo stesso aspetto. I widget interattivi (filtri, strumenti di correzione)
restano nella dashboard; l'export mostra lo stato dei filtri predefiniti.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

import pandas as pd

try:
    from . import dati, tema, grafici
    from .tema import esc, fmt_int
except ImportError:
    import dati
    import tema
    import grafici
    from tema import esc, fmt_int


# --- BLOCCHI -----------------------------------------------------------------
@dataclass
class Html:
    html: str


@dataclass
class Grafico:
    fig: object


@dataclass
class Pannello:
    titolo: str
    blocchi: list
    sottotitolo: str = ''
    nota: str = ''


@dataclass
class Colonne:
    colonne: list
    pesi: list = field(default_factory=list)


@dataclass
class Dettagli:
    titolo: str
    blocchi: list
    aperto: bool = False


@dataclass
class Tabella:
    df: pd.DataFrame
    formati: dict = field(default_factory=dict)
    etichette: dict = field(default_factory=dict)


@dataclass
class Grafo:
    html: str
    altezza: int = 720


@dataclass
class Selettore:
    """Scelta di un gruppo fra molti: st.selectbox in dashboard, <select> nell'export."""
    etichetta: str
    opzioni: dict  # etichetta opzione -> lista di blocchi
    chiave: str = 'selettore'


def filtri_attivi(voci: list[tuple[str, str]]) -> Pannello:
    """Riepilogo dei filtri (solo export: in dashboard al suo posto ci sono i widget)."""
    pills = ''.join(f'<span class="pill">{esc(k)}: <strong>{esc(v)}</strong></span>' for k, v in voci)
    return Pannello('Filtri', [Html(tema.rd(f'<div class="doc-tags">{pills}</div>'))],
                    nota='Valori fissati per questa fotografia; nel dashboard i filtri sono modificabili.')


# --- MASTHEAD ----------------------------------------------------------------
def masthead(df_master: pd.DataFrame, stamp: str) -> Html:
    ultimi7 = int((df_master['data'] >= (datetime.now().date() - pd.Timedelta(days=7))).sum())
    alto = int((df_master['livello_allarme'] >= 3).sum())
    date = pd.to_datetime(df_master['data'], errors='coerce').dropna()
    periodo = f"{date.min():%d/%m/%Y} – {date.max():%d/%m/%Y}" if not date.empty else 'n.d.'
    kpis = [(fmt_int(len(df_master)), 'documenti analizzati'),
            (fmt_int(df_master['fonte'].nunique()), 'fonti monitorate'),
            (fmt_int(alto), 'con allarme alto (livello 3)', 'alto'),
            (fmt_int(ultimi7), 'pubblicati negli ultimi 7 giorni'),
            (periodo, 'periodo coperto', 'small')]
    return Html(tema.rd(tema.masthead(stamp, kpis)))


# --- 1. PANORAMICA -------------------------------------------------------------
def testata_home() -> Html:
    return Html(tema.rd(tema.sec_head(
        'Home Radar', 'Panoramica generale',
        'Volume dei documenti raccolti nel tempo e ultime uscite, da tutte le fonti processate. '
        'In rosso i documenti con allarme alto (livello 3).')))


def vista_home(df: pd.DataFrame, dati_raw: dict) -> list:
    senza_data = int(df['data'].isna().sum())
    if df.dropna(subset=['data']).empty:
        timeline = [Html(tema.rd(tema.vuoto('Nessun documento datato con i filtri correnti.')))]
    else:
        timeline = [Grafico(grafici.timeline_giornaliera(df))]
    per_canale = df['canale'].value_counts()
    blocchi = [
        Colonne([
            [Pannello('Eventi per giorno', timeline,
                      sottotitolo=f'{fmt_int(len(df))} documenti nella vista',
                      nota=(f'{fmt_int(senza_data)} documenti senza data di pubblicazione non compaiono nel grafico.'
                            if senza_data else ''))],
            [Pannello('Documenti per canale', [Html(tema.rd(tema.hbars(per_canale)))],
                      sottotitolo='Canale di raccolta (scraper)')],
        ], pesi=[1.35, 1]),
        Html(tema.rd(tema.sottotitolo('Ultimi 12 eventi') + tema.doc_cards(df, 12))),
        Dettagli('Tabella · ultimi 50 eventi', [Tabella(
            df[['data', 'categoria', 'fonte', 'tipo', 'titolo', 'livello_allarme']].head(50),
            formati={'data': 'data'},
            etichette={'data': 'Data', 'categoria': 'Categoria', 'fonte': 'Fonte', 'tipo': 'Tipo',
                       'titolo': 'Titolo', 'livello_allarme': 'Allarme'})]),
    ]
    if dati_raw:
        blocchi.append(Pannello(
            'Ultime notizie per fonte',
            [Dettagli(f'{etichetta} — {fmt_int(len(d))} notizie', [Tabella(
                d, formati={'data_scraping': 'dataora'},
                etichette={'titolo': 'Titolo', 'data_scraping': 'Data raccolta'})])
             for etichetta, d in dati_raw.items()],
            sottotitolo='Titolo e data di raccolta dal CSV grezzo di ciascuno scraper, '
                        'indipendentemente dalla classificazione NLP.'))
    else:
        blocchi.append(Html(tema.rd(tema.callout(
            'Nessun dato grezzo trovato in <code>data/raw/</code>. Esegui gli scraper per popolare questa sezione.'))))
    return blocchi


# --- 2. CAMPAGNE ONG -----------------------------------------------------------
def testata_ong() -> Html:
    return Html(tema.rd(tema.sec_head(
        'Campagne ONG', 'Comunicati delle organizzazioni',
        'Comunicati, report e prese di posizione delle organizzazioni della società civile monitorate.')))


def avviso_ong_mancanti(mancanti: list[str]) -> list:
    if not mancanti:
        return []
    return [Html(tema.rd(tema.callout(
        f'{len(mancanti)} ONG senza documenti raccolti: ' + esc(', '.join(mancanti)), 'warn')))]


def vista_ong(df_ong_unif: pd.DataFrame, n_organizzazioni: int) -> list:
    if df_ong_unif.empty:
        return [Html(tema.rd(tema.callout(
            'Nessun documento ONG con i filtri correnti. Esegui lo scraper delle ONG o aggiungi un documento a mano.')))]
    d = df_ong_unif.sort_values('data', ascending=False, na_position='last')
    per_ong = d['fonte'].value_counts()
    gruppi = {}
    for nome in sorted(d['fonte'].unique()):
        docs = d[d['fonte'] == nome]
        gruppi[nome] = [Html(tema.rd(tema.nota(f'{fmt_int(len(docs))} documenti per {esc(nome)}')
                                     + tema.doc_cards(docs, n=None, una_colonna=True, estratto=500)))]
    return [
        Html(tema.rd(tema.kpi_row([(fmt_int(len(d)), 'comunicati analizzati'),
                                   (fmt_int(n_organizzazioni), 'organizzazioni selezionate')]))),
        Colonne([
            [Pannello('Documenti per organizzazione', [Html(tema.rd(tema.hbars(per_ong, 'ong')))])],
            [Pannello('Più recenti', [Html(tema.rd(tema.doc_cards(d, 6, una_colonna=True)))])],
        ], pesi=[1, 1.15]),
        Html(tema.rd(tema.sottotitolo('Documenti per organizzazione'))),
        Selettore("Scegli un'ONG per il dettaglio", gruppi, chiave='ong_dettaglio'),
    ]


# --- 3. GEOGRAFIA --------------------------------------------------------------
def testata_geo() -> Html:
    return Html(tema.rd(tema.sec_head(
        'Provvedimenti e geografia', 'Dove avvengono i fatti',
        'Ambito geografico assegnato dalla pipeline NLP a ogni documento, per tipologia di contenuto e canale.')))


AREE = ['Italia', 'Europa', 'USA / Internazionale', 'Asia']


def vista_geo(df: pd.DataFrame, ordine_tipi: list[str]) -> list:
    amb = df['ambito_geografico']
    kpi = tema.kpi_row([(fmt_int(len(df)), 'documenti analizzati'),
                        (fmt_int((amb == 'Italia').sum()), 'Italia'),
                        (fmt_int((amb == 'Europa').sum()), 'Europa'),
                        (fmt_int(amb.isin(['USA / Internazionale', 'Asia']).sum()), 'Mondo')])
    if df.empty:
        return [Html(tema.rd(kpi + tema.vuoto('Nessun documento con i filtri correnti.')))]
    pivot = pd.crosstab(df['canale'], df['ambito_geografico'])
    pivot = pivot[[a for a in AREE if a in pivot.columns] + [c for c in pivot.columns if c not in AREE]]
    pivot = pivot.loc[pivot.sum(axis=1).sort_values(ascending=False).index]
    return [
        Html(tema.rd(kpi)),
        Colonne([
            [Pannello('Distribuzione geografica per tipologia', [Grafico(grafici.geografia_per_tipo(df, ordine_tipi))])],
            [Pannello('Area × canale', [Html(tema.rd(tema.heat_table(pivot, tema.COLORI['geo'])))],
                      sottotitolo='Documenti per canale di raccolta e area')],
        ], pesi=[1.35, 1]),
        Dettagli(f'Elenco di tutti i documenti ({fmt_int(len(df))})', [Tabella(
            df[['data', 'categoria', 'fonte', 'tipo', 'ambito_geografico', 'titolo', 'livello_allarme']],
            formati={'data': 'data'},
            etichette={'data': 'Data', 'categoria': 'Categoria', 'fonte': 'Fonte', 'tipo': 'Tipo',
                       'ambito_geografico': 'Area', 'titolo': 'Titolo', 'livello_allarme': 'Allarme'})]),
    ]


# --- 4. NETWORK ----------------------------------------------------------------
def testata_network() -> Html:
    return Html(tema.rd(
        tema.sec_head('Network temi', 'Legami tra ONG, temi e notizie',
                      'Ogni ONG è collegata ai temi del suo profilo e alle notizie che ha pubblicato. '
                      'Le notizie di altre fonti si agganciano al tema con più parole chiave in comune; '
                      'sotto la soglia minima restano fuori dal grafo, per non inventare associazioni deboli. '
                      'Sono incluse le notizie degli ultimi 30 giorni o con allarme alto.')
        + tema.legenda([dati.GRUPPI_GRAFO[k] for k in ('ONG', 'Tema', 'Notizia', 'NotiziaGenerale')])))


def vista_network(html_grafo: str, stats: dict) -> list:
    return [
        Html(tema.rd(tema.kpi_row([(fmt_int(stats['ONG']), 'organizzazioni'),
                                   (fmt_int(stats['Tema']), 'temi monitorati'),
                                   (fmt_int(stats['Notizia']), 'notizie ONG'),
                                   (fmt_int(stats['NotiziaGenerale']), 'notizie da altre fonti'),
                                   (fmt_int(stats['archi']), 'connessioni')]))),
        Pannello('', [Grafo(html_grafo)],
                 nota='Trascina i nodi per muovere la rete, usa la rotella per lo zoom, passa sopra un nodo per i dettagli. '
                      'Il collegamento notizia → tema è calcolato per sovrapposizione lessicale: va letto come indicativo.'),
    ]


# --- 5. POSIZIONAMENTO ---------------------------------------------------------
def testata_posizionamento() -> Html:
    assi = ('<table class="assi"><thead><tr><th>Asse</th><th>−1</th><th>+1</th></tr></thead><tbody>'
            '<tr><th>Orizzontale</th><td>Italia</td><td>Mondo</td></tr>'
            '<tr><th>Verticale</th><td>Tecnico</td><td>Legale</td></tr></tbody></table>')
    return Html(tema.rd(
        tema.sec_head('Mappa di posizionamento', 'Dove si collocano le ONG',
                      'Piano a due assi: ogni notizia ONG è un punto grigio, ogni ONG è il centroide delle sue '
                      'notizie (cerchio viola, più grande se pubblica di più).') + assi))


def vista_posizionamento(df_notizie: pd.DataFrame, centroidi: pd.DataFrame) -> list:
    return [Pannello('', [Grafico(grafici.posizionamento(df_notizie, centroidi))],
                     nota='Gli score derivano da regole sul profilo ONG (60%) e da parole chiave legali/tecniche '
                          'nel testo (40%), più l\'ambito geografico degli articoli: è una stima, non una misura. '
                          'Passa sopra i punti per i dettagli.')]


# --- 6. TEMI NEL TEMPO ---------------------------------------------------------
def testata_tempo() -> Html:
    return Html(tema.rd(tema.sec_head(
        'Analisi temporale', 'Andamento di fonti e temi',
        'A · documenti pubblicati ogni mese, per fonte. B · tendenze dei temi tech e diritti digitali, '
        'per capire quali argomenti crescono o calano.')))


def vista_tempo_a(df_periodo: pd.DataFrame, ordine_fonti: list[str], df_sanzioni: pd.DataFrame) -> list:
    blocchi = [Html(tema.rd(tema.kpi_row([(fmt_int(len(df_periodo)), 'documenti nel periodo selezionato')])))]
    if df_periodo.empty:
        return blocchi + [Html(tema.rd(tema.vuoto('Nessun documento nel periodo selezionato.')))]
    blocchi.append(Pannello('A · Documenti per mese, per fonte',
                            [Grafico(grafici.mensile_per_fonte(dati.conteggio_mensile_per_fonte(df_periodo), ordine_fonti))],
                            sottotitolo='Periodi di maggiore attività regolatoria o giornalistica.'))
    if not df_sanzioni.empty:
        blocchi.append(Pannello('Totale sanzioni (EUR) per mese — solo GPDP/AGCOM', [Grafico(grafici.sanzioni(df_sanzioni))]))
    else:
        blocchi.append(Html(tema.rd(tema.nota(
            'Grafico delle sanzioni: la colonna <code>importo_eur</code> non è presente o non ha valori nei dati '
            'attuali; comparirà automaticamente quando i dati saranno disponibili.'))))
    return blocchi


def _righe_trend(confronto: pd.DataFrame, df_kw: pd.DataFrame, mesi: list[str]) -> str:
    if confronto.empty:
        return tema.vuoto('Nessun tema in questa direzione.')
    righe = []
    for nome, r in confronto.iterrows():
        serie = df_kw[df_kw['tema'] == nome].set_index('mese')['conteggio'].reindex(mesi, fill_value=0).tolist()
        segno = '+' if r['variazione_pct'] > 0 else ''
        cls = 'delta-su' if r['variazione_pct'] > 0 else 'delta-giu'
        righe.append(f'<div class="trend"><span class="trend-n">{esc(nome)}</span>{tema.sparkline(serie)}'
                     f'<span class="trend-v">{r["freq_recente"]:.1f}<small> doc/mese</small> · '
                     f'<span class="{cls}">{segno}{r["variazione_pct"]:.0f}%</span></span></div>')
    return f'<div class="trends">{"".join(righe)}</div>'


def vista_tempo_b(df_kw: pd.DataFrame, livello: str, sotto_attivi: pd.DataFrame) -> list:
    intro = []
    if livello != "Macro-temi" and not sotto_attivi.empty:
        intro.append(Html(tema.rd(tema.nota(
            'Sotto-temi introdotti nel tempo: ' + '; '.join(
                f'<strong>{esc(r["tema"])}</strong> (in {esc(r["padre"])}, dal {esc(r["dal"] or "n.d.")})'
                for _, r in sotto_attivi.iterrows())
            + '. Il trend è <strong>retroattivo</strong>: la pipeline riapplica il registro a tutto lo storico, '
              'quindi i mesi precedenti all\'introduzione sono ricostruiti a posteriori.'))))
    elif livello == "Sotto-temi":
        intro.append(Html(tema.rd(tema.callout('Nessun sotto-tema attivo. Puoi crearne uno dalla scheda Topic emergenti.'))))

    descr = ('Temi rilevati dalla pipeline NLP con approccio ibrido: match lessicale sul lessico curato '
             '(<code>data/utils/temi.csv</code>) più match semantico via embedding, che recupera sinonimi e '
             'parafrasi anche in altre lingue.')
    if df_kw.empty:
        return intro + [Pannello('B · Tendenze dei temi nel tempo', [Html(tema.rd(tema.vuoto(
            'Nessun tema rilevato nel periodo selezionato.')))], sottotitolo=descr)]

    ordine = df_kw.groupby('tema')['conteggio'].sum().sort_values(ascending=False).index.tolist()
    nota_cap = (f'Nel grafico i {len(tema.CATEGORICI)} temi più frequenti; gli altri sono nella tabella.'
                if len(ordine) > len(tema.CATEGORICI) else '')
    blocchi = intro + [Pannello('B · Tendenze dei temi nel tempo', [Grafico(grafici.trend_temi(df_kw, ordine))],
                                sottotitolo=descr, nota=nota_cap)]

    esito = dati.confronto_temi(df_kw)
    if esito is None:
        blocchi.append(Html(tema.rd(tema.nota(
            'Dati insufficienti per calcolare crescita e calo (servono almeno 4 mesi distinti).'))))
    else:
        conf, prec, rec = esito
        mesi = sorted(df_kw['mese'].unique())[-6:]
        su = conf[conf['variazione_pct'] > 0].head(5)
        giu = conf[conf['variazione_pct'] < 0].tail(5).sort_values('variazione_pct')
        blocchi.append(Html(tema.rd(tema.sottotitolo(
            f'Variazione della frequenza: {prec[0]}–{prec[1]} → {rec[0]}–{rec[1]}'))))
        blocchi.append(Colonne([
            [Pannello('In crescita', [Html(tema.rd(_righe_trend(su, df_kw, mesi)))])],
            [Pannello('In calo', [Html(tema.rd(_righe_trend(giu, df_kw, mesi)))])],
        ], pesi=[1, 1]))

    tabella = df_kw.pivot_table(index='mese', columns='tema', values='conteggio', fill_value=0).reset_index()
    blocchi.append(Dettagli('Tabella dettagliata · documenti per tema per mese',
                            [Tabella(tabella, etichette={'mese': 'Mese'})]))
    return blocchi


# --- 7. TOPIC EMERGENTI --------------------------------------------------------
VALUTAZIONI = {'coperto': 'Già coperto', 'candidato_sottotema': 'Candidato sotto-tema',
               'fuori_lessico': 'Fuori lessico'}


def testata_topic() -> Html:
    return Html(tema.rd(
        tema.sec_head('Topic emergenti', 'Argomenti nuovi scoperti dai dati',
                      'Cluster di documenti trovati automaticamente da BERTopic. Sono proposte da validare a mano, '
                      'non temi ufficiali.')
        + tema.callout('Vista esplorativa, distinta dai temi curati: i trend di <em>Temi nel tempo</em> tracciano i '
                       'temi che già conosci (<code>temi.csv</code>); qui la clusterizzazione non supervisionata '
                       'scopre argomenti non previsti, da promuovere eventualmente nel lessico curato. Essendo '
                       'statistica, può cambiare tra un\'esecuzione e l\'altra: da leggere come radar, non come misura.')))


def _etichetta_topic(r) -> str:
    return f"#{int(r['topic_id'])} · " + ', '.join(str(r['parole_chiave']).split(', ')[:3])


def etichette_topic(df_topic: pd.DataFrame) -> dict:
    return {int(r['topic_id']): _etichetta_topic(r) for _, r in df_topic.iterrows()}


def _quota(v) -> str:
    v = pd.to_numeric(v, errors='coerce')
    return '' if pd.isna(v) else f'quota {v * 100:.0f}%'


def tabella_topic(df_topic: pd.DataFrame, df_trend: pd.DataFrame) -> str:
    mesi = []
    if not df_trend.empty:
        tutti = pd.period_range(df_trend['mese'].min(), df_trend['mese'].max(), freq='M').astype(str).tolist()
        mesi = tutti[-12:]
    righe = []
    for _, r in df_topic.sort_values('dimensione', ascending=False).iterrows():
        tid = int(r['topic_id'])
        spark = ''
        if mesi:
            s = df_trend[df_trend['topic_id'] == tid].set_index('mese')['conteggio']
            spark = tema.sparkline(s.reindex(mesi, fill_value=0).tolist(), 110, 28)
        val = str(r.get('valutazione', '') or '')
        pill = (f'<span class="pill p-{esc(val)}">{esc(VALUTAZIONI.get(val, val))}</span>' if val else '')
        sotto = str(r.get('sottotema_esistente', '') or '')
        sotto = '' if sotto.lower() == 'nan' else sotto
        righe.append(
            f'<tr><td class="num">#{tid}</td><td class="num">{fmt_int(r["dimensione"])}</td>'
            f'<td><strong>{esc(r["parole_chiave"])}</strong><div class="es">Es.: {esc(r.get("titoli_esempio", ""))}</div></td>'
            f'<td><div class="es">{esc(r.get("fonti", ""))}</div></td>'
            f'<td>{pill}</td>'
            f'<td>{esc(r.get("padre_proposto", ""))}<div class="es">{_quota(r.get("quota_padre"))}</div></td>'
            f'<td>{esc(sotto) or "—"}<div class="es">{_quota(r.get("quota_sottotema")) if sotto else ""}</div></td>'
            f'<td>{spark}</td></tr>')
    return ('<div class="tbl-wrap"><table class="topics"><thead><tr><th>ID</th><th>Doc.</th>'
            '<th>Parole distintive e titoli d\'esempio</th><th>Fonti</th><th>Confronto con i temi</th>'
            '<th>Macro-tema prevalente</th><th>Sotto-tema prevalente</th><th>Ultimi 12 mesi</th></tr></thead>'
            f'<tbody>{"".join(righe)}</tbody></table></div>')


def vista_topic(df_topic: pd.DataFrame, df_trend: pd.DataFrame) -> list:
    if df_topic.empty:
        return [Html(tema.rd(tema.callout(
            'Nessun report di scoperta trovato. Generalo (offline, periodicamente) con '
            '<code>python nlp/topic_discovery.py</code>: produce <code>data/processed/topic_emergenti.csv</code> '
            'e <code>_trend.csv</code>, che questa vista legge.', 'warn')))]
    return [
        Html(tema.rd(tema.kpi_row([(fmt_int(len(df_topic)), 'topic scoperti'),
                                   (fmt_int(df_topic['dimensione'].sum()), 'documenti raggruppati')]))),
        Pannello('Topic per dimensione', [Html(tema.rd(tabella_topic(df_topic, df_trend)))],
                 sottotitolo='Parole distintive (c-TF-IDF) e titoli d\'esempio dicono di cosa parla ogni cluster. '
                             '<strong>Confronto con i temi</strong>: già coperto da un sotto-tema · candidato '
                             '(dentro un macro-tema ma senza sotto-tema) · fuori lessico (nessun tema lo copre).'),
    ]


def vista_topic_trend(df_topic: pd.DataFrame, df_trend: pd.DataFrame, scelti: list[int]) -> list:
    if df_topic.empty or df_trend.empty or not scelti:
        return []
    etich = etichette_topic(df_topic)
    ordine = [etich[t] for t in scelti if t in etich]
    df_t = df_trend[df_trend['topic_id'].isin(scelti)].copy()
    df_t['Topic'] = df_t['topic_id'].map(etich)
    return [Pannello('Andamento nel tempo', [Grafico(grafici.trend_topic(df_t, ordine))],
                     sottotitolo='Documenti per topic emergente, per mese.')]


def vista_registro(registro: pd.DataFrame) -> list:
    sotto = registro[registro['padre'] != '']
    macro = registro[registro['padre'] == ''][['tema', 'termini', 'soglia', 'stato', 'dal']]
    et = {'tema': 'Tema', 'termini': 'Termini', 'soglia': 'Soglia', 'stato': 'Stato', 'dal': 'Dal',
          'padre': 'Macro-tema', 'origine': 'Origine'}
    return [
        Html(tema.rd(tema.sottotitolo('Registro dei temi') + tema.nota(
            'Un <strong>sotto-tema</strong> specializza uno dei macro-temi (es. <em>Chat Control</em> dentro '
            '<em>Chat e Messaggistica</em>); i suoi documenti contano anche per il macro-tema. I macro-temi sono il '
            'riferimento stabile per trend e gold set e si modificano solo in <code>data/utils/temi.csv</code>.'))),
        Dettagli(f'Sotto-temi registrati ({len(sotto)})',
                 [Tabella(sotto, etichette=et)] if not sotto.empty
                 else [Html(tema.rd(tema.vuoto('Nessun sotto-tema ancora registrato.')))]),
        Dettagli(f'Macro-temi (sola lettura, {len(macro)})', [Tabella(macro, etichette=et)]),
    ]


# --- 8. METODO -----------------------------------------------------------------
def vista_metodo(df_master: pd.DataFrame, stamp: str, statico: bool) -> list:
    senza_tema = int((df_master['temi'].fillna('') == '').sum())
    senza_data = int(df_master['data'].isna().sum())
    voci = [
        f'{esc(stamp)}. Dati letti dai file <code>data/processed/*_analyzed.csv</code> (più i documenti ONG '
        f'inseriti a mano); nessun dato viene modificato o aggiunto da questa vista.',
        'Temi, sentiment, ambito geografico, livello di allarme ed entità sono <strong>classificazioni automatiche</strong> '
        'della pipeline NLP, non fatti verificati.',
        f'{fmt_int(senza_tema)} documenti su {fmt_int(len(df_master))} non hanno un tema; '
        f'{fmt_int(senza_data)} non hanno una data di pubblicazione.',
        'Il collegamento notizia → ONG (<code>ong_link_score</code>) e notizia → tema nel network sono calcolati per '
        'sovrapposizione lessicale: vanno letti come indicativi.',
        'La mappa di posizionamento è una stima a regole (profilo ONG + parole chiave + ambito geografico), non una misura.',
        'I topic emergenti sono cluster statistici (BERTopic) e possono cambiare tra un\'esecuzione e l\'altra.',
        'Alcuni titoli possono contenere caratteri non leggibili: è un problema di codifica presente nei dati sorgente, '
        'mostrato così com\'è.',
        'Il livello di allarme e la correzione delle classificazioni sono alimentati dall\'active learning: le correzioni '
        'degli operatori vengono salvate in <code>training_data_feedback.csv</code> e usate al riaddestramento successivo.',
    ]
    if statico:
        voci.append('Questa è una <strong>fotografia statica</strong> del dashboard: i filtri sono fissati ai valori '
                    'indicati in ogni scheda e gli strumenti di correzione sono disponibili solo nel dashboard Streamlit.')
    return [Html(tema.rd(
        tema.sec_head('Note di metodo', 'Da dove vengono questi numeri')
        + '<div class="metodo"><ul>' + ''.join(f'<li>{v}</li>' for v in voci) + '</ul></div>'))]
