import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import recurring_ical_events
import streamlit as st
from icalendar import Calendar

# pip install streamlit pandas icalendar recurring-ical-events

TZ = ZoneInfo("Europe/Warsaw")
PLIK_DANYCH = Path("dane.json")
METODY_PLATNOSCI = ["Przelew", "BLIK", "Gotówka"]
MIESIACE = [
    "styczeń", "luty", "marzec", "kwiecień", "maj", "czerwiec",
    "lipiec", "sierpień", "wrzesień", "październik", "listopad", "grudzień",
]

# --- KONFIGURACJA STRONY I STYLIZACJA (RETRO-PINK) ---
st.set_page_config(
    page_title="SMG - Skarbówka mnie goni", page_icon="💖", layout="wide"
)

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
        background-color: #f7a8b8;
        color: white;
        border: 2px solid #d16ba5;
        border-radius: 8px;
        font-weight: bold;
        box-shadow: 2px 2px 0px #d16ba5;
        transition: 0.1s;
    }
    .stButton > button:hover, .stDownloadButton > button:hover,
    .stFormSubmitButton > button:hover {
        background-color: #f3839c;
        border-color: #b5497b;
        color: white;
    }

    input, textarea, select {
        border: 2px solid #f3c6df !important;
        border-radius: 6px !important;
        background-color: #fff9fb !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# --- TRWAŁOŚĆ DANYCH (dane.json) ---
def wczytaj_dane():
    if PLIK_DANYCH.exists():
        try:
            return json.loads(PLIK_DANYCH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {"cennik": [], "uczniowie": []}


def zapisz_dane():
    PLIK_DANYCH.write_text(
        json.dumps(
            {
                "cennik": st.session_state.cennik,
                "uczniowie": st.session_state.uczniowie,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


if "cennik" not in st.session_state:
    dane = wczytaj_dane()
    st.session_state.cennik = dane.get("cennik", [])
    st.session_state.uczniowie = dane.get("uczniowie", [])


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
        # wydarzenia bez strefy traktujemy jako czas polski
        if dtstart.tzinfo is None:
            dtstart = dtstart.replace(tzinfo=TZ)
        if dtend.tzinfo is None:
            dtend = dtend.replace(tzinfo=TZ)
        dtstart, dtend = dtstart.astimezone(TZ), dtend.astimezone(TZ)

        lekcje.append(
            {
                "Data": dtstart.strftime("%Y-%m-%d"),
                "Godzina": f"{dtstart:%H:%M} - {dtend:%H:%M}",
                "Tytuł wydarzenia": str(ev.get("SUMMARY", "")),
                "Czas (min)": int((dtend - dtstart).total_seconds() // 60),
            }
        )
    if not lekcje:
        return pd.DataFrame()
    return pd.DataFrame(lekcje).sort_values(["Data", "Godzina"])


def parse_csv_file(uploaded_file, rok, miesiac):
    """CSV musi mieć kolumny: Data, Tytuł wydarzenia, Czas (min)."""
    df = pd.read_csv(uploaded_file)
    wymagane = {"Data", "Tytuł wydarzenia", "Czas (min)"}
    brakuje = wymagane - set(df.columns)
    if brakuje:
        st.error(f"W pliku CSV brakuje kolumn: {', '.join(sorted(brakuje))}")
        return pd.DataFrame()
    daty = pd.to_datetime(df["Data"], errors="coerce")
    df = df[(daty.dt.year == rok) & (daty.dt.month == miesiac)].copy()
    df["Data"] = daty.dt.strftime("%Y-%m-%d")
    return df.sort_values("Data")


def znajdz_stawke(minuty, cennik):
    for c in cennik:
        if c["Czas (min)"] == minuty:
            return c["Stawka (zł)"]
    if cennik:  # proporcjonalnie do pierwszej zdefiniowanej stawki
        c = cennik[0]
        return round(c["Stawka (zł)"] / c["Czas (min)"] * minuty, 2)
    return 0.0


def dopasuj_ucznia(tytul, uczniowie):
    t = tytul.lower()
    for u in uczniowie:
        if u["Imię dziecka"].lower() in t:
            return u
    return None


# --- NAGŁÓWEK ---
st.title("💾 SMG: Skarbówka mnie goni ✨")
st.write("Rozliczaj swoje korepetycje szybko, bezboleśnie i w pięknym, różowym stylu!")

# --- SEKCJA 1: STAWKI ---
st.header("💖 1. Konfiguracja stawek za czas zajęć")

with st.form("formularz_stawki"):
    col1, col2 = st.columns(2)
    minuty_f = col1.number_input(
        "Czas trwania (w minutach)", min_value=15, max_value=240, value=60, step=15
    )
    stawka_f = col2.number_input(
        "Stawka (w zł) za ten czas", min_value=0.0, value=50.0, step=5.0
    )
    if st.form_submit_button("Dodaj / Zaktualizuj stawkę"):
        for wpis in st.session_state.cennik:
            if wpis["Czas (min)"] == minuty_f:
                wpis["Stawka (zł)"] = stawka_f
                break
        else:
            st.session_state.cennik.append(
                {"Czas (min)": int(minuty_f), "Stawka (zł)": float(stawka_f)}
            )
        zapisz_dane()
        st.success(f"Zapisano stawkę {stawka_f} zł dla czasu {minuty_f} min!")

if st.session_state.cennik:
    edytowany = st.data_editor(
        pd.DataFrame(st.session_state.cennik),
        hide_index=True,
        num_rows="dynamic",
        key="edytor_cennik",
    ).dropna()
    nowy_cennik = edytowany.to_dict("records")
    if nowy_cennik != st.session_state.cennik:
        st.session_state.cennik = nowy_cennik
        zapisz_dane()
else:
    st.info("Brak zdefiniowanych stawek. Dodaj jakąś powyżej!")

# --- SEKCJA 2: UCZNIOWIE ---
st.header("🌸 2. Baza uczniów i przedmiotów")
st.caption("Uczeń jest rozpoznawany po imieniu w tytule wydarzenia w kalendarzu.")

with st.form("formularz_ucznia"):
    col_u1, col_u2 = st.columns(2)
    imie_dziecka = col_u1.text_input("Imię dziecka (np. Zosia)")
    przedmiot = col_u2.text_input("Przedmiot (np. Matematyka)")
    if st.form_submit_button("Dodaj ucznia do bazy"):
        if imie_dziecka.strip():
            st.session_state.uczniowie.append(
                {"Imię dziecka": imie_dziecka.strip(), "Przedmiot": przedmiot.strip()}
            )
            zapisz_dane()
            st.success(f"Dodano do bazy: {imie_dziecka} – {przedmiot}")
        else:
            st.warning("Musisz podać imię dziecka!")

if st.session_state.uczniowie:
    edytowani = st.data_editor(
        pd.DataFrame(st.session_state.uczniowie),
        hide_index=True,
        num_rows="dynamic",
        key="edytor_uczniowie",
    )
    edytowani = edytowani.dropna(subset=["Imię dziecka"]).fillna("")
    nowi = edytowani.to_dict("records")
    if nowi != st.session_state.uczniowie:
        st.session_state.uczniowie = nowi
        zapisz_dane()
else:
    st.info("Brak zdefiniowanych uczniów w bazie.")

# --- SEKCJA 3: KALENDARZ I ROZLICZENIE ---
st.header("🎀 3. Wgraj grafik i generuj rozliczenie")

c1, c2 = st.columns(2)
rok = int(c1.number_input("Rok", 2024, 2035, datetime.now().year))
miesiac = c2.selectbox(
    "Miesiąc",
    range(1, 13),
    index=datetime.now().month - 1,
    format_func=lambda m: MIESIACE[m - 1],
)

uploaded_file = st.file_uploader(
    "Wgraj plik z kalendarzem (.ics lub .csv)", type=["ics", "csv"]
)

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
        st.warning(
            f"Nie znaleziono wydarzeń z miesiąca: {MIESIACE[miesiac - 1]} {rok}"
            " (sprawdź też format pliku)."
        )
    else:
        st.success("Plik wczytany pomyślnie! 💕")
        st.subheader("Wykryte wydarzenia z kalendarza:")
        st.dataframe(df_kalendarz, hide_index=True)

        st.subheader(f"✨ Rozliczenie: {MIESIACE[miesiac - 1]} {rok}")

        rozliczone = []
        for _, row in df_kalendarz.iterrows():
            tytul = str(row["Tytuł wydarzenia"])
            minuty = int(row["Czas (min)"])
            uczen = dopasuj_ucznia(tytul, st.session_state.uczniowie)
            rozliczone.append(
                {
                    "Data": row["Data"],
                    "Uczeń": uczen["Imię dziecka"] if uczen else "Nie przypisano",
                    "Przedmiot": (uczen["Przedmiot"] if uczen else "") or "—",
                    "Tytuł w kalendarzu": tytul,
                    "Czas (min)": minuty,
                    "Stawka (zł)": znajdz_stawke(minuty, st.session_state.cennik),
                    "Metoda płatności": "Przelew",
                }
            )
        df_wynikowe = pd.DataFrame(rozliczone)

        opcje_uczniow = ["Nie przypisano"] + sorted(
            {u["Imię dziecka"] for u in st.session_state.uczniowie}
        )
        edited_df = st.data_editor(
            df_wynikowe,
            hide_index=True,
            num_rows="dynamic",
            column_config={
                "Metoda płatności": st.column_config.SelectboxColumn(
                    options=METODY_PLATNOSCI, required=True
                ),
                "Uczeń": st.column_config.SelectboxColumn(options=opcje_uczniow),
                "Stawka (zł)": st.column_config.NumberColumn(format="%.2f"),
            },
        )

        calkowity = edited_df["Stawka (zł)"].sum()
        st.markdown(f"### 💰 Łącznie do rozliczenia: **{calkowity:.2f} zł**")

        st.markdown("#### 🧸 Podsumowanie")
        col_a, col_b = st.columns(2)
        col_a.dataframe(
            edited_df.groupby("Uczeń")["Stawka (zł)"].sum().reset_index(),
            hide_index=True,
        )
        col_b.dataframe(
            edited_df.groupby("Metoda płatności")["Stawka (zł)"].sum().reset_index(),
            hide_index=True,
        )

        st.download_button(
            "💾 Pobierz CSV",
            edited_df.to_csv(index=False).encode("utf-8-sig"),
            f"rozliczenie_{rok}_{miesiac:02d}.csv",
            "text/csv",
        )
