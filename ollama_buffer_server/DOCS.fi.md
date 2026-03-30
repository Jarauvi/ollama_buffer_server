# Ollama-puskuripalvelin (Ollama Buffer Server)

Tämä sovellus toimii Home Assistantin ja paikallisen Ollama-palvelimesi välillä. Se esigeneroi ja tallentaa kielimallin vastaukset paikalliseen SQLite-tietokantaan, jotta automaatiot saavat vastaukset välittömästi ilman odottelua.

## Asetukset

### Yhteys
- **Ollama API-päätepiste**: Ollama-palvelimen URL-osoite.
- **Valtuutustunnus**: Token API:n suojaamiseksi.

### Puskuripäätepisteet
Voit määrittää useita eri "puskureita" eri käyttötarkoituksiin (esim. yksi säätiedotuksille, toinen yleisten vastausten summaamiseen).
- **Nimi**: Puskurin yksilöllinen tunniste (ID).
- **Puskurin maksimikoko**: Kuinka monta valmista vastausta pidetään varastossa.
- **Puskurin kehote (Prompt)**: Ohje, jota käytetään vastausten esigenerointiin.

## Käyttöohje
Kun sovellus on käynnissä, vastauksen voi noutaa esim. Home Assistantin REST-komennolla:

```yaml
rest_command:
  get_ai_reply:
    url: "http://localhost:8000/read_buffer"
    method: post
    headers:
      Authorization: "Bearer SINUN_TUNNUKSESI"
    payload: '{"name": "weather"}'
```