from google.oauth2.service_account import Credentials
import gspread
import pandas as pd
import streamlit as st

# ==========================================
# 0. CONFIGURAZIONE PAGINA (MOBILE CENTERED)
# ==========================================
st.set_page_config(
    page_title="Contabilità - Spesa e Mesi", page_icon="🛒", layout="centered"
)

# ID del tuo Google Sheet principale
SHEET_ID = "1Ka7EbFA8aeCHfZb_YTWMjDT3Z7n8a9JUPUUqhIEC068"
LOGIN_GID = "2140068884"

# Mappatura delle sezioni con i rispettivi GID dei fogli
SECTIONS_GIDS = {
    "Lista della spesa": "1311166810",
    "Gennaio": "620769078",
    "Febbraio": "1488371451",
    "Marzo": "42697191",
    "Aprile": "1104467997",
    "Maggio": "703608499",
    "Giugno": "1346342417",
    "Luglio": "2042094472",
    "Agosto": "913928488",
    "Settembre": "1936940915",
    "Ottobre": "1095046403",
    "Novembre": "757892738",
    "Dicembre": "1354075837",
}


# ==========================================
# 1. FUNZIONI HELPER GOOGLE SHEETS (CON CACHE)
# ==========================================
@st.cache_resource
def ottieni_credenziali():
    try:
        creds_dict = dict(st.secrets["gcp_service_account"])
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ]
        return Credentials.from_service_account_info(
            creds_dict, scopes=scopes
        )
    except Exception as e:
        st.error(f"Errore caricamento credenziali da secrets: {e}")
        return None


@st.cache_data(ttl=60)
def verifica_credenziali_da_foglio(user_inserito, pass_inserita):
    try:
        creds = ottieni_credenziali()
        if not creds:
            return False
        client = gspread.authorize(creds)
        spreadsheet = client.open_by_key(SHEET_ID)

        worksheet = next(
            (
                ws
                for ws in spreadsheet.worksheets()
                if str(ws.id).strip() == str(LOGIN_GID).strip()
            ),
            None,
        )
        if not worksheet:
            worksheet = spreadsheet.get_worksheet(0)

        user_corretto = worksheet.cell(3, 2).value
        pass_corretta = worksheet.cell(4, 2).value

        if (
            user_inserito.strip() == str(user_corretto).strip()
            and pass_inserita.strip() == str(pass_corretta).strip()
        ):
            return True
        return False
    except Exception as e:
        st.error(f"Errore di connessione al foglio credenziali: {e}")
        return False


def apri_foglio_sezione(nome_sezione):
    creds = ottieni_credenziali()
    if not creds:
        return None
    client = gspread.authorize(creds)
    spreadsheet = client.open_by_key(SHEET_ID)

    target_gid = SECTIONS_GIDS.get(nome_sezione, "")
    worksheet = None
    if target_gid:
        worksheet = next(
            (
                ws
                for ws in spreadsheet.worksheets()
                if str(ws.id).strip() == str(target_gid).strip()
            ),
            None,
        )
    if not worksheet:
        worksheet = spreadsheet.worksheet(nome_sezione)
    return worksheet


# ==========================================
# 2. GESTIONE LOGIN PERSISTENTE
# ==========================================
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    st.markdown("<h1 style='text-align: center;'>Contabilità</h1>", unsafe_allow_html=True)
    try:
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.image("logo.jpg", use_container_width=True)
    except Exception:
        pass

    st.markdown("### 🔐 Accesso Riservato")
    username_input = st.text_input("Username")
    password_input = st.text_input("Password", type="password")

    if st.button("Accedi", use_container_width=True):
        if verifica_credenziali_da_foglio(username_input, password_input):
            st.session_state.logged_in = True
            st.rerun()
        else:
            st.error("Credenziali non valide.")
    st.stop()


# ==========================================
# 3. FUNZIONI FORMATTAZIONE E DATI FOGLI
# ==========================================
def formatta_valuta_lettura(valore):
    if valore is None:
        return ""
    val_str = str(valore).strip()
    if val_str in ["", "nan", "None", "<NA>", "€ 0,00", "0"]:
        return ""
    
    val_pulito = val_str.replace("€", "").replace(" ", "")
    if "," in val_pulito and "." in val_pulito:
        val_pulito = val_pulito.replace(".", "").replace(",", ".")
    elif "," in val_pulito:
        val_pulito = val_pulito.replace(",", ".")
        
    try:
        num = float(val_pulito)
        return f"€ {num:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except ValueError:
        return val_str


def pulisci_e_converti_importo(valore):
    if valore is None:
        return ""
    val_str = str(valore).strip()
    if val_str in ["", "nan", "None", "<NA>"]:
        return ""
    val_str = val_str.replace("€", "").replace(" ", "")
    if "," in val_str and "." in val_str:
        val_str = val_str.replace(".", "").replace(",", ".")
    elif "," in val_str:
        val_str = val_str.replace(",", ".")
    try:
        return float(val_str)
    except ValueError:
        return val_str


def carica_dati_foglio(nome_sezione):
    try:
        worksheet = apri_foglio_sezione(nome_sezione)
        if not worksheet:
            return nome_sezione, pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

        if nome_sezione != "Lista della spesa":
            titolo_cella = worksheet.cell(1, 1).value
            titolo_pagina = titolo_cella if titolo_cella and titolo_cella.strip() != "" else nome_sezione
            intestazioni_fisse = ["Categoria", "Descrizione", "Importo"]

            tutti_i_valori = worksheet.get("A1:I33")

            def estrai_righe(start_riga, end_riga, num_righe_default):
                righe = []
                for r_idx in range(start_riga - 1, min(end_riga, len(tutti_i_valori))):
                    row = tutti_i_valori[r_idx] if r_idx < len(tutti_i_valori) else []
                    while len(row) < 3:
                        row.append("")
                    row[2] = formatta_valuta_lettura(row[2])
                    righe.append(row[:3])

                while len(righe) < num_righe_default:
                    righe.append(["", "", ""])
                return pd.DataFrame(righe, columns=intestazioni_fisse)

            # 1. Entrate (A5:C8)
            df_entrate = estrai_righe(5, 8, 4)
            # 2. Spese Fisse (A13:C16)
            df_spese_fisse = estrai_righe(13, 16, 4)
            # 3. Spese Variabili (A20:C25)
            df_spese_variabili = estrai_righe(20, 25, 6)
            # 4. Debiti (A30:C33)
            df_debiti = estrai_righe(30, 33, 4)

            # 5. Riepilogo (H5:I11)
            righe_riepilogo = []
            for r_idx in range(4, 11):
                row = tutti_i_valori[r_idx] if r_idx < len(tutti_i_valori) else []
                val_h = row[7] if len(row) > 7 else ""
                val_i = row[8] if len(row) > 8 else ""
                val_i = formatta_valuta_lettura(val_i)
                righe_riepilogo.append([val_h, val_i])
            
            while len(righe_riepilogo) < 7:
                righe_riepilogo.append(["", ""])
            
            df_riepilogo = pd.DataFrame(righe_riepilogo, columns=["Voce", "Importo"])

            return titolo_pagina, df_entrate, df_spese_fisse, df_spese_variabili, df_debiti, df_riepilogo

        # CASO LISTA DELLA SPESA
        dati_grezzi = worksheet.get_all_values()
        if not dati_grezzi:
            return nome_sezione, pd.DataFrame(), None, None, None, None

        df = pd.DataFrame(dati_grezzi)
        start_row = 4
        end_row = min(150, len(df))
        end_col = min(4, df.shape[1])

        if len(df) > start_row:
            df_subset = df.iloc[start_row:end_row, 0:end_col].copy()
            df_subset.columns = df_subset.iloc[0]
            df_subset = df_subset.drop(df_subset.index[0]).reset_index(drop=True)

            for col in df_subset.columns:
                if df_subset[col].astype(str).str.lower().isin(["true", "false", "1", "0", "vero", "falso"]).all():
                    df_subset[col] = df_subset[col].astype(str).str.lower().isin(["true", "1", "vero"])

            return nome_sezione, df_subset, None, None, None, None
        else:
            return nome_sezione, pd.DataFrame(), None, None, None, None
    except Exception as e:
        st.warning(f"Impossibile leggere il foglio per '{nome_sezione}': {e}")
        return nome_sezione, None, None, None, None, None


def pulisci_df_per_salvataggio(df):
    cleaned_df = df.copy()
    cleaned_df = cleaned_df.fillna("")
    for col in cleaned_df.columns:
        if "importo" in col.lower() or "prezzo" in col.lower() or "costo" in col.lower():
            cleaned_df[col] = cleaned_df[col].apply(pulisci_e_converti_importo)
        else:
            cleaned_df[col] = cleaned_df[col].astype(str).replace(["nan", "None", "<NA>"], "")
    return cleaned_df


# Funzioni di salvataggio singole
def salva_entrate(nome_sezione, df_entrate_edit):
    try:
        worksheet = apri_foglio_sezione(nome_sezione)
        if not worksheet: return False
        intestazioni_fisse = ["Categoria", "Descrizione", "Importo"]
        
        df_pulito = pulisci_df_per_salvataggio(df_entrate_edit)
        data_entrate = df_pulito.values.tolist()
        
        worksheet.update("A4:C4", [intestazioni_fisse])
        worksheet.update("A5:C8", data_entrate)
        return True
    except Exception as e:
        st.error(f"Errore salvataggio Entrate: {e}")
        return False

def salva_spese_fisse(nome_sezione, df_spese_edit):
    try:
        worksheet = apri_foglio_sezione(nome_sezione)
        if not worksheet: return False
        intestazioni_fisse = ["Categoria", "Descrizione", "Importo"]
        
        df_pulito = pulisci_df_per_salvataggio(df_spese_edit)
        data_spese = df_pulito.values.tolist()
        
        worksheet.update("A12:C12", [intestazioni_fisse])
        worksheet.update("A13:C16", data_spese)
        return True
    except Exception as e:
        st.error(f"Errore salvataggio Spese Fisse: {e}")
        return False

def salva_spese_variabili(nome_sezione, df_var_edit):
    try:
        worksheet = apri_foglio_sezione(nome_sezione)
        if not worksheet: return False
        intestazioni_fisse = ["Categoria", "Descrizione", "Importo"]
        
        df_pulito = pulisci_df_per_salvataggio(df_var_edit)
        data_var = df_pulito.values.tolist()
        
        worksheet.update("A19:C19", [intestazioni_fisse])
        worksheet.update("A20:C25", data_var)
        return True
    except Exception as e:
        st.error(f"Errore salvataggio Spese Variabili: {e}")
        return False

def salva_debiti(nome_sezione, df_debiti_edit):
    try:
        worksheet = apri_foglio_sezione(nome_sezione)
        if not worksheet: return False
        intestazioni_fisse = ["Categoria", "Descrizione", "Importo"]
        
        df_pulito = pulisci_df_per_salvataggio(df_debiti_edit)
        data_debiti = df_pulito.values.tolist()
        
        worksheet.update("A29:C29", [intestazioni_fisse])
        worksheet.update("A30:C33", data_debiti)
        return True
    except Exception as e:
        st.error(f"Errore salvataggio Debiti: {e}")
        return False

def salva_lista_spesa(nome_sezione, edited_df, totale_spesa):
    try:
        worksheet = apri_foglio_sezione(nome_sezione)
        if not worksheet: return False
        worksheet.update_acell("E5", totale_spesa)
        header = list(edited_df.columns)
        
        df_pulito = pulisci_df_per_salvataggio(edited_df)
        data_values = df_pulito.values.tolist()
        
        cell_list = [header] + data_values
        worksheet.update(f"A5:D{5 + len(cell_list)}", cell_list)
        return True
    except Exception as e:
        st.error(f"Errore durante il salvataggio: {e}")
        return False


# ==========================================
# 4. INTERFACCIA PRINCIPALE (LAYOUT CENTRATO MOBILE)
# ==========================================

st.markdown("<h1 style='text-align: center;'>Contabilità</h1>", unsafe_allow_html=True)

try:
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        st.image("logo.jpg", use_container_width=True)
except Exception:
    pass

st.markdown("---")

menu_options = list(SECTIONS_GIDS.keys())
selected_section = st.selectbox("📌 Seleziona Sezione:", menu_options)

st.markdown("---")

# Sezione Lista della spesa
if selected_section == "Lista della spesa":
    titolo_sezione, df_dati, _, _, _, _ = carica_dati_foglio(selected_section)
    st.subheader(f"📁 {titolo_sezione}")

    if df_dati is not None and not df_dati.empty:
        num_righe_visibili = max(10, min(len(df_dati), 10))
        edited_df = st.data_editor(
            df_dati,
            use_container_width=True,
            hide_index=True,
            height=num_righe_visibili * 35 + 40,
            key=f"editor_{selected_section}",
        )

        totale = 0.0
        colonna_importo = None
        for col in edited_df.columns:
            col_lower = str(col).lower()
            if any(k in col_lower for k in ["prezzo", "importo", "costo", "totale", "euro", "€"]):
                colonna_importo = col
                break
        
        if not colonna_importo and len(edited_df.columns) > 1:
            colonna_importo = edited_df.columns[-1]

        if colonna_importo:
            try:
                valori_numerici = pd.to_numeric(edited_df[colonna_importo].astype(str).str.replace('€', '').str.replace('.', '').str.replace(',', '.'), errors='coerce').fillna(0)
                totale = valori_numerici.sum()
            except Exception:
                totale = 0.0

        st.markdown(f"### 💶 Totale Spesa: **€ {totale:,.2f}**")

        if st.button("💾 Salva Modifiche", type="primary", use_container_width=True):
            if salva_lista_spesa(selected_section, edited_df, f"€ {totale:,.2f}"):
                st.success("Modifiche salvate con successo!")
                st.rerun()
    else:
        st.info("Nessun dato trovato o intervallo vuoto nel foglio selezionato.")

# Sezione Mesi (Gennaio, Febbraio, ecc.)
else:
    titolo_sezione, df_entrate, df_spese_fisse, df_spese_var, df_debiti, df_riepilogo = carica_dati_foglio(selected_section)
    st.markdown(f"<h2 style='text-align: center;'>📁 {titolo_sezione}</h2>", unsafe_allow_html=True)

    if df_entrate is not None and df_spese_fisse is not None and df_spese_var is not None and df_debiti is not None:
        col_bloc_entrate = [df_entrate.columns[0]] if len(df_entrate.columns) > 0 else []
        col_bloc_spese_fisse = [df_spese_fisse.columns[0]] if len(df_spese_fisse.columns) > 0 else []
        col_bloc_spese_var = [df_spese_var.columns[0]] if len(df_spese_var.columns) > 0 else []
        col_bloc_debiti = [df_debiti.columns[0]] if len(df_debiti.columns) > 0 else []

        # --- TABELLA ENTRATE ---
        st.markdown(
            """
            <div style="background-color: #f0f2f6; padding: 8px; border-radius: 5px; text-align: center; font-weight: bold; margin-bottom: 5px;">
                📈 ENTRATE
            </div>
            """,
            unsafe_allow_html=True
        )
        edited_entrate = st.data_editor(
            df_entrate,
            disabled=col_bloc_entrate,
            use_container_width=True,
            hide_index=True,
            height=len(df_entrate) * 35 + 40,
            key=f"editor_entrate_{selected_section}",
        )
        tot_entrate = 0.0
        try:
            val_ent = pd.to_numeric(edited_entrate['Importo'].astype(str).str.replace('€', '').str.replace('.', '').str.replace(',', '.'), errors='coerce').fillna(0)
            tot_entrate = val_ent.sum()
        except Exception:
            tot_entrate = 0.0
        st.markdown(f"**Totale Entrate:** € {tot_entrate:,.2f}")
        
        if st.button("💾 Salva Entrate", type="primary", use_container_width=True, key=f"btn_salva_entrate_{selected_section}"):
            if salva_entrate(selected_section, edited_entrate):
                st.success("Entrate salvate con successo!")
                st.rerun()

        st.markdown("---")

        # --- TABELLA SPESE FISSE ---
        st.markdown(
            """
            <div style="background-color: #f0f2f6; padding: 8px; border-radius: 5px; text-align: center; font-weight: bold; margin-bottom: 5px;">
                📉 SPESE FISSE
            </div>
            """,
            unsafe_allow_html=True
        )
        edited_spese_fisse = st.data_editor(
            df_spese_fisse,
            disabled=col_bloc_spese_fisse,
            use_container_width=True,
            hide_index=True,
            height=len(df_spese_fisse) * 35 + 40,
            key=f"editor_spese_fisse_{selected_section}",
        )
        tot_spese_fisse = 0.0
        try:
            val_spe_fisse = pd.to_numeric(edited_spese_fisse['Importo'].astype(str).str.replace('€', '').str.replace('.', '').str.replace(',', '.'), errors='coerce').fillna(0)
            tot_spese_fisse = val_spe_fisse.sum()
        except Exception:
            tot_spese_fisse = 0.0
        st.markdown(f"**Totale Spese Fisse:** € {tot_spese_fisse:,.2f}")

        if st.button("💾 Salva Spese Fisse", type="primary", use_container_width=True, key=f"btn_salva_fisse_{selected_section}"):
            if salva_spese_fisse(selected_section, edited_spese_fisse):
                st.success("Spese Fisse salvate con successo!")
                st.rerun()

        st.markdown("---")

        # --- TABELLA SPESE VARIABILI ---
        st.markdown(
            """
            <div style="background-color: #f0f2f6; padding: 8px; border-radius: 5px; text-align: center; font-weight: bold; margin-bottom: 5px;">
                📊 SPESE VARIABILI
            </div>
            """,
            unsafe_allow_html=True
        )
        edited_spese_var = st.data_editor(
            df_spese_var,
            disabled=col_bloc_spese_var,
            use_container_width=True,
            hide_index=True,
            height=len(df_spese_var) * 35 + 40,
            key=f"editor_spese_var_{selected_section}",
        )
        tot_spese_var = 0.0
        try:
            val_spe_var = pd.to_numeric(edited_spese_var['Importo'].astype(str).str.replace('€', '').str.replace('.', '').str.replace(',', '.'), errors='coerce').fillna(0)
            tot_spese_var = val_spe_var.sum()
        except Exception:
            tot_spese_var = 0.0
        st.markdown(f"**Totale Spese Variabili:** € {tot_spese_var:,.2f}")

        if st.button("💾 Salva Spese Variabili", type="primary", use_container_width=True, key=f"btn_salva_var_{selected_section}"):
            if salva_spese_variabili(selected_section, edited_spese_var):
                st.success("Spese Variabili salvate con successo!")
                st.rerun()

        st.markdown("---")

        # --- TABELLA DEBITI ---
        st.markdown(
            """
            <div style="background-color: #f0f2f6; padding: 8px; border-radius: 5px; text-align: center; font-weight: bold; margin-bottom: 5px;">
                💳 DEBITI
            </div>
            """,
            unsafe_allow_html=True
        )
        edited_debiti = st.data_editor(
            df_debiti,
            disabled=col_bloc_debiti,
            use_container_width=True,
            hide_index=True,
            height=len(df_debiti) * 35 + 40,
            key=f"editor_debiti_{selected_section}",
        )
        tot_debiti = 0.0
        try:
            val_deb = pd.to_numeric(edited_debiti['Importo'].astype(str).str.replace('€', '').str.replace('.', '').str.replace(',', '.'), errors='coerce').fillna(0)
            tot_debiti = val_deb.sum()
        except Exception:
            tot_debiti = 0.0
        st.markdown(f"**Totale Debiti:** € {tot_debiti:,.2f}")

        if st.button("💾 Salva Debiti", type="primary", use_container_width=True, key=f"btn_salva_debiti_{selected_section}"):
            if salva_debiti(selected_section, edited_debiti):
                st.success("Debiti salvati con successo!")
                st.rerun()

        st.markdown("---")

        # --- TABELLA RIEPILOGO (H5:I11 - SOLO LETTURA) ---
        st.markdown(
            """
            <div style="background-color: #f0f2f6; padding: 8px; border-radius: 5px; text-align: center; font-weight: bold; margin-bottom: 5px;">
                📋 RIEPILOGO
            </div>
            """,
            unsafe_allow_html=True
        )
        if df_riepilogo is not None and not df_riepilogo.empty:
            st.dataframe(
                df_riepilogo,
                use_container_width=True,
                hide_index=True,
                height=len(df_riepilogo) * 35 + 40,
            )

    else:
        st.info("Nessun dato trovato nel foglio selezionato.")

st.markdown("---")
if st.button("🚪 Logout", use_container_width=True):
    st.session_state.logged_in = False
    st.rerun()
