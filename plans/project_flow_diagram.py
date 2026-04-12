import streamlit as st

def display_project_flow_diagram():
    st.markdown("""
    ```mermaid
    graph TD
        subgraph Data_Sources ["Data Sources"]
            A[GNews API] --> S_GNews(scraper_gnews.py)
            B[Garante Privacy Website] --> S_GPDP(scraper_gpdp.py)
            C[ONG RSS Feeds] --> S_ONG(scraper_ong.py)
            D[EU Institutional RSS Feeds] --> S_RSS_EU(scraper_rss_eu.py)
        end

        subgraph Scrapers ["Scrapers"]
            S_GNews --> DR_GNews(data/raw/gnews_sample.csv)
            S_GPDP --> DR_GPDP(data/raw/gpdp_sample.csv)
            S_ONG --> DR_ONG(data/raw/ong_sample.csv)
            S_RSS_EU --> DR_RSS_EU(data/raw/rss_eu_sample.csv)
        end

        subgraph NLP_Processing ["NLP Processing"]
            DR_GPDP --> NLP_Text(nlp/text_analysis.py)
            NLP_Text -->|Entita, Geografia| DP_GPDP(data/processed/gpdp_analyzed.csv)
        end

        subgraph Dashboard ["Dashboard"]
            DR_ONG --> D_App(app/dashboard.py)
            DP_GPDP --> D_App
            D_App -->|Streamlit Interface| User(End User)
        end

        style A fill:#f9f,stroke:#333,stroke-width:2px
        style B fill:#f9f,stroke:#333,stroke-width:2px
        style C fill:#f9f,stroke:#333,stroke-width:2px
        style D fill:#f9f,stroke:#333,stroke-width:2px
        style S_GNews fill:#ccf,stroke:#333,stroke-width:2px
        style S_GPDP fill:#ccf,stroke:#333,stroke-width:2px
        style S_ONG fill:#ccf,stroke:#333,stroke-width:2px
        style S_RSS_EU fill:#ccf,stroke:#333,stroke-width:2px
        style DR_GNews fill:#cff,stroke:#333,stroke-width:2px
        style DR_GPDP fill:#cff,stroke:#333,stroke-width:2px
        style DR_ONG fill:#cff,stroke:#333,stroke-width:2px
        style DR_RSS_EU fill:#cff,stroke:#333,stroke-width:2px
        style NLP_Text fill:#cfc,stroke:#333,stroke-width:2px
        style DP_GPDP fill:#cff,stroke:#333,stroke-width:2px
        style D_App fill:#fcc,stroke:#333,stroke-width:2px
        style User fill:#afa,stroke:#333,stroke-width:2px
    ```
    """)

if __name__ == "__main__":
    st.set_page_config(page_title="Project Flow Diagram", layout="wide")
    st.title("Diagramma di Flusso del Progetto")
    display_project_flow_diagram()