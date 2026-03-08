## AI Indian Stock Mover – Telegram Bot

This project tracks Indian NSE stocks (from NIFTY 50, NIFTY NEXT 50,
NIFTY MIDCAP 100, NIFTY SMALLCAP 100) that move between 5–10% in a
session, finds related news, generates a short explanation of the move,
and sends a summary to your personal Telegram account.

### Components

- **Python backend** (`backend/`):
  - Fetches NSE data using `nsepython`.
  - Finds 5–10% movers in the selected indices.
  - Fetches related news from a free news API (if configured) and/or Google News RSS.
  - Generates a human-readable reason for each move (heuristic or optional AI summarization).
  - Sends a text summary to a Telegram chat via the Telegram Bot API.
- **Scheduler**:
  - GitHub Actions workflow runs the backend every trading day around 10:00 AM IST.

---

## Backend setup (Python)

### 1. Install dependencies

From the repo root:

```bash
python -m venv .venv
source .venv/bin/activate  # on Windows: .venv\Scripts\activate
pip install -U pip
pip install .
```

### 2. Environment variables

The backend reads configuration from environment variables:

- **Required for Telegram notifications**:
  - `TELEGRAM_BOT_TOKEN`: Bot token from BotFather.
  - `TELEGRAM_CHAT_ID`: Your personal chat ID (or a group/channel ID).
- **Optional for primary news API**:
  - `NEWS_API_KEY`: API key for your chosen free news API (e.g. MarketAux).
  - `NEWS_API_BASE_URL`: Base URL for the news API (defaults to a MarketAux-style endpoint).
- **Optional tuning**:
  - `MIN_MOVE_PERCENT` (default `5`)
  - `MAX_MOVE_PERCENT` (default `10`)
  - `MAX_MOVERS_PER_SIDE` (default `30`)
- **Optional AI summarization**:
  - `ENABLE_SUMMARIZATION` (`true`/`false`, default `false`)
  - `SUMMARIZATION_MODEL` (Hugging Face model name, default `sshleifer/distilbart-cnn-12-6`)
  - `SUMMARY_MAX_LENGTH`, `SUMMARY_MIN_LENGTH` (ints, control summarization length)

### 3. Running the daily job locally

With the virtualenv active and env vars set:

```bash
python -m backend.run_daily_job
```

This will:

1. Determine “today” in IST and skip weekends.
2. Fetch index constituents and compute percentage moves.
3. Filter movers whose absolute move is between `MIN_MOVE_PERCENT` and `MAX_MOVE_PERCENT`.
4. Fetch related news for each mover.
5. Generate a `reasonSummary` for each mover.
6. Send a summary message to your configured Telegram chat.

---

## GitHub Actions scheduler

The workflow file `.github/workflows/daily_movers.yml` runs the
Python job on a schedule roughly corresponding to 10:00 AM IST:

- Cron expression: `30 4 * * 1-5` (04:30 UTC, Monday–Friday).

### Required secrets in GitHub

In your repository settings under **Secrets and variables → Actions**, add:

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`
- `NEWS_API_KEY` (optional, but recommended for better news coverage)

Once configured, GitHub Actions will execute the ingestion job automatically on each
scheduled run and send you a Telegram message.

---

## Optional AI summarization

By default, the backend uses a lightweight heuristic `reason_engine` based on
headline keywords. To enable AI summarization:

1. Install `transformers` and a compatible backend (e.g. PyTorch) in the backend
   environment.
2. Set:

   ```bash
   export ENABLE_SUMMARIZATION=true
   export SUMMARIZATION_MODEL=sshleifer/distilbart-cnn-12-6  # or another summarization model
   ```

3. Re-run `backend.run_daily_job` locally, or set these env vars in GitHub Actions.

If the summarization model cannot be loaded for any reason, the code automatically
falls back to the heuristic reason generator, so failures are graceful.

---

## Streamlit dashboard

This project now stores alert history in `data/alerts_history.csv` and includes a
dashboard with filters for date, symbol, sector, reason type, hit-rate, and PnL.

Run:

```bash
streamlit run dashboard/app.py
```

Optional custom history path:

```bash
export ALERT_HISTORY_PATH=/path/to/alerts_history.csv
streamlit run dashboard/app.py
```
