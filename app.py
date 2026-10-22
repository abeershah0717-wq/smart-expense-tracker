
            
        m = df.assign(month=df["date"].dt.to_period("M").astype(str))
        piv = (m.pivot_table(index="month", columns="type", values="amount",
                             aggfunc="sum", fill_value=0)
               .reindex(columns=["Income", "Expense"], fill_value=0))
        monthly = piv.round(2).to_dict("index")
    return {
        "income": round(income, 2),
        "expense": round(expense, 2),
        "balance": round(income - expense, 2),
        "savings_rate": round((income - expense) / income * 100, 1) if income else None,
        "by_category": by_cat,
        "monthly": monthly,
        "n_entries": int(len(df)),
        "start": df["date"].min().date().isoformat() if not df.empty else None,
        "end": df["date"].max().date().isoformat() if not df.empty else None,
    }


def build_prompt(summary, currency):
    """Only aggregated data is sent to Gemini (no notes / raw rows)."""
    cats = "\n".join(f"- {k}: {currency}{v:,.2f}" for k, v in summary["by_category"].items()) or "- none"
    months = "\n".join(
        f"- {k}: income {currency}{v['Income']:,.2f}, expenses {currency}{v['Expense']:,.2f}"
        for k, v in summary["monthly"].items()) or "- none"
    rate = f"{summary['savings_rate']}%" if summary["savings_rate"] is not None else "n/a"
    return f"""You are a friendly, practical personal-finance coach.
Analyse this user's data ({summary['start']} to {summary['end']}, {summary['n_entries']} entries).

Total income: {currency}{summary['income']:,.2f}
Total expenses: {currency}{summary['expense']:,.2f}
Balance: {currency}{summary['balance']:,.2f}
Savings rate: {rate}

Expenses by category:
{cats}

Monthly totals:
{months}

Respond in markdown with exactly these sections:
### Spending patterns
(3-4 bullet points describing notable patterns/trends)
### Budgeting suggestions
(4-5 specific, actionable suggestions with target amounts or percentages)
### One quick win
(one thing they can do this week)

Be concise, specific to the numbers, non-judgmental. This is general guidance, not professional financial advice."""


def get_ai_summary(summary, currency, api_key, model=DEFAULT_MODEL):
    """Call Gemini and return markdown text. Raises on API failure."""
    from google import genai  # imported lazily so the app loads without a key

    client = genai.Client(api_key=api_key)
    resp = client.models.generate_content(model=model, contents=build_prompt(summary, currency))
    text = (resp.text or "").strip()
    if not text:
        raise RuntimeError("Gemini returned an empty response (it may have been blocked). Try again.")
    return text


def get_api_key():
    try:
        key = st.secrets.get("GEMINI_API_KEY")
    except Exception:  # no secrets.toml present
        key = None
    return key or os.getenv("GEMINI_API_KEY")


# ---------- UI ----------
def main():
    st.set_page_config(page_title="Expense Tracker + AI", page_icon="💰", layout="wide")
    st.title("💰 Expense Tracker with AI Budgeting")

    if "df" not in st.session_state:
        st.session_state.df = empty_df()
    df = st.session_state.df

    # Sidebar: add entries, settings, import/export
    with st.sidebar:
        st.header("➕ Add entry")
        currency = st.text_input("Currency symbol", value="$", max_chars=4)
        kind = st.radio("Type", ["Expense", "Income"], horizontal=True)
        with st.form("entry_form", clear_on_submit=True):
            d = st.date_input("Date", value=date.today())
            cat = st.selectbox("Category", EXPENSE_CATEGORIES if kind == "Expense" else INCOME_CATEGORIES)
            amount = st.number_input("Amount", min_value=0.0, step=1.0, format="%.2f")
            note = st.text_input("Note (optional)")
            if st.form_submit_button("Add", use_container_width=True):
                try:
                    st.session_state.df = add_entry(df, d, kind, cat, amount, note)
                    st.success("Entry added!")
                    st.rerun()
                except ValueError as e:
                    st.error(str(e))

        st.divider()
        st.header("💾 Your data")
        st.caption("Data lives only in this browser session. Download it to keep it.")
        if not df.empty:
            st.download_button("Download CSV", df.to_csv(index=False).encode("utf-8"),
                               "expenses.csv", "text/csv", use_container_width=True)
        up = st.file_uploader("Load CSV", type="csv")
        if up is not None and st.button("Load file", use_container_width=True):
            try:
                st.session_state.df = clean_df(pd.read_csv(io.BytesIO(up.getvalue())))
                st.rerun()
            except Exception as e:
                st.error(f"Could not load file: {e}")
        if st.button("Clear all data", use_container_width=True):
            st.session_state.df = empty_df()
            st.session_state.pop("ai_text", None)
            st.rerun()

    if df.empty:
        st.info("No data yet. Add your first expense or income from the sidebar 👈")
        return

    # Date filter
    min_d, max_d = df["date"].min().date(), df["date"].max().date()
    c1, c2 = st.columns(2)
    start = c1.date_input("From", min_d, min_value=min_d, max_value=max_d)
    end = c2.date_input("To", max_d, min_value=min_d, max_value=max_d)
    view = df[(df["date"].dt.date >= start) & (df["date"].dt.date <= end)]
    if view.empty:
        st.warning("No entries in that date range.")
        return

    s = compute_summary(view)
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Income", f"{currency}{s['income']:,.2f}")
    m2.metric("Expenses", f"{currency}{s['expense']:,.2f}")
    m3.metric("Balance", f"{currency}{s['balance']:,.2f}")
    m4.metric("Savings rate", f"{s['savings_rate']}%" if s["savings_rate"] is not None else "n/a")

    tab_charts, tab_totals, tab_data, tab_ai = st.tabs(
        ["📊 Charts", "🧾 Category totals", "📋 Entries", "🤖 AI suggestions"])

    exp = view[view["type"] == "Expense"]
    with tab_charts:
        left, right = st.columns(2)
        if exp.empty:
            left.info("No expenses to chart.")
        else:
            pie = px.pie(exp.groupby("category", as_index=False)["amount"].sum(),
                         names="category", values="amount", hole=0.4,
                         title="Spending by category")
            left.plotly_chart(pie, use_container_width=True)
        monthly = view.assign(month=view["date"].dt.to_period("M").astype(str)) \
                      .groupby(["month", "type"], as_index=False)["amount"].sum()
        bar = px.bar(monthly, x="month", y="amount", color="type", barmode="group",
                     title="Income vs expenses per month",
                     color_discrete_map={"Income": "#2e9e5b", "Expense": "#d9534f"})
        right.plotly_chart(bar, use_container_width=True)
        if not exp.empty:
            daily = exp.groupby(exp["date"].dt.date, as_index=False)["amount"].sum()
            daily.columns = ["date", "amount"]
            st.plotly_chart(px.line(daily, x="date", y="amount", markers=True,
                                    title="Daily spending"), use_container_width=True)

    with tab_totals:
        if exp.empty:
            st.info("No expenses in this range.")
        else:
            tot = exp.groupby("category", as_index=False)["amount"].sum() \
                     .sort_values("amount", ascending=False)
            tot["% of spending"] = (tot["amount"] / tot["amount"].sum() * 100).round(1)
            tot["amount"] = tot["amount"].round(2)
            st.dataframe(tot, use_container_width=True, hide_index=True)

    with tab_data:
        show = view.sort_values("date", ascending=False).copy()
        show["date"] = show["date"].dt.date
        st.dataframe(show, use_container_width=True)
        idx = st.number_input("Row number to delete (index in the table)", min_value=0,
                              max_value=int(df.index.max()), step=1)
        if st.button("Delete row"):
            if idx in st.session_state.df.index:
                st.session_state.df = st.session_state.df.drop(index=idx).reset_index(drop=True)
                st.rerun()

    with tab_ai:
        st.caption("Only totals (by category and month) are sent to Gemini, not your notes.")
        key = get_api_key() or st.text_input("Gemini API key", type="password",
                                             help="Get a free key at aistudio.google.com")
        model = st.text_input("Model", value=os.getenv("GEMINI_MODEL", DEFAULT_MODEL))
        if st.button("✨ Analyse my spending", type="primary"):
            if not key:
                st.error("Please provide a Gemini API key.")
            else:
                with st.spinner("Gemini is analysing your data..."):
                    try:
                        st.session_state.ai_text = get_ai_summary(s, currency, key, model)
                    except Exception as e:
                        st.error(f"AI request failed: {e}")
        if st.session_state.get("ai_text"):
            st.markdown(st.session_state.ai_text)


if __name__ == "__main__":
    main()
