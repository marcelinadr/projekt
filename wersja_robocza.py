 import re
import pandas as pd
import streamlit as st

# --- KONFIGURACJA STRONY I STYLIZACJA (RETRO-PINK) ---
st.set_page_config(
    page_title="SMG - Skarbówka mnie goni", page_icon="💖", layout="wide"
)

# Wstrzykiwanie własnego kodu CSS dla uzyskania pastelowego, retro klimatu
st.markdown(
    """
    <style>
    /* Ogólne tło strony i czcionka */
    .stApp {
        background-color: #fff0f5;
        color: #4a3b4c;
    }
    
    /* Nagłówki */
    h1, h2, h3 {
        color: #d16ba5 !important;
        font-family: 'Courier New', Courier, monospace;
        border-bottom: 2px dashed #f3c6df;
        padding-bottom: 5px;
    }

    /* Kontenery formularzy / karty w stylu retro okienek */
    div[data-testid="stForm"], div.stExpander, div[data-testid="stVerticalBlock"] > div.stContainer {
        background-color: #ffffff;
        border: 2px solid #f3c6df;
        border-radius: 12px;
        padding: 15px;
        box-shadow: 4px 4px 0px #f8d7eb;
    }

    /* Przyciski */
    .stButton > button {
        background-color: #f7a8b8;
        color: white;
        border: 2px solid #d16ba5;
        border-radius: 8px;
        font-weight: bold;
        box-shadow: 2px 2px 0px #d16ba5;
        transition: 0.1s;
    }
    .stButton > button:hover {
        background-color: #f3839c;
        border-color: #b5497b;
        color: white;
    }

    /* Pola tekstowe i inputy */
    input, textarea, select {
        border: 2px solid #f3c6df !important;
        border-radius: 6px !important;
        background-color: #fff9fb !important;
    }
    </style>
""",
    unsafe_allow_html=True,
)

# --- NAGŁÓWEK APLIKACJI ---
st.title("💾 SMG: Skarbówka mnie goni ✨")
st.write(
    "Rozliczaj swoje korepetycje szybko, bezboleśnie i w pięknym, różowym stylu!"
)

# --- SEKCJA 1: KONFIGURACJA STAWEK ---
st.header("💖 1. Konfiguracja stawek")

if "cennik" not in st.session_state:
  st.session_state.cennik = []

with st.form("formularz_stawki"):
  stawka_domyslna = st.number_input(
      "Domyślna stawka za lekcję (w zł)", min_value=0.0, value=50.0, step=5.0
  )

  submit_button = st.form_submit_button("Zapisz stawkę")

  if submit_button:
    st.session_state.cennik = [{"Stawka (zł)": stawka_domyslna}]
    st.success(f"Zapisano stawkę domyślną: {stawka_domyslna} zł!")

if st.session_state.cennik:
  st.write(f"Aktualna stawka za lekcję: **{st.session_state.cennik[0]['Stawka (zł)']} zł**")
else:
  st.info("Brak zdefiniowanej stawki. Ustaw ją powyżej!")


# --- SEKCJA 2: BAZA UCZNIÓW I PRZEDMIOTÓW ---
st.header("🌸 2. Baza uczniów i przedmiotów")

if "uczniowie" not in st.session_state:
  st.session_state.uczniowie = []

with st.form("formularz_ucznia"):
  col_u1, col_u2 = st.columns(2)
  with col_u1:
    imie_dziecka = st.text_input("Imię dziecka (np. Zosia)")
  with col_u2:
    przedmiot = st.text_input("Przedmiot (np. Matematyka)")

  submit_uczen = st.form_submit_button("Dodaj ucznia do bazy")

  if submit_uczen:
    if imie_dziecka:
      nowy_uczen = {"Imię dziecka": imie_dziecka, "Przedmiot": przedmiot}
      st.session_state.uczniowie.append(nowy_uczen)
      st.success(f"Dodano do bazy: {imie_dziecka} – {przedmiot}")
    else:
      st.warning("Musisz podać imię dziecka!")

if st.session_state.uczniowie:
  df_uczniowie = pd.DataFrame(st.session_state.uczniowie)
  st.dataframe(df_uczniowie, hide_index=True)
else:
  st.info("Brak zdefiniowanych uczniów w bazie.")


# --- FUNKCJA PARSUJĄCA PLIK .ICS ---
def parse_ics_file(uploaded_file):
  content = uploaded_file.getvalue().decode("utf-8", errors="ignore")
  vevents = content.split("BEGIN:VEVENT")
  lekcje = []

  for event in vevents[1:]:
    summary_match = re.search(r"SUMMARY:(.*?)(?:\r?\n|$)", event)
    dtstart_match = re.search(r"DTSTART(?:;[^:]+)?:([0-9TZ]+)", event)

    if summary_match and dtstart_match:
      tytul = summary_match.group(1).strip()
      tytul = tytul.replace("\\,", ",").replace("\\;", ";")

      start_str = dtstart_match.group(1)

      try:
        start_dt = pd.to_datetime(start_str, errors="coerce")
        data_dzien = start_dt.strftime("%Y-%m-%d")
        godzina = start_dt.strftime("%H:%M")
      except:
        data_dzien = start_str[:8]
        godzina = "??:??"

      lekcje.append({
          "Data": data_dzien,
          "Godzina": godzina,
          "Tytuł wydarzenia": tytul,
      })

  return pd.DataFrame(lekcje)


# --- SEKCJA 3: WCZYTANIE KALENDARZA I ROZLICZENIE ---
st.header("🎀 3. Wgraj grafik i generuj rozliczenie")

uploaded_file = st.file_uploader(
    "Wgraj plik z kalendarzem (.ics lub .csv)", type=["ics", "csv"]
)

if uploaded_file is not None:
  st.success("Plik wczytany pomyślnie! 💕")

  if uploaded_file.name.endswith(".csv"):
    df_kalendarz = pd.read_csv(uploaded_file)
  elif uploaded_file.name.endswith(".ics"):
    df_kalendarz = parse_ics_file(uploaded_file)

  if not df_kalendarz.empty:
    st.subheader("Wykryte wydarzenia z kalendarza:")
    st.dataframe(df_kalendarz, hide_index=True)

    # SILNIK DOPASOWUJĄCY I ROZLICZENIE
    st.subheader("✨ Gotowa tabela rozliczeniowa miesięczna:")

    rozliczone_dane = []
    domyslna_stawka = (
        st.session_state.cennik[0]["Stawka (zł)"]
        if st.session_state.cennik
        else 50.0
    )

    for index, row in df_kalendarz.iterrows():
      tytul = row.get("Tytuł wydarzenia", "")

      # Dopasowanie ucznia z bazy na podstawie tekstu w tytule
      dopasowany_uczen = "Nie przypisano"
      dopasowany_przedmiot = "Nie przypisano"
      for u in st.session_state.uczniowie:
        if (
            u["Imię dziecka"].lower() in tytul.lower()
            or u["Przedmiot"].lower() in tytul.lower()
        ):
          dopasowany_uczen = u["Imię dziecka"]
          dopasowany_przedmiot = u["Przedmiot"]
          break

      rozliczone_dane.append({
          "Data": row.get("Data", "Brak"),
          "Godzina": row.get("Godzina", ""),
          "Uczeń": dopasowany_uczen,
          "Przedmiot": dopasowany_przedmiot,
          "Tytuł w kalendarzu": tytul,
          "Stawka (zł)": domyslna_stawka,
          "Metoda płatności": "Przelew",
      })

    df_wynikowe = pd.DataFrame(rozliczone_dane)

    # Edytowalna tabela w Streamlit
    edited_df = st.data_editor(df_wynikowe, hide_index=True, num_rows="dynamic")

    # Podsumowanie finansowe
    calkowity_zarobek = edited_df["Stawka (zł)"].sum()
    st.markdown(f"### 💰 Łącznie do rozliczenia: **{calkowity_zarobek:.2f} zł**")
  else:
    st.warning(
        "Nie znaleziono żadnych wydarzeń w wgranym pliku lub format jest"
        " nieczytelny."
    )
