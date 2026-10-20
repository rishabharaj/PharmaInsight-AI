# PharmaInsight AI

PharmaInsight AI is an interactive sales analytics app built with Streamlit, SQLite, Pandas, Plotly, and LangChain. It explores a **fully synthetic** pharmaceutical sales dataset and turns verified SQL results into charts, answers, and business recommendations. Product names, representatives, transactions, and figures are fictional.

## What you can do

- **Explore the dashboard:** filter by date, region, and product; review revenue, units, monthly trends, product mix, regional results, and sales representative rankings.
- **Ask the data:** ask supported questions about product movement, regional performance, or monthly sales trends. The app runs predefined, parameterized SQL queries and shows the actual figures beside each answer.
- **Generate business insights:** get a deterministic summary without an API key, or request a LangChain and OpenAI explanation of verified aggregate facts.

Try asking: **“Which medicine performed poorly last month, and what should we do?”** The app compares each selected product across the latest two complete months in the dataset, identifies revenue declines, and suggests checks before making a business decision. For the included sample, this compares November and December 2025.

## How it works

```text
Synthetic CSV → Pandas validation → SQLite sales + dimension tables
                                      ├─ parameterized SQL → KPIs, charts, rankings
                                      ├─ fixed SQL tools → LangChain Q&A → OpenAI suggestions
                                      └─ verified facts → offline or AI business insights
```

SQL calculates every displayed figure. A fixed router selects one of three read-only query tools; the model cannot create or execute SQL. Only the question and aggregate synthetic results are sent to OpenAI when an AI answer is requested. Generated numerical claims are rejected, and the app falls back to a verified SQL summary. The included CSV has 2,400 valid transactions; the import also demonstrates exclusion of two invalid rows and one duplicate.

## Run locally

Requires Python 3.10+ and an internet connection for the optional AI features. The dashboard and SQL answers also work offline.

### Windows

Double-click `START_PROJECT.bat`, then open [http://127.0.0.1:8501](http://127.0.0.1:8501). The launcher sets up the Python environment and sample database on first run.

For a manual start:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pharma_insight.setup
.\.venv\Scripts\python.exe -m streamlit run app.py --server.address 127.0.0.1
```

### macOS or Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m pharma_insight.setup
python -m streamlit run app.py
```

### OpenAI key for local use

Create a **`.env` file in the project root**, beside `app.py` and `requirements.txt`, using `.env.example` as the template:

```dotenv
OPENAI_API_KEY=your_openai_api_key_here
```

Keep the real key only in your local `.env`; it is excluded by `.gitignore`. If you already have a `.env`, edit it instead of replacing it. Refresh the app after adding the key. Without it, the dashboard and verified SQL summaries remain available.

## Deploy on Streamlit Community Cloud

1. Sign in to [Streamlit Community Cloud](https://share.streamlit.io/) with GitHub and select **Create app**.
2. Choose this repository, branch **`main`**, and entrypoint **`app.py`**. Streamlit installs packages from `requirements.txt`.
3. In **Advanced settings → Secrets**, add the key as a root-level TOML secret:

   ```toml
   OPENAI_API_KEY = "your_openai_api_key_here"
   ```

4. Click **Deploy** and wait for the app URL. If you skip the secret, the SQL dashboard still works and the AI features use their offline summaries.

**Do not upload `.env` to GitHub or to Streamlit Cloud.** The `.env` file is for local development; the hosted app reads `OPENAI_API_KEY` from Streamlit's Secrets setting. If you make the hosted app public with an API key, visitors can trigger requests against your OpenAI account.

This Streamlit server is not designed for a direct Vercel import. A Vercel deployment would need a separate web frontend and API. Streamlit Community Cloud runs the existing app with its current architecture.

## Verify

```bash
python -m pytest -q
```

The tests cover data validation, filtered SQL totals, the three query tools, AI response guards, and Streamlit interactions.

## Project structure

| Path | Purpose |
| --- | --- |
| `app.py` | Dashboard, chat interface, and business insights |
| `pharma_insight/generator.py` | Repeatable synthetic dataset |
| `pharma_insight/database.py` | Pandas validation and SQLite loading |
| `pharma_insight/analytics.py` | Dashboard queries and verified facts |
| `pharma_insight/qa.py` | Safe SQL tools and LangChain question answering |
| `pharma_insight/insights.py` | OpenAI integration and offline insights |
| `tests/` | Automated checks |
| `SOURCES_AND_CREDITS.md` | Library and source attribution |

## Scope and limitations

The dataset is a demonstration, not real commercial or patient data. Observed revenue cannot establish demand, market potential, sales targets, representative effectiveness, or causes of a change. Product comparisons require two complete months in the selected date range; a monthly trend may include partial boundary months. AI recommendations are suggestions for investigation, not medical advice or automated decisions.
