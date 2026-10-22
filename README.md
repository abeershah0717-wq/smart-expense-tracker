# smart-expense-tracker# 💰 Expense Tracker with AI Budgeting

A Streamlit app where you log daily expenses and income, view spending charts and
category totals, and get AI-generated budgeting suggestions from Google Gemini Flash.

## Features
- Add income and expenses (date, category, amount, note)
- Summary metrics: income, expenses, balance, savings rate
- Charts: spending by category, income vs expenses per month, daily spending
- Category totals table with percentages and a date-range filter
- Gemini summary of spending patterns + budgeting suggestions
- CSV download/upload so you can keep your data
- Privacy: only aggregated totals are sent to Gemini, never your notes

## Run locally
```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Get a free key at https://aistudio.google.com/apikey
export GEMINI_API_KEY="your-key"   # Windows PowerShell: $env:GEMINI_API_KEY="your-key"
streamlit run app.py
```
You can also skip the env variable and paste the key into the AI tab.

Optional: use a different model with `GEMINI_MODEL` (default `gemini-2.5-flash`).

## Using secrets (recommended)
Create `.streamlit/secrets.toml` (never commit it):
```toml
GEMINI_API_KEY = "your-key"
```

## Note on data storage
Data is stored in the browser session only. Streamlit Community Cloud has no
persistent disk, so use **Download CSV** to save your data and **Load CSV** to restore it.

## Project files
- `app.py` – the app
- `requirements.txt` – dependencies
