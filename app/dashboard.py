"""
Dashboard Streamlit del Radar Diritti Digitali.

Aggrega i dati NLP-processati e li presenta in otto schede (panoramica, campagne
ONG, geografia, network temi, mappa di posizionamento, analisi temporale, topic
emergenti, note di metodo).

Il contenuto delle schede è descritto in app/viste.py come blocchi neutri e reso
qui con i widget Streamlit; app/export_html.py rende gli stessi blocchi in HTML
statico per i beta tester. Lo stile (token, CSS, template Plotly) è in app/tema.py.
Solo la dashboard ha i filtri interattivi e gli strumenti operatore (correzioni
per l'active learning, documenti manuali, profilo keyword ONG, sotto-temi).
"""
import os
import sys
from datetime import datetime

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

CARTELLA_APP = os.path.dirname(os.path.abspath(__file__))
for _p in (CARTELLA_APP, os.path.abspath(os.path.join(CARTELLA_APP, '..'))):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import dati  # noqa: E402
import grafici  # noqa: E402
import tema  # noqa: E402
import viste as V  # noqa: E402
from scrapers.scraper_ong import PROFILI_ONG  # noqa: E402
from utils.feedback_schema import append_correzioni  # noqa: E402
from utils.ong_profile import carica_profilo_keywords_ong, salva_profilo_keywords_ong  # noqa: E402
from utils.ong_manual_entries import salva_documento_manuale  # noqa: E402
from nlp.theme_matching import STATI as STATI_TEMA, SOGLIA_SOTTOTEMA, salva_registro_temi  # noqa: E402

st.set_page_config(page_title=tema.TITOLO, page_icon="⚖️", layout="wide")
st.markdown(tema.css_streamlit(), unsafe_allow_html=True)

# --- DATI (cache sui loader puri di app/dati.py) ------------------------------
carica_dati_unificati = st.cache_data(dati.carica_dati_unificati)
carica_dati_ong = st.cache_data(dati.carica_dati_ong)
carica_dati_per_analisi_temporale = st.cache_data(dati.carica_dati_per_analisi_temporale)
carica_dati_raw_per_fonte = st.cache_data(dati.carica_dati_raw_per_fonte)
carica_topic_emergenti = st.cache_data(dati.carica_topic_emergenti)
carica_registro = st.cache_data(dati.carica_registro)
carica_temi = st.cache_data(dati.carica_temi)
carica_dati_gnews = st.cache_data(dati.carica_dati_gnews)
carica_dati_tech_news = st.cache_data(dati.carica_dati_tech_news)
carica_dati_rss_eu = st.cache_data(dati.carica_dati_rss_eu)
carica_dati_eu_parl = st.cache_data(dati.carica_dati_eu_parl)
carica_dati_agcom = st.cache_data(dati.carica_dati_agcom)


@st.cache_data
def grafo_network(df_ong: pd.DataFrame, profilo: dict, correzioni: dict) -> tuple[str, dict]:
    fonti_generaliste = {
        "GNews": carica_dati_gnews(), "Tech News Italiane": carica_dati_tech_news(),
        "RSS Regolatori Europei": carica_dati_rss_eu(), "Parlamento Europeo": carica_dati_eu_parl(),
        "AGCOM": carica_dati_agcom(),
    }
    G = dati.costruisci_grafo(df_ong, fonti_generaliste, profilo, correzioni)
    return grafici.html_grafo(G), dati.statistiche_grafo(G)


df_unificato = carica_dati_unificati()
df_ong = carica_dati_ong()
df_master = dati.prepara_master(df_unificato)


# --- RENDERER DEI BLOCCHI ------------------------------------------------------
_contatore_pannelli = [0]


def pannello():
    """st.container con bordo e chiave 'pannello_N': la chiave diventa la classe CSS
    st-key-pannello_N, che tema.CSS_STREAMLIT colora come i .panel dell'export."""
    _contatore_pannelli[0] += 1
    return st.container(border=True, key=f"pannello_{_contatore_pannelli[0]}")

def _column_config(formati: dict, etichette: dict) -> dict:
    cfg = {}
    for col, f in formati.items():
        nome = etichette.get(col, col)
        if f == 'data':
            cfg[nome] = st.column_config.DateColumn(nome, format="DD/MM/YYYY")
        elif f == 'dataora':
            cfg[nome] = st.column_config.DatetimeColumn(nome, format="DD/MM/YYYY HH:mm")
        elif f == 'pct':
            cfg[nome] = st.column_config.ProgressColumn(nome, format="%.0f%%", min_value=0, max_value=1)
    if 'Titolo' in etichette.values():
        cfg.setdefault('Titolo', st.column_config.TextColumn('Titolo', width="large"))
    return cfg


def rendi(blocchi: list) -> None:
    for b in blocchi:
        if isinstance(b, V.Html):
            st.markdown(b.html, unsafe_allow_html=True)
        elif isinstance(b, V.Grafico):
            st.plotly_chart(b.fig, theme=None, width='stretch', config={'displaylogo': False})
        elif isinstance(b, V.Pannello):
            with pannello():
                if b.titolo:
                    st.markdown(tema.rd(tema.panel_head(b.titolo, b.sottotitolo)), unsafe_allow_html=True)
                rendi(b.blocchi)
                if b.nota:
                    st.markdown(tema.rd(tema.nota(b.nota)), unsafe_allow_html=True)
        elif isinstance(b, V.Colonne):
            for col, contenuto in zip(st.columns(b.pesi or len(b.colonne), gap="medium"), b.colonne):
                with col:
                    rendi(contenuto)
        elif isinstance(b, V.Dettagli):
            with st.expander(b.titolo, expanded=b.aperto):
                rendi(b.blocchi)
        elif isinstance(b, V.Tabella):
            st.dataframe(b.df.rename(columns=b.etichette), hide_index=True, width='stretch',
                         column_config=_column_config(b.formati, b.etichette))
        elif isinstance(b, V.Grafo):
            components.html(b.html, height=b.altezza)
        elif isinstance(b, V.Selettore):
            if b.opzioni:
                scelta = st.selectbox(b.etichetta, options=list(b.opzioni), key=b.chiave)
                rendi(b.opzioni[scelta])


def filtri_pannello():
    """Pannello bianco che ospita i widget di filtro (nell'export: riepilogo)."""
    c = pannello()
    c.markdown(tema.rd(tema.panel_head('Filtri')), unsafe_allow_html=True)
    return c


def strumenti_operatore(chiave: str):
    """Contenitore degli strumenti operatore: bordo tratteggiato, non esportati."""
    return st.container(key=f"operatore_{chiave}")


# --- MASTHEAD E SCHEDE -----------------------------------------------------------
aggiornamento = dati.data_aggiornamento()
stamp = f"Dati al {aggiornamento:%d/%m/%Y %H:%M}" if aggiornamento else "Dati non disponibili"
rendi([V.masthead(df_master, stamp)])

(tab_home, tab_ong, tab_geo, tab_network, tab_posizionamento,
 tab_tempo, tab_topic, tab_metodo) = st.tabs([etichetta for _, etichetta in tema.SCHEDE])

# ==========================================
# 1. PANORAMICA (HOME RADAR)
# ==========================================
with tab_home:
    rendi([V.testata_home()])

    with filtri_pannello():
        # Categoria-macro: separa i fatti (atti ufficiali) dall'opinione (blog).
        categorie_disponibili = sorted(df_master['categoria'].dropna().unique())
        categorie_selezionate = st.multiselect(
            "Categoria fonte — Ufficiale (fatti) · Stampa · Blog/Opinione · Società civile",
            options=categorie_disponibili, default=categorie_disponibili,
            help="Filtra per natura della fonte: distingue gli atti ufficiali da stampa e opinioni.")
        col_f1, col_f2, col_f3, col_f4 = st.columns(4)
        with col_f1:
            fonti_selezionate = st.multiselect("Fonte", options=df_master['fonte'].unique(),
                                               default=df_master['fonte'].unique())
        with col_f2:
            aree_selezionate = st.multiselect("Area geografica", options=df_master['ambito_geografico'].unique(),
                                              default=df_master['ambito_geografico'].unique())
        with col_f3:
            livello_allarme = st.slider("Livello allarme minimo", min_value=1, max_value=3, value=1)
        with col_f4:
            intervallo_giorni = st.selectbox("Intervallo temporale", options=dati.INTERVALLI_HOME,
                                             index=dati.INTERVALLO_HOME_DEFAULT, format_func=lambda x: x[0])

    df_filtrato = dati.filtra_master(df_master, intervallo_giorni[1], categorie_selezionate,
                                     fonti_selezionate, aree_selezionate, livello_allarme)
    rendi(V.vista_home(df_filtrato, carica_dati_raw_per_fonte()))

    # === SISTEMA HUMAN-IN-THE-LOOP ===
    with strumenti_operatore('home'):
        with st.expander("Strumenti operatore · Correggi classificazione (active learning)"):
            col_filtro_gold1, col_filtro_gold2 = st.columns(2)
            with col_filtro_gold1:
                fonte_filtro = st.selectbox("Filtra per fonte:",
                                            options=["Tutte le fonti"] + list(df_unificato['fonte'].unique()))
            with col_filtro_gold2:
                st.checkbox("Mostra solo notizie non ancora corrette", value=False)

            df_gold = df_master.copy()
            if fonte_filtro != "Tutte le fonti":
                df_gold = df_gold[df_gold['fonte'] == fonte_filtro]

            CATEGORIE_GEOGRAFICHE = ["Italia", "Europa", "USA / Internazionale", "Asia", "Generico"]
            ong_lista = list(PROFILI_ONG.keys())

            df_correzione = df_gold[['data', 'fonte', 'titolo', 'ambito_geografico', 'livello_allarme']].copy()
            df_correzione['errore_segnalato'] = False
            df_correzione['categoria_corretta'] = "Non modificato"
            df_correzione['livello_allarme_corretto'] = df_correzione['livello_allarme']
            df_correzione['ong_collegata_corretta'] = ""

            df_modificato = st.data_editor(
                df_correzione,
                column_config={
                    "data": st.column_config.DateColumn("Data", disabled=True, format="DD/MM/YYYY"),
                    "fonte": st.column_config.TextColumn("Fonte", disabled=True),
                    "titolo": st.column_config.TextColumn("Titolo", disabled=True, width="large"),
                    "ambito_geografico": st.column_config.TextColumn("Classificazione AI", disabled=True),
                    "errore_segnalato": st.column_config.CheckboxColumn("Segnala errore"),
                    "categoria_corretta": st.column_config.SelectboxColumn("Categoria corretta",
                                                                           options=CATEGORIE_GEOGRAFICHE),
                    "livello_allarme": st.column_config.NumberColumn("Livello AI", disabled=True,
                                                                     min_value=1, max_value=5),
                    "livello_allarme_corretto": st.column_config.NumberColumn(
                        "Livello allarme reale",
                        help="Modifica per assegnare l'importanza vera di questa notizia. 1 = Bassa, 5 = Molto Alta",
                        min_value=1, max_value=5, step=1),
                    "ong_collegata_corretta": st.column_config.SelectboxColumn(
                        "ONG associata", options=ong_lista,
                        help="Assegna manualmente quale ONG è citata in questa notizia"),
                },
                hide_index=True, width='stretch',
                disabled=["data", "fonte", "titolo", "ambito_geografico"],
            )

            if st.button("Salva correzioni", type="primary"):
                modifiche = df_modificato[df_modificato['errore_segnalato'] == True].copy()  # noqa: E712
                if len(modifiche) > 0:
                    modifiche['timestamp_correzione'] = datetime.now().isoformat()
                    modifiche['utente'] = "Operatore"
                    modifiche['tipo_correzione'] = "classificazione"
                    # Append allineato allo schema canonico (utils/feedback_schema.py)
                    append_correzioni(modifiche, dati.PERCORSO_FEEDBACK)
                    st.success(f"Salvate {len(modifiche)} correzioni. Saranno usate per il prossimo "
                               "fine-tuning del modello.")
                else:
                    st.info("Nessuna modifica selezionata per il salvataggio.")

# ==========================================
# 2. CAMPAGNE ONG
# ==========================================
with tab_ong:
    rendi([V.testata_ong()])
    ong_con_documenti = set(df_ong['nome_organizzazione'].unique()) if not df_ong.empty else set()
    rendi(V.avviso_ong_mancanti(sorted(set(PROFILI_ONG.keys()) - ong_con_documenti)))

    if df_ong.empty:
        ong_selezionate = []
    else:
        with filtri_pannello():
            ong_selezionate = st.multiselect("Organizzazioni", options=df_ong['nome_organizzazione'].unique(),
                                             default=df_ong['nome_organizzazione'].unique())
    df_ong_vista = dati.ong_come_unificato(df_ong[df_ong['nome_organizzazione'].isin(ong_selezionate)]
                                           if not df_ong.empty else df_ong)
    rendi(V.vista_ong(df_ong_vista, len(ong_selezionate)))

    with strumenti_operatore('ong'):
        with st.expander("Strumenti operatore · Aggiungi un documento manualmente"):
            with st.form("aggiungi_documento_ong", clear_on_submit=True):
                ong_form = st.selectbox("Organizzazione *", options=sorted(PROFILI_ONG.keys()),
                                        key="ong_manuale_select")
                titolo_form = st.text_input("Titolo *")
                testo_form = st.text_area("Testo *", height=150)
                data_form = st.date_input("Data *", value=datetime.now().date())
                url_form = st.text_input("Link *")
                if st.form_submit_button("Salva documento"):
                    errori_form = []
                    if not titolo_form.strip():
                        errori_form.append("titolo")
                    if not testo_form.strip():
                        errori_form.append("testo")
                    if not url_form.strip().lower().startswith("http"):
                        errori_form.append("link (deve iniziare con http)")
                    if errori_form:
                        st.error(f"Campi mancanti o non validi: {', '.join(errori_form)}")
                    else:
                        salva_documento_manuale(ong_form, titolo_form, testo_form, data_form, url_form)
                        st.success(f"Documento aggiunto per '{ong_form}'.")
                        carica_dati_ong.clear()
                        st.rerun()

# ==========================================
# 3. GEOGRAFIA (tutte le fonti)
# ==========================================
with tab_geo:
    rendi([V.testata_geo()])
    ordine_tipi = df_master['tipo'].value_counts().index.tolist()
    with filtri_pannello():
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            filtro_tipo = st.multiselect("Tipo di contenuto", options=ordine_tipi, default=ordine_tipi)
        with col_f2:
            filtro_area = st.selectbox("Area geografica", ["Tutte le aree"] + V.AREE)
    df_geo = df_master[df_master['tipo'].isin(filtro_tipo)]
    if filtro_area != "Tutte le aree":
        df_geo = df_geo[df_geo['ambito_geografico'] == filtro_area]
    rendi(V.vista_geo(df_geo, ordine_tipi))

# ==========================================
# 4. NETWORK ONG <-> TEMI
# ==========================================
with tab_network:
    rendi([V.testata_network()])
    profilo_keywords_ong = carica_profilo_keywords_ong()
    if df_ong.empty:
        rendi([V.Html(tema.rd(tema.callout('Nessun dato ONG disponibile per costruire il network.', 'warn')))])
    else:
        html_grafo, stats = grafo_network(df_ong, profilo_keywords_ong, dati.correzioni_ong_manuali())
        rendi(V.vista_network(html_grafo, stats))

    with strumenti_operatore('network'):
        with st.expander("Strumenti operatore · Profilo parole chiave ONG"):
            st.markdown("Parole chiave aggiuntive, specifiche per ONG, usate solo per collegare le notizie "
                        "all'ONG più pertinente in questo grafo — si sommano al `focus` già definito, "
                        "non lo sostituiscono.")
            ong_scelta_profilo = st.selectbox("Organizzazione", options=sorted(PROFILI_ONG.keys()),
                                              key="ong_profilo_select")
            testo_keywords = st.text_area("Parole chiave (una per riga)",
                                          value="\n".join(profilo_keywords_ong.get(ong_scelta_profilo, [])),
                                          key="ong_profilo_textarea", height=120)
            if st.button("Salva profilo", key="salva_profilo_ong"):
                nuove_parole = [r.strip() for r in testo_keywords.split("\n") if r.strip()]
                salva_profilo_keywords_ong(ong_scelta_profilo, nuove_parole)
                st.success(f"Profilo di '{ong_scelta_profilo}' aggiornato: {len(nuove_parole)} parole chiave.")
                st.rerun()

        if not df_ong.empty:
            with st.expander("Strumenti operatore · Correggi associazioni notizie → ONG"):
                st.markdown("Se una notizia è associata alla ONG sbagliata puoi correggere l'associazione qui.")
                df_correzione_network = df_ong[['data_pubblicazione', 'nome_organizzazione', 'titolo', 'url']].head(50).copy()
                df_correzione_network['associazione_corretta'] = df_correzione_network['nome_organizzazione']
                df_modificato_network = st.data_editor(
                    df_correzione_network,
                    column_config={
                        "nome_organizzazione": st.column_config.TextColumn("Associazione attuale", disabled=True),
                        "associazione_corretta": st.column_config.SelectboxColumn(
                            "Associazione corretta", options=list(PROFILI_ONG.keys())),
                        "titolo": st.column_config.TextColumn("Titolo notizia", disabled=True, width="large"),
                        "url": st.column_config.TextColumn("Link", disabled=True),
                    },
                    hide_index=True, width='stretch')
                if st.button("Salva correzioni associazioni", type="primary"):
                    modifiche_network = df_modificato_network[
                        df_modificato_network['associazione_corretta'] != df_modificato_network['nome_organizzazione']
                    ].copy()
                    if len(modifiche_network) > 0:
                        # Stesso schema/percorso del "Correggi classificazione" della Panoramica.
                        modifiche_feedback = pd.DataFrame({
                            'data': modifiche_network['data_pubblicazione'],
                            'fonte': modifiche_network['nome_organizzazione'],
                            'titolo': modifiche_network['titolo'],
                            'errore_segnalato': True,
                            'ong_collegata_corretta': modifiche_network['associazione_corretta'],
                            'timestamp_correzione': datetime.now().isoformat(),
                            'utente': "Operatore",
                            'tipo_correzione': "ong_collegata",
                        })
                        append_correzioni(modifiche_feedback, dati.PERCORSO_FEEDBACK)
                        grafo_network.clear()
                        st.success(f"Salvate {len(modifiche_network)} correzioni in training_data_feedback.csv.")
                    else:
                        st.info("Nessuna modifica effettuata")

# ==========================================
# 5. MAPPA DI POSIZIONAMENTO
# ==========================================
with tab_posizionamento:
    rendi([V.testata_posizionamento()])
    if df_ong.empty:
        rendi([V.Html(tema.rd(tema.callout('Nessun dato ONG disponibile.', 'warn')))])
    else:
        # salva=True: aggiorna ong_posizioni_permanenti.csv (come prima del refactor)
        df_notizie_pos, centroidi_ong = dati.prepara_posizionamento(df_ong, salva=True)
        rendi(V.vista_posizionamento(df_notizie_pos, centroidi_ong))

# ==========================================
# 6. ANALISI TEMPORALE
# ==========================================
with tab_tempo:
    rendi([V.testata_tempo()])
    df_temporale = carica_dati_per_analisi_temporale()
    if df_temporale.empty:
        rendi([V.Html(tema.rd(tema.callout(
            'Nessun dato temporale disponibile. Verifica che gli scraper abbiano prodotto i CSV analizzati '
            'in <code>data/processed/</code>.', 'warn')))])
    else:
        with filtri_pannello():
            scelta_intervallo = st.selectbox("Periodo di analisi", options=dati.INTERVALLI_TEMPO,
                                             format_func=lambda x: x[0], index=0)
        df_periodo = dati.filtra_periodo(df_temporale, scelta_intervallo[1])
        ordine_fonti = df_temporale['fonte'].value_counts().index.tolist()
        rendi(V.vista_tempo_a(df_periodo, ordine_fonti, dati.sanzioni_mensili(df_periodo)))

        reg_temi = carica_registro()
        reg_attivi = reg_temi[reg_temi['stato'] == 'attivo']
        with filtri_pannello():
            livello = st.radio("Livello dei temi", dati.LIVELLI_TEMI, horizontal=True, key="livello_temi_trend",
                               help="I macro-temi includono anche i documenti dei loro sotto-temi.")
        df_kw = dati.conteggio_temi_mensile(df_periodo, dati.temi_ammessi(livello, reg_temi))
        rendi(V.vista_tempo_b(df_kw, livello, reg_attivi[reg_attivi['padre'] != '']))

# ==========================================
# 7. TOPIC EMERGENTI + GESTIONE SOTTO-TEMI
# ==========================================
ETICHETTE_VALUTAZIONE_TOPIC = {
    'coperto': 'già coperto', 'candidato_sottotema': 'candidato sotto-tema', 'fuori_lessico': 'fuori lessico',
}

with tab_topic:
    rendi([V.testata_topic()])
    df_topic, df_trend = carica_topic_emergenti()
    rendi(V.vista_topic(df_topic, df_trend))

    if not df_topic.empty and not df_trend.empty:
        etichetta = V.etichette_topic(df_topic)
        with filtri_pannello():
            scelti = st.multiselect(
                "Topic da confrontare (massimo 8)", options=sorted(etichetta.keys()),
                default=df_topic.nlargest(5, 'dimensione')['topic_id'].astype(int).tolist(),
                format_func=lambda t: etichetta.get(t, f"#{t}"), max_selections=8)
        rendi(V.vista_topic_trend(df_topic, df_trend, scelti))

    registro = carica_registro()
    rendi(V.vista_registro(registro))

    # Ciclo: BERTopic SCOPRE -> l'operatore APPROVA qui -> il matcher TRACCIA.
    # I macro-temi restano fissi; qui si gestiscono solo i sotto-temi. Nessuna
    # cancellazione: un sotto-tema si "dismette" (stato) e la sua storia resta.
    if msg := st.session_state.pop('msg_registro_temi', None):
        st.success(msg)

    macro_attivi = registro[(registro['padre'] == '') & (registro['stato'] == 'attivo')]['tema'].tolist()

    def _salva_registro(df_nuovo: pd.DataFrame, messaggio: str) -> None:
        """Salva via nlp.theme_matching (validazione + backup) e ricarica la vista."""
        try:
            backup = salva_registro_temi(df_nuovo)
        except ValueError as err:
            st.error("Registro non salvato, correggi questi punti:\n\n" +
                     "\n".join(f"- {e}" for e in str(err).splitlines()))
            return
        carica_registro.clear()
        carica_temi.clear()
        st.session_state['msg_registro_temi'] = (
            messaggio + (f" Backup della versione precedente: `{os.path.basename(backup)}`." if backup else "")
            + " Rilancia `python nlp/text_analysis.py` per applicarlo ai documenti.")
        st.rerun()

    with strumenti_operatore('topic'):
        with st.expander("Strumenti operatore · Nuovo sotto-tema", expanded=False):
            st.caption("Le modifiche vengono salvate in `data/utils/temi.csv` (con backup) e si applicano al "
                       "prossimo `python nlp/text_analysis.py`, retroattivamente su tutto lo storico.")
            opzioni_topic = [None]
            if not df_topic.empty:
                ordine = {'fuori_lessico': 0, 'candidato_sottotema': 1, 'coperto': 2}
                df_ord = df_topic.copy()
                if 'valutazione' in df_ord.columns:
                    df_ord = df_ord.assign(_o=df_ord['valutazione'].map(ordine).fillna(3)) \
                                   .sort_values(['_o', 'dimensione'], ascending=[True, False])
                opzioni_topic += df_ord['topic_id'].astype(int).tolist()
            righe_topic = {int(r['topic_id']): r for _, r in df_topic.iterrows()} if not df_topic.empty else {}

            def _etichetta_topic(tid):
                if tid is None:
                    return "— Manuale (nessun topic) —"
                r = righe_topic[tid]
                val = ETICHETTE_VALUTAZIONE_TOPIC.get(r.get('valutazione'), '')
                return f"#{tid} · {', '.join(str(r['parole_chiave']).split(', ')[:3])} · {val}"

            tid = st.selectbox("Parti da un topic scoperto", opzioni_topic,
                               format_func=_etichetta_topic, key="nuovo_sottotema_topic")
            sorgente = righe_topic.get(tid)
            parole = str(sorgente['parole_chiave']).split(', ') if sorgente is not None else []
            if sorgente is not None:
                st.caption(f"Titoli d'esempio: {sorgente['titoli_esempio']}")
                if sorgente.get('valutazione') == 'coperto':
                    st.warning(f"Questo topic è già coperto dal sotto-tema «{sorgente.get('sottotema_esistente')}».")

            padre_default = sorgente.get('padre_proposto') if sorgente is not None else None
            with st.form(f"form_sottotema_{tid}"):
                nome = st.text_input("Nome del sotto-tema", value=' '.join(parole[:2]).title() if parole else '')
                padre = st.selectbox("Macro-tema padre", macro_attivi,
                                     index=macro_attivi.index(padre_default) if padre_default in macro_attivi else 0)
                termini = st.text_area(
                    "Termini-seme (uno per riga)", value='\n'.join(parole),
                    help="Un documento ha il sotto-tema se contiene uno di questi termini (match esatto) o se gli "
                         "è semanticamente vicino. Le parole di BERTopic sono solo un punto di partenza: tieni "
                         "quelle specifiche, togli quelle generiche. Minimo 3 caratteri; una radice come "
                         "'sorveglian' copre più desinenze.")
                soglia = st.slider("Soglia semantica", 0.30, 1.0, SOGLIA_SOTTOTEMA, 0.01,
                                   help="Più alta = più preciso, meno documenti. 1.0 = solo match esatto dei termini.")
                stato = st.radio("Stato", ['attivo', 'candidato'], horizontal=True,
                                 help="'candidato' lo salva nel registro senza ancora rilevarlo.")
                if st.form_submit_button("Aggiungi sotto-tema", type="primary"):
                    origine = f"bertopic#{tid}: {', '.join(parole[:3])}" if sorgente is not None else 'manuale'
                    nuova = pd.DataFrame([{
                        'tema': nome.strip(), 'termini': '|'.join(termini.splitlines()),
                        'soglia': soglia, 'padre': padre, 'stato': stato,
                        'dal': datetime.now().strftime('%Y-%m-%d'), 'origine': origine,
                    }])
                    _salva_registro(pd.concat([registro, nuova], ignore_index=True),
                                    f"Sotto-tema «{nome.strip()}» aggiunto a «{padre}».")

        sotto = registro[registro['padre'] != ''].copy()
        if not sotto.empty:
            with st.expander("Strumenti operatore · Modifica sotto-temi"):
                st.caption("Modifica direttamente nella tabella. Per ritirare un sotto-tema imposta lo stato su "
                           "**dismesso**: smette di essere rilevato ma resta nel registro.")
                sotto_mod = st.data_editor(
                    sotto,
                    column_config={
                        'tema': st.column_config.TextColumn("Sotto-tema", required=True),
                        'termini': st.column_config.TextColumn("Termini (separati da |)", width="large", required=True),
                        'soglia': st.column_config.NumberColumn("Soglia", min_value=0.30, max_value=1.0,
                                                                step=0.01, format="%.2f"),
                        'padre': st.column_config.SelectboxColumn("Macro-tema", options=macro_attivi, required=True),
                        'stato': st.column_config.SelectboxColumn("Stato", options=list(STATI_TEMA), required=True),
                        'dal': st.column_config.TextColumn("Dal", disabled=True),
                        'origine': st.column_config.TextColumn("Origine", disabled=True),
                    },
                    hide_index=True, width='stretch', num_rows="fixed", key="editor_sottotemi")
                if st.button("Salva modifiche ai sotto-temi", type="primary"):
                    if sotto_mod.reset_index(drop=True).equals(sotto.reset_index(drop=True)):
                        st.info("Nessuna modifica da salvare.")
                    else:
                        _salva_registro(pd.concat([registro[registro['padre'] == ''], sotto_mod], ignore_index=True),
                                        "Sotto-temi aggiornati.")

# ==========================================
# 8. NOTE DI METODO
# ==========================================
with tab_metodo:
    rendi(V.vista_metodo(df_master, stamp, statico=False))
