# Wingspan Calculator

Unofficial Streamlit app for the [Wingspan](https://stonemaiergames.com/games/wingspan/) board game. Estimate bird draw probabilities from your selected expansions and filters, and calculate food dice odds.

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Deploy

This app is set up for [Streamlit Community Cloud](https://share.streamlit.io). Main file: `app.py`.

## Data sources

Bird card data in `wingspan_game.csv` is derived from the community dataset packaged in [coolbutuseless/wingspan](https://github.com/coolbutuseless/wingspan) (see [DATA_LICENSE](DATA_LICENSE)), originally compiled by [TawnyFrogmouth on BoardGameGeek](https://boardgamegeek.com/filepage/193164/wingspan-bird-card-bonus-card-spreadsheet).

Americas expansion birds were supplemented from [Wingsearch](https://github.com/navarog/wingsearch) via `import_americas.py`.

## Disclaimer

Wingspan is a trademark of Stonemaier Games. This project is unofficial fan tooling and is not affiliated with or endorsed by Stonemaier Games.

## License

Application code is licensed under the [MIT License](LICENSE). Bird card data is subject to the terms in [DATA_LICENSE](DATA_LICENSE).
