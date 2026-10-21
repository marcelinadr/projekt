import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import recurring_ical_events
import streamlit as st
from icalendar import Calendar

# pip install streamlit pandas icalendar recurring-ical-events tzdata

TZ = ZoneInfo("Europe/Warsaw")
PLIK_DANYCH = Path("dane.json")
METODY_PLATNOSCI = ["Przelew", "BLIK", "Gotówka"]
STATUSY = ["Odbyła się", "Nieobecność płatna", "Odwołana"]
STATUSY_PLATNE = {"Odbyła się", "Nieobecność płatna"}
MIESIACE = [
    "styczeń", "luty", "marzec", "kwiecień", "maj", "czerwiec",
    "lipiec", "sierpień", "wrzesień", "październik", "listopad", "grudzień",
]
KOL_UCZNIA = ["Imię dziecka", "Przedmiot", "Stawka za godzinę (zł)",
              "Domyślna płatność", "Fraza w kalendarzu"]
KOL_ROZLICZENIA = ["Uwzględnij", "Data", "Uczeń", "Przedmiot", "Tytuł w kalendarzu",
                   "Czas (min)", "Stawka (zł)", "Metoda płatności", "Status", "Opłacone"]

st.set_page_config(page_title="Skarbówka mnie goni", page_icon="💖", layout="wide")

# --- WYGLĄD ---
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@400;500;600&family=Inter:wght@400;500;600&display=swap');

    html, body, .stApp, [class*="st-"] { font-family: 'Inter', sans-serif; }
    .stApp { background-color: #f9ecf1; color: #4a2f3a; }
    .block-container { max-width: 1100px; padding-top: 2.5rem; padding-bottom: 4rem; }
    header[data-testid="stHeader"] { background: transparent; }

    h1, h2, h3 {
        font-family: 'Cormorant Garamond', serif !important;
        font-weight: 500 !important;
        color: #b85f79 !important;
        border: none !important;
        letter-spacing: 0.2px;
    }
    h1 { font-size: 3.2rem !important; margin-bottom: 0.2rem; }
    h3 { font-size: 1.9rem !important; margin-top: 1.2rem; }

    /* zakładki */
    button[data-baseweb="tab"] { font-weight: 500; font-size: 1rem; color: #8a5a6b; }
    button[data-baseweb="tab"][aria-selected="true"] { color: #b85f79; }
    div[data-baseweb="tab-highlight"] { background-color: #c9738c !important; height: 3px; }
    div[data-baseweb="tab-border"] { background-color: #efd0db !important; }

    /* karty */
    div[data-testid="stForm"],
    div[data-testid="stVerticalBlockBorderWrapper"] {
        background-color: #f6dbe4;
        border: none !important;
        border-radius: 24px !important;
        padding: 1.4rem 1.6rem;
    }
    div[data-testid="stForm"] { box-shadow: none; }
    div[data-testid="stMetric"] {
        background-color: #f6dbe4; border-radius: 20px; padding: 1rem 1.3rem;
    }
    div[data-testid="stMetricValue"] { font-family: 'Cormorant Garamond', serif; color: #b85f79; }
    div.stExpander { border: none !important; background-color: #f6dbe4; border-radius: 20px; }

    /* duży panel z kwotą */
    .panel {
        background: #d98fa3; color: #fff; border-radius: 28px;
        padding: 1.6rem 2rem; margin: 1rem 0 1.2rem 0;
    }
    .panel-label { font-size: 0.95rem; opacity: 0.9; letter-spacing: 0.5px; }
    .panel-amount {
        font-family: 'Cormorant Garamond', serif; font-size: 3.4rem;
        font-weight: 500; line-height: 1.1;
    }

    /* przyciski */
    .stButton > button, .stDownloadButton > button, .stFormSubmitButton > button {
        background-color: #d98fa3; color: #fff; border: none; border-radius: 999px;
        padding: 0.5rem 1.6rem; font-weight: 500; box-shadow: none; transition: 0.15s;
    }
    .stButton > button:hover, .stDownloadButton > button:hover,
    .stFormSubmitButton > button:hover { background-color: #c9738c; color: #fff; }

    /* pola */
    div[data-baseweb="input"], div[data-baseweb="select"] > div, div[data-baseweb="base-input"] {
        background-color: #ffffff !important; border-radius: 12px !important;
        border-color: #ecc3d1 !important;
    }
    input, textarea { color: #4a2f3a !important; }
    div[data-testid="stWidgetLabel"] p, div[data-testid="stWidgetLabel"] label {
        color: #5a3a46 !important; font-weight: 500;
    }
    div[data-testid="stFileUploader"] section { background: #fff; border-radius: 16px; }
    </style>
    """,
    unsafe_allow_html=True,
)


# --- DANE (dane.json) ---
def normalizuj_ucznia(u):
    return {
        "Imię dziecka": str(u.get("Imię dziecka", "")).strip(),
        "Przedmiot": str(u.get("Przedmiot", "") or "").strip(),
        "Stawka za godzinę (zł)": float(u.get("Stawka za godzinę (zł)") or 0.0),
        "Domyślna płatność": u.get("Domyślna płatność") or "Przelew",
        "Fraza w kalendarzu": str(u.get("Fraza w kalendarzu", "") or "").strip(),
    }


def wczytaj_dane():
    if PLIK_DANYCH.exists():
        try:
            dane = json.loads(PLIK_DANYCH.read_text(encoding="utf-8"))
            uczniowie = [normalizuj_ucznia(u) for u in dane.get("uczniowie", [])
                         if u.get("Imię dziecka")]
            miesiace = dane.get("miesiace", {})
            return uczniowie, miesiace if isinstance(miesiace, dict) else {}
        except (json.JSONDecodeError, OSError, ValueError, TypeError, AttributeError):
            pass
    return [], {}


def dane_do_json():
    return json.dumps(
        {"uczniowie": st.session_state.uczniowie, "miesiace": st.session_state.miesiace},
        ensure_ascii=False, indent=2,
    )


def zapisz_dane():
    PLIK_DANYCH.write_text(dane_do_json(), encoding="utf-8")


if "uczniowie" not in st.session_state:
    st.session_state.uczniowie, st.session_state.miesiace = wczytaj_dane()


# --- FUNKCJE POMOCNICZE ---
def fmt_zl(x):
    return f"{x:,.2f}".replace(",", " ").replace(".", ",") + " zł"


def klucz_miesiaca(rok, miesiac):
    return f"{rok}-{miesiac:02d}"


def nazwa_miesiaca(klucz):
    rok, m = klucz.split("-")
    return f"{MIESIACE[int(m) - 1]} {rok}"


def parse_ics_file(uploaded_file, rok, miesiac):
    """Wczytuje .ics z obsługą wydarzeń cyklicznych i strefy czasowej."""
    cal = Calendar.from_ical(uploaded_file.getvalue())
    start = (rok, miesiac, 1)
    koniec = (rok + (miesiac == 12), miesiac % 12 + 1, 1)

    lekcje = []
    for ev in recurring_ical_events.of(cal).between(start, koniec):
        dtstart = ev.decoded("DTSTART")
        if not isinstance(dtstart, datetime):  # pomijamy wydarzenia całodniowe
            continue
        dtend = ev.decoded("DTEND") if ev.get("DTEND") else dtstart
        if dtstart.tzinfo is None:
            dtstart = dtstart.replace(tzinfo=TZ)
        if dtend.tzinfo is None:
            dtend = dtend.replace(tzinfo=TZ)
        dtstart, dtend = dtstart.astimezone(TZ), dtend.astimezone(TZ)
        lekcje.append({
            "Data": dtstart.strftime("%Y-%m-%d"),
            "Godzina": f"{dtstart:%H:%M}",
            "Tytuł wydarzenia": str(ev.get("SUMMARY", "")),
            "Czas (min)": int((dtend - dtstart).total_seconds() // 60),
        })
    if not lekcje:
        return pd.DataFrame()
    return pd.DataFrame(lekcje).sort_values(["Data", "Godzina"])


def parse_csv_file(uploaded_file, rok, miesiac):
    """CSV musi mieć kolumny: Data, Tytuł wydarzenia, Czas (min)."""
    df = pd.read_csv(uploaded_file)
    brakuje = {"Data", "Tytuł wydarzenia", "Czas (min)"} - set(df.columns)
    if brakuje:
        st.error(f"W pliku CSV brakuje kolumn: {', '.join(sorted(brakuje))}")
        return pd.DataFrame()
    daty = pd.to_datetime(df["Data"], errors="coerce")
    df = df[(daty.dt.year == rok) & (daty.dt.month == miesiac)].copy()
    df["Data"] = daty.dt.strftime("%Y-%m-%d")
    return df.sort_values("Data")


def wzorzec_ucznia(u):
    """Fraza do szukania w tytule: własna albo imię bez końcówki (Zosia -> zosi)."""
    if u["Fraza w kalendarzu"]:
        return u["Fraza w kalendarzu"].lower()
    imie = u["Imię dziecka"].lower()
    return imie[:-1] if len(imie) >= 4 else imie


def dopasuj_ucznia(tytul, uczniowie):
    t = tytul.lower()
    trafione = [u for u in uczniowie if wzorzec_ucznia(u) and wzorzec_ucznia(u) in t]
    if len(trafione) == 1:
        return trafione[0], "ok"
    return None, ("niejednoznaczne" if trafione else "brak")


def buduj_rozliczenie(df_kalendarz, uczniowie):
    wiersze = []
    for _, row in df_kalendarz.iterrows():
        tytul = str(row["Tytuł wydarzenia"])
        minuty = int(row["Czas (min)"])
        u, wynik = dopasuj_ucznia(tytul, uczniowie)
        if u:
            wiersze.append({
                "Uwzględnij": True, "Data": row["Data"], "Uczeń": u["Imię dziecka"],
                "Przedmiot": u["Przedmiot"] or "—", "Tytuł w kalendarzu": tytul,
                "Czas (min)": minuty,
                "Stawka (zł)": round(u["Stawka za godzinę (zł)"] * minuty / 60, 2),
                "Metoda płatności": u["Domyślna płatność"],
                "Status": "Odbyła się", "Opłacone": False,
            })
        else:
            wiersze.append({
                "Uwzględnij": False, "Data": row["Data"],
                "Uczeń": "Nie przypisano" if wynik == "brak" else "Niejednoznaczne",
                "Przedmiot": "—", "Tytuł w kalendarzu": tytul, "Czas (min)": minuty,
                "Stawka (zł)": 0.0, "Metoda płatności": "Przelew",
                "Status": "Odbyła się", "Opłacone": False,
            })
    return pd.DataFrame(wiersze, columns=KOL_ROZLICZENIA)


def do_rozliczenia(df):
    return df[df["Uwzględnij"].astype(bool) & df["Status"].isin(STATUSY_PLATNE)]


def wiersze_do_json(df):
    return json.loads(df.to_json(orient="records", force_ascii=False))


def podsumowanie_miesiaca(wiersze):
    df = pd.DataFrame(wiersze, columns=KOL_ROZLICZENIA)
    df["Uwzględnij"] = df["Uwzględnij"].fillna(False).astype(bool)
    df["Opłacone"] = df["Opłacone"].fillna(False).astype(bool)
    liczone = do_rozliczenia(df)
    suma = float(liczone["Stawka (zł)"].fillna(0).sum())
    oplacone = float(liczone.loc[liczone["Opłacone"], "Stawka (zł)"].fillna(0).sum())
    return {
        "lekcje": len(liczone),
        "godziny": round(float(liczone["Czas (min)"].fillna(0).sum()) / 60, 2),
        "suma": suma, "oplacone": oplacone, "zalegle": suma - oplacone,
    }


# --- NAGŁÓWEK ---
st.title("Skarbówka mnie goni")

if "flash" in st.session_state:
    st.success(st.session_state.pop("flash"))

tab_u, tab_r, tab_h, tab_k = st.tabs(["Uczniowie", "Rozliczenie", "Historia", "Kopia zapasowa"])

# =============== ZAKŁADKA: UCZNIOWIE ===============
with tab_u:
    st.subheader("Dodaj ucznia")
    with st.form("formularz_ucznia", clear_on_submit=True):
        c1, c2 = st.columns(2)
        imie = c1.text_input("Imię dziecka", placeholder="np. Zosia")
        przedmiot = c2.text_input("Przedmiot", placeholder="np. Matematyka")
        c3, c4 = st.columns(2)
        stawka_h = c3.number_input("Stawka za godzinę (zł)", min_value=0.0, value=60.0, step=5.0)
        platnosc = c4.selectbox("Zwykle płaci", METODY_PLATNOSCI)
        fraza = st.text_input(
            "Fraza w kalendarzu (opcjonalnie)",
            placeholder="np. Zosia K.",
            help="Domyślnie szukam imienia w tytule wydarzenia. Wpisz własną frazę, "
                 "jeśli dwoje dzieci ma to samo imię albo tytuły są nietypowe.",
        )
        if st.form_submit_button("Dodaj ucznia"):
            if imie.strip():
                st.session_state.uczniowie.append(normalizuj_ucznia({
                    "Imię dziecka": imie, "Przedmiot": przedmiot,
                    "Stawka za godzinę (zł)": stawka_h,
                    "Domyślna płatność": platnosc, "Fraza w kalendarzu": fraza,
                }))
                zapisz_dane()
                st.session_state["flash"] = f"Dodano ucznia: {imie.strip()}"
                st.rerun()
            else:
                st.warning("Wpisz imię dziecka.")

    st.subheader("Twoi uczniowie")
    if st.session_state.uczniowie:
        edytowani = st.data_editor(
            pd.DataFrame(st.session_state.uczniowie, columns=KOL_UCZNIA),
            hide_index=True, num_rows="dynamic", key="edytor_uczniowie",
            use_container_width=True,
            column_config={
                "Stawka za godzinę (zł)": st.column_config.NumberColumn(min_value=0.0, format="%.2f"),
                "Domyślna płatność": st.column_config.SelectboxColumn(options=METODY_PLATNOSCI),
            },
        )
        edytowani = edytowani.dropna(subset=["Imię dziecka"])
        nowi = [normalizuj_ucznia(r) for r in edytowani.to_dict("records")
                if str(r["Imię dziecka"]).strip()]
        if nowi != st.session_state.uczniowie:
            st.session_state.uczniowie = nowi
            zapisz_dane()
    else:
        st.info("Nie ma jeszcze żadnych uczniów.")

# =============== ZAKŁADKA: ROZLICZENIE ===============
with tab_r:
    st.subheader("1. Wybierz miesiąc")
    c1, c2 = st.columns(2)
    rok = int(c1.number_input("Rok", 2024, 2035, datetime.now().year))
    miesiac = c2.selectbox("Miesiąc", range(1, 13), index=datetime.now().month - 1,
                           format_func=lambda m: MIESIACE[m - 1])
    klucz = klucz_miesiaca(rok, miesiac)
    zapisany = st.session_state.miesiace.get(klucz)

    st.subheader("2. Wgraj kalendarz")
    uploaded_file = st.file_uploader(
        "Plik .ics lub .csv", type=["ics", "csv"], label_visibility="collapsed")

    df_start, zrodlo = None, None
    if uploaded_file is not None:
        try:
            if uploaded_file.name.lower().endswith(".csv"):
                df_kal = parse_csv_file(uploaded_file, rok, miesiac)
            else:
                df_kal = parse_ics_file(uploaded_file, rok, miesiac)
        except Exception as e:
            st.error(f"Nie udało się odczytać pliku: {e}")
            df_kal = pd.DataFrame()

        if df_kal.empty:
            st.warning(f"Brak wydarzeń z miesiąca: {nazwa_miesiaca(klucz)}.")
        elif not st.session_state.uczniowie:
            st.warning("Najpierw dodaj uczniów w zakładce „Uczniowie”.")
        else:
            df_start = buduj_rozliczenie(df_kal, st.session_state.uczniowie)
            zrodlo = "kalendarz"
            if zapisany:
                st.info("Ten miesiąc ma już zapis. Zapisanie nadpisze go nowymi danymi.")
    elif zapisany:
        df_start = pd.DataFrame(zapisany, columns=KOL_ROZLICZENIA)
        zrodlo = "zapis"

    if df_start is not None:
        st.subheader("3. Sprawdź i popraw")
        opcje_uczniow = ["Nie przypisano", "Niejednoznaczne"] + sorted(
            {u["Imię dziecka"] for u in st.session_state.uczniowie})
        edited_df = st.data_editor(
            df_start, hide_index=True, num_rows="dynamic", use_container_width=True,
            key=f"edytor_{klucz}_{zrodlo}",
            column_config={
                "Uwzględnij": st.column_config.CheckboxColumn(
                    help="Odznacz wydarzenia, które nie są lekcjami."),
                "Opłacone": st.column_config.CheckboxColumn(),
                "Status": st.column_config.SelectboxColumn(options=STATUSY, required=True),
                "Metoda płatności": st.column_config.SelectboxColumn(
                    options=METODY_PLATNOSCI, required=True),
                "Uczeń": st.column_config.SelectboxColumn(options=opcje_uczniow),
                "Stawka (zł)": st.column_config.NumberColumn(format="%.2f"),
            },
        )
        edited_df = edited_df.dropna(subset=["Data"]).fillna(
            {"Uwzględnij": False, "Opłacone": False, "Stawka (zł)": 0.0})
        liczone = do_rozliczenia(edited_df)
        suma = float(liczone["Stawka (zł)"].sum())
        oplacone = float(liczone.loc[liczone["Opłacone"].astype(bool), "Stawka (zł)"].sum())

        st.markdown(
            f'<div class="panel"><div class="panel-label">Do rozliczenia · '
            f'{nazwa_miesiaca(klucz)}</div>'
            f'<div class="panel-amount">{fmt_zl(suma)}</div></div>',
            unsafe_allow_html=True,
        )
        m1, m2, m3 = st.columns(3)
        m1.metric("Opłacone", fmt_zl(oplacone))
        m2.metric("Czeka na płatność", fmt_zl(suma - oplacone))
        m3.metric("Liczba lekcji", len(liczone))

        if not liczone.empty:
            st.subheader("Podsumowanie")
            col_a, col_b = st.columns(2)
            po_uczniu = liczone.groupby("Uczeń").agg(
                Lekcje=("Data", "count"),
                Godziny=("Czas (min)", lambda s: round(s.sum() / 60, 2)),
                **{"Suma (zł)": ("Stawka (zł)", "sum")},
            ).reset_index()
            col_a.dataframe(po_uczniu, hide_index=True, use_container_width=True)
            col_b.dataframe(
                liczone.groupby("Metoda płatności")["Stawka (zł)"].sum().reset_index(),
                hide_index=True, use_container_width=True)

        b1, b2, _ = st.columns([1, 1, 2])
        if b1.button("Zapisz miesiąc"):
            st.session_state.miesiace[klucz] = wiersze_do_json(edited_df)
            zapisz_dane()
            st.session_state["flash"] = f"Zapisano: {nazwa_miesiaca(klucz)}"
            st.rerun()
        b2.download_button(
            "Pobierz CSV", liczone.to_csv(index=False).encode("utf-8-sig"),
            f"rozliczenie_{klucz}.csv", "text/csv",
        )
    elif uploaded_file is None:
        st.info("Wgraj kalendarz, żeby zacząć.")

# =============== ZAKŁADKA: HISTORIA ===============
with tab_h:
    if not st.session_state.miesiace:
        st.info("Nie ma jeszcze zapisanych miesięcy. Zapisz pierwszy w zakładce „Rozliczenie”.")
    else:
        lata = sorted({k.split("-")[0] for k in st.session_state.miesiace}, reverse=True)
        wybrany_rok = st.selectbox("Rok", lata)
        klucze = sorted(k for k in st.session_state.miesiace if k.startswith(wybrany_rok))
        wiersze = []
        for k in klucze:
            p = podsumowanie_miesiaca(st.session_state.miesiace[k])
            wiersze.append({
                "Miesiąc": nazwa_miesiaca(k), "Lekcje": p["lekcje"], "Godziny": p["godziny"],
                "Do rozliczenia (zł)": round(p["suma"], 2),
                "Opłacone (zł)": round(p["oplacone"], 2),
                "Zaległe (zł)": round(p["zalegle"], 2),
            })
        df_hist = pd.DataFrame(wiersze)

        st.markdown(
            f'<div class="panel"><div class="panel-label">Przychód w roku {wybrany_rok}</div>'
            f'<div class="panel-amount">{fmt_zl(df_hist["Do rozliczenia (zł)"].sum())}</div></div>',
            unsafe_allow_html=True,
        )
        h1, h2, h3 = st.columns(3)
        h1.metric("Opłacone", fmt_zl(df_hist["Opłacone (zł)"].sum()))
        h2.metric("Zaległe", fmt_zl(df_hist["Zaległe (zł)"].sum()))
        h3.metric("Godziny", f'{df_hist["Godziny"].sum():.1f}')
        st.dataframe(df_hist, hide_index=True, use_container_width=True)

        with st.expander("Usuń zapisany miesiąc"):
            do_usuniecia = st.selectbox("Miesiąc", klucze, format_func=nazwa_miesiaca,
                                        key="usun_miesiac")
            potwierdzenie = st.checkbox("Rozumiem, że tego nie da się cofnąć")
            if st.button("Usuń", disabled=not potwierdzenie):
                st.session_state.miesiace.pop(do_usuniecia, None)
                zapisz_dane()
                st.session_state["flash"] = f"Usunięto: {nazwa_miesiaca(do_usuniecia)}"
                st.rerun()

# =============== ZAKŁADKA: KOPIA ZAPASOWA ===============
with tab_k:
    st.subheader("Pobierz kopię")
    st.download_button(
        "Pobierz wszystkie dane (.json)", dane_do_json().encode("utf-8"),
        f"smg_kopia_{datetime.now():%Y-%m-%d}.json", "application/json",
    )
    st.subheader("Przywróć z kopii")
    plik_kopii = st.file_uploader("Plik .json", type=["json"], key="kopia",
                                  label_visibility="collapsed")
    if plik_kopii is not None and st.button("Przywróć dane z tego pliku"):
        try:
            dane = json.loads(plik_kopii.getvalue().decode("utf-8"))
            uczniowie = [normalizuj_ucznia(u) for u in dane["uczniowie"] if u.get("Imię dziecka")]
            miesiace = dane.get("miesiace", {})
            if not isinstance(miesiace, dict):
                raise ValueError("zły format miesięcy")
            st.session_state.uczniowie = uczniowie
            st.session_state.miesiace = miesiace
            zapisz_dane()
            st.session_state["flash"] = "Dane zostały przywrócone."
            st.rerun()
        except (KeyError, ValueError, TypeError, AttributeError, UnicodeDecodeError):
            st.error("To nie wygląda na plik kopii z tej aplikacji.")
