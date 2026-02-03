# KSeF E2E Login Test (Playwright + Python)

Skrypt automatyzuje podstawowy test logowania do KSeF:

1. Wejście na `https://ap.ksef.mf.gov.pl/web/`
2. Kliknięcie „Uwierzytelnij się w Krajowym Systemie”
3. Kliknięcie „Zaloguj profilem zaufanym”
4. Wpisanie losowego poprawnego NIP
5. Jeśli nastąpi przekierowanie na `podpis.gov.pl` → test OK
6. W przeciwnym razie test zgłasza błąd z treścią z konsoli / odpowiedzi 400

## Wymagania

- Python 3.9+
- `pip`

## Szybkie uruchomienie (jedna komenda)

```bash
./run.sh
```

Skrypt:
- utworzy `.venv` jeśli nie istnieje,
- zainstaluje zależności,
- zainstaluje Chromium dla Playwright,
- uruchomi testy.

## Ręczne uruchomienie

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m playwright install --with-deps chromium
pytest -q
```

Jeśli nie masz uprawnień do instalacji zależności systemowych:

```bash
python -m playwright install chromium
```

## Tryb debug

```bash
KSEF_DEBUG=1 pytest -q -s
```

W trybie debug zapisywane są:
- `debug/*.html`
- `debug/*.png`

## Pliki

- `tests/test_ksef_login.py` — główny test
- `requirements.txt` — zależności
- `run.sh` — uruchomienie jedną komendą

## Uwagi

- Test generuje poprawny NIP zgodnie z algorytmem kontrolnym (mod 11).
- Strona KSeF bywa niestabilna — w razie błędów uruchom test w trybie debug i sprawdź artefakty w `debug/`.
