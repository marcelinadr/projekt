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

# --- KONFIGURACJA STRONY I STYLIZACJA (RETRO-PINK) ---
st.set_page_config(page_title="SMG - Skarbówka mnie goni", page_icon="💖", layout="wide")

st.markdown(
    """
    <style>
    .stApp { background-color: #fff0f5; color: #4a3b4c; }
    h1, h2, h3 {
        color: #d16ba5 !important;
        font-family: 'Courier New', Courier, monospace;
        border-bottom: 2px dashed #f3c6df;
        padding-bottom: 5px;
    }
    div[data-testid="stForm"], div.stExpander {
        background-color: #ffffff;
        border: 2px solid #f3c6df;
        border-radius: 12px;
        padding: 15px;
        box-shadow: 4px 4px 0px #f8d7eb;
    }
    .stButton > button, .stDownloadButton > button, .stFormSubmitButton > button {
        background-color: #f7a8b8; color: white; border: 2px solid #d16ba5;
        border-radius: 8px; font-weight: bold; box-shadow: 2px 2px 0px #d16ba5;
        transition: 0.1s;
    }
    .stButton > button:hover, .stDownloadButton > button:hover,
    .stFormSubmitButton > button:hover {
        background-color: #f3839c; border-color: #b5497b; color: white;
    }
    input, textarea, select {
        border: 2px solid #f3c6df !important; border-radius: 6px !important;
        background-color: #fff9fb !important; color: #4a3b4c !important;
    }
    div[data-testid="stWidgetLabel"] p, div[data-testid="stWidgetLabel"] label,
    div[data-testid="stCaptionContainer"], .stMarkdown p { color: #4a3b4c !important; }
    </style>
    """,
    unsafe_allow_html=True,
)


# --- TRWAŁOŚĆ DANYCH (dane.json) ---
def normalizuj_ucznia(u):
    return {
        "Imię dziecka": str(u.get("Imię dziecka", "")).strip(),
        "Przedmiot": str(u.get("Przedmiot", "") or "").strip(),
        "Stawka za godzinę (zł)": float(u.get("Stawka za godzinę (zł)") or 0.0),
        "Domyślna płatność": u.get("Domyślna płatność") or "Przelew",
        "Fraza w kalendarzu": str(u.get("Fraza w kalendarzu", "") or "").strip(),
    }


def wczytaj_uczniow():
    if PLIK_DANYCH.exists():
        try:
            dane = json.loads(PLIK_DANYCH.read_text(encoding="utf-8"))
            return [normalizuj_ucznia(u) for u in dane.get("uczniowie", [])
                    if u.get("Imię dziecka")]
        except (json.JSONDecodeError, OSError, ValueError, TypeError):
            pass
    return []


def zapisz_uczniow():
    PLIK_DANYCH.write_text(
        json.dumps({"uczniowie": st.session_state.uczniowie},
                   ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


if "uczniowie" not in st.session_state:
    st.session_state.uczniowie = wczytaj_uczniow()


# --- FUNKCJE POMOCNICZE ---
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
    """Zwraca (uczeń, status): status 'ok' / 'brak' / 'niejednoznaczne'."""
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
            stawka = round(u["Stawka za godzinę (zł)"] * minuty / 60, 2)
            wiersze.append({
                "Uwzględnij": True, "Data": row["Data"], "Uczeń": u["Imię dziecka"],
                "Przedmiot": u["Przedmiot"] or "—", "Tytuł w kalendarzu": tytul,
                "Czas (min)": minuty, "Stawka (zł)": stawka,
                "Metoda płatności": u["Domyślna płatność"],
                "Status": "Odbyła się", "Opłacone": False,
            })
        else:
            wiersze.append({
                "Uwzględnij": False, "Data": row["Data"],
                "Uczeń": "Nie przypisano" if wynik == "brak" else "Niejednoznaczne",
                "Przedmiot": "—", "Tytuł w kalendarzu": tytul,
                "Czas (min)": minuty, "Stawka (zł)": 0.0,
                "Metoda płatności": "Przelew", "Status": "Odbyła się",
                "Opłacone": False,
            })
    return pd.DataFrame(wiersze)


def do_rozliczenia(df):
    return df[df["Uwzględnij"] & df["Status"].isin(STATUSY_PLATNE)]


# --- NAGŁÓWEK ---
st.title("💾 SMG: Skarbówka mnie goni ✨")
st.write("Rozliczaj swoje korepetycje szybko, bezboleśnie i w pięknym, różowym stylu!")

# --- SEKCJA 1: UCZNIOWIE ---
st.header("🌸 1. Uczniowie: stawka i płatność")
st.caption(
    "Uczeń jest rozpoznawany po imieniu w tytule wydarzenia (np. „Zosia – matma”). "
    "Jeśli dwoje dzieci ma to samo imię albo tytuły są nietypowe, wpisz własną frazę."
)

with st.form("formularz_ucznia"):
    c1, c2, c3 = st.columns(3)
    imie = c1.text_input("Imię dziecka (np. Zosia)")
    przedmiot = c2.text_input("Przedmiot (np. Matematyka)")
    stawka_h = c3.number_input("Stawka za godzinę (zł)", min_value=0.0, value=60.0, step=5.0)
    c4, c5 = st.columns(2)
    platnosc = c4.selectbox("Domyślna metoda płatności", METODY_PLATNOSCI)
    fraza = c5.text_input("Fraza w kalendarzu (opcjonalnie)")
    if st.form_submit_button("Dodaj ucznia"):
        if imie.strip():
            st.session_state.uczniowie.append(normalizuj_ucznia({
                "Imię dziecka": imie, "Przedmiot": przedmiot,
                "Stawka za godzinę (zł)": stawka_h,
                "Domyślna płatność": platnosc, "Fraza w kalendarzu": fraza,
            }))
            zapisz_uczniow()
            st.success(f"Dodano: {imie.strip()} – {stawka_h:.2f} zł/h")
        else:
            st.warning("Musisz podać imię dziecka!")

if st.session_state.uczniowie:
    edytowani = st.data_editor(
        pd.DataFrame(st.session_state.uczniowie, columns=KOL_UCZNIA),
        hide_index=True, num_rows="dynamic", key="edytor_uczniowie",
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
        zapisz_uczniow()
else:
    st.info("Brak uczniów. Dodaj pierwszego powyżej!")

# --- SEKCJA 2: KALENDARZ I ROZLICZENIE ---
st.header("🎀 2. Wgraj grafik i generuj rozliczenie")

c1, c2 = st.columns(2)
rok = int(c1.number_input("Rok", 2024, 2035, datetime.now().year))
miesiac = c2.selectbox("Miesiąc", range(1, 13), index=datetime.now().month - 1,
                       format_func=lambda m: MIESIACE[m - 1])

uploaded_file = st.file_uploader("Wgraj plik z kalendarzem (.ics lub .csv)", type=["ics", "csv"])

if uploaded_file is not None:
    try:
        if uploaded_file.name.lower().endswith(".csv"):
            df_kalendarz = parse_csv_file(uploaded_file, rok, miesiac)
        else:
            df_kalendarz = parse_ics_file(uploaded_file, rok, miesiac)
    except Exception as e:
        st.error(f"Nie udało się odczytać pliku: {e}")
        df_kalendarz = pd.DataFrame()

    if df_kalendarz.empty:
        st.warning(f"Nie znaleziono wydarzeń z miesiąca: {MIESIACE[miesiac - 1]} {rok} "
                   "(sprawdź też format pliku).")
    elif not st.session_state.uczniowie:
        st.warning("Najpierw dodaj uczniów w sekcji 1, żeby dopasować lekcje.")
    else:
        df_wynikowe = buduj_rozliczenie(df_kalendarz, st.session_state.uczniowie)
        nieprzypisane = int((~df_wynikowe["Uwzględnij"]).sum())

        st.subheader(f"✨ Rozliczenie: {MIESIACE[miesiac - 1]} {rok}")
        st.caption(
            f"Wydarzenia bez dopasowanego ucznia ({nieprzypisane}) są domyślnie "
            "wyłączone z sumy. Zaznacz „Uwzględnij” i wybierz ucznia, jeśli to jednak lekcja."
        )

        opcje_uczniow = ["Nie przypisano", "Niejednoznaczne"] + sorted(
            {u["Imię dziecka"] for u in st.session_state.uczniowie})
        edited_df = st.data_editor(
            df_wynikowe, hide_index=True, num_rows="dynamic",
            column_config={
                "Uwzględnij": st.column_config.CheckboxColumn(),
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

        suma = liczone["Stawka (zł)"].sum()
        oplacone = liczone.loc[liczone["Opłacone"], "Stawka (zł)"].sum()
        st.markdown(f"### 💰 Do rozliczenia: **{suma:.2f} zł**")
        m1, m2, m3 = st.columns(3)
        m1.metric("Opłacone", f"{oplacone:.2f} zł")
        m2.metric("Czeka na płatność", f"{suma - oplacone:.2f} zł")
        m3.metric("Liczba lekcji", len(liczone))

        if not liczone.empty:
            st.markdown("#### 🧸 Podsumowanie")
            col_a, col_b = st.columns(2)
            po_uczniu = liczone.groupby("Uczeń").agg(
                Lekcje=("Data", "count"),
                Godziny=("Czas (min)", lambda s: round(s.sum() / 60, 2)),
                **{"Suma (zł)": ("Stawka (zł)", "sum")},
            ).reset_index()
            col_a.dataframe(po_uczniu, hide_index=True)
            col_b.dataframe(
                liczone.groupby("Metoda płatności")["Stawka (zł)"].sum().reset_index(),
                hide_index=True)

        st.download_button(
            "💾 Pobierz CSV (tylko uwzględnione lekcje)",
            liczone.to_csv(index=False).encode("utf-8-sig"),
            f"rozliczenie_{rok}_{miesiac:02d}.csv", "text/csv",
        )
