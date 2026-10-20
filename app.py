"""Local Streamlit dashboard for synthetic pharmaceutical sales."""

import json

import streamlit as st

from pharma_insight.analytics import filter_options, query_dashboard, verified_facts
from pharma_insight.charts import monthly_chart, product_chart, region_chart
from pharma_insight.insights import DEFAULT_MODEL, cloud_llm_insight, configured_api_key, offline_insight
from pharma_insight.qa import EXAMPLES, answer_question
from pharma_insight.setup import DB_PATH, ROOT, ensure_demo_data


st.set_page_config(page_title="PharmaInsight AI", page_icon="📊", layout="wide")
if "ai_result" not in st.session_state:
    st.session_state.ai_result = None
if "qa_history" not in st.session_state:
    st.session_state.qa_history = []

try:
    setup_report = ensure_demo_data()
    options = filter_options(DB_PATH)
except Exception as exc:
    st.error(f"The local sample database could not be prepared: {exc}")
    st.stop()

st.title("PharmaInsight AI")
st.caption("Pharmaceutical commercial analytics · India demo · synthetic transactions only")
st.info("All products, people, transactions, and business figures in this demo are fictional. Currency: INR.", icon="ℹ️")

if setup_report:
    st.success(f"Demo data loaded: {setup_report['accepted_rows']:,} valid transactions; "
               f"{setup_report['invalid_rows']} invalid and {setup_report['duplicate_rows']} duplicate rows excluded.")

with st.sidebar:
    st.header("Filters")
    selection = st.date_input("Sale date", value=(options["min_date"], options["max_date"]),
                              min_value=options["min_date"], max_value=options["max_date"])
    region_map = dict(zip(options["regions"].region_name, options["regions"].region_id))
    product_map = dict(zip(options["products"].product_name, options["products"].product_id))
    selected_regions = st.multiselect("Region", list(region_map), help="Empty means all regions")
    selected_products = st.multiselect("Product", list(product_map), help="Empty means all products")
    st.divider()
    st.caption("SQL runs inside this app. Your question and aggregate synthetic results go to OpenAI only when you ask a supported question.")

if not isinstance(selection, (tuple, list)) or len(selection) != 2:
    st.warning("Select both a start and an end date.")
    st.stop()

start, end = selection
region_ids = [int(region_map[name]) for name in selected_regions]
product_ids = [int(product_map[name]) for name in selected_products]
try:
    data = query_dashboard(DB_PATH, start, end, region_ids, product_ids)
    facts = verified_facts(data)
except Exception as exc:
    st.error(f"Analytics query failed: {exc}")
    st.stop()

metric_a, metric_b, metric_c = st.columns(3)
metric_a.metric("Total revenue", f"₹{facts['revenue_inr']:,.2f}", border=True)
metric_b.metric("Units sold", f"{facts['units']:,}", border=True)
metric_c.metric("Transactions", f"{facts['transactions']:,}", border=True)

if facts["transactions"] == 0:
    st.warning("No sales match these filters. Change a region, product, or date range.")
    st.stop()

overview, team, assistant, insight, method = st.tabs(
    ["Overview", "Sales team", "Ask the data", "Business insights", "How it works"])
with overview:
    st.subheader("Monthly sales trend")
    st.plotly_chart(monthly_chart(data["monthly"]), width="stretch", key="monthly",
                    alt="Monthly revenue trend for the selected sales")
    left, right = st.columns(2)
    with left:
        st.subheader("Top products")
        st.plotly_chart(product_chart(data["products"]), width="stretch", key="products",
                        alt="Revenue of the top products in the selected sales")
    with right:
        st.subheader("Regional performance")
        st.plotly_chart(region_chart(data["regions"]), width="stretch", key="regions",
                        alt="Revenue by region for the selected sales")

with team:
    st.subheader("Sales representative ranking")
    st.caption("Ranked by revenue within the current filters. These are fictional representatives.")
    st.dataframe(data["reps"], width="stretch", hide_index=True,
                 alt="Sales representatives ranked by revenue",
                 column_config={"revenue_inr": st.column_config.NumberColumn("Revenue (₹)", format="₹%.2f")})
    st.subheader("Regional detail")
    st.dataframe(data["regions"], width="stretch", hide_index=True,
                 alt="Regional revenue, units, and transaction totals")

with assistant:
    st.subheader("Ask PharmaInsight")
    st.caption("Ask about product movement, regional performance, or monthly trends. Questions use the date, region, and product filters in the sidebar. Each answer uses a predefined SQL query.")
    st.markdown("**Try:** " + " · ".join(EXAMPLES))
    api_key = configured_api_key(ROOT / ".env")
    if not api_key:
        st.info("Add your OpenAI key to the project's .env file for AI explanations. Verified SQL summaries still work.")
    qa_signature = json.dumps({"start": str(start), "end": str(end),
                               "regions": region_ids, "products": product_ids}, sort_keys=True)
    if st.session_state.get("qa_signature") != qa_signature:
        st.session_state.qa_history = []
        st.session_state.qa_signature = qa_signature
    question = st.chat_input("Ask a sales question", max_chars=500)
    if question:
        with st.spinner("Checking the sales data and preparing an answer..."):
            try:
                response = answer_question(question, DB_PATH, start, end,
                                           region_ids, product_ids, api_key)
            except Exception as exc:
                response = {"answer": "The sales query could not be completed. Please try another selection.",
                            "source": f"Query error: {type(exc).__name__}", "rows": [], "period": ""}
        st.session_state.qa_history.append({"question": question, "response": response})
        st.session_state.qa_history = st.session_state.qa_history[-5:]
    for item in st.session_state.qa_history:
        with st.chat_message("user"):
            st.write(item["question"])
        with st.chat_message("assistant"):
            response = item["response"]
            st.write(response["answer"])
            if response.get("rows"):
                st.caption(f"Verified data · {response['period']}")
                st.dataframe(response["rows"], width="stretch", hide_index=True,
                             alt="Verified sales figures used for this answer",
                             column_config={
                                 "product": "Medicine",
                                 "region": "Region",
                                 "previous_revenue_inr": st.column_config.NumberColumn("Previous revenue (₹)", format="₹%.2f"),
                                 "latest_revenue_inr": st.column_config.NumberColumn("Latest revenue (₹)", format="₹%.2f"),
                                 "change_inr": st.column_config.NumberColumn("Revenue change (₹)", format="₹%.2f"),
                                 "change_pct": st.column_config.NumberColumn("Change (%)", format="%.1f%%"),
                                 "revenue_inr": st.column_config.NumberColumn("Revenue (₹)", format="₹%.2f"),
                             })
            if response.get("note"):
                st.caption(response["note"])
            st.caption(response["source"])

with insight:
    st.subheader("AI business insights")
    st.caption("SQL computes every figure. LangChain sends only the verified aggregate facts for an optional explanation.")
    a, b, c = st.columns(3)
    a.metric("Leading product", facts["top_product"], border=True)
    b.metric("Highest revenue region" if facts["regions_in_scope"] > 1 else "Region in view",
             facts["strongest_region"], border=True)
    c.metric("Lowest revenue region" if facts["regions_in_scope"] > 1 else "Regional comparison",
             facts["weakest_region"] if facts["regions_in_scope"] > 1 else "Select more regions",
             border=True)
    st.caption(f"Model: {DEFAULT_MODEL}. Clicking the button sends only these synthetic aggregate facts to OpenAI.")
    if not api_key:
        st.info("Add your OpenAI key to the project's .env file, then refresh this page.")
        st.session_state.ai_result = None
    signature = json.dumps({"facts": facts, "model": DEFAULT_MODEL}, sort_keys=True)
    if st.session_state.ai_result and st.session_state.ai_result["signature"] != signature:
        st.session_state.ai_result = None
    if st.button("Generate AI explanation", type="primary", icon=":material/auto_awesome:",
                 disabled=not bool(api_key)):
        with st.spinner("Asking OpenAI to explain the verified facts..."):
            explanation, source = cloud_llm_insight(facts, api_key)
        st.session_state.ai_result = {"signature": signature, "text": explanation, "source": source}
    result = st.session_state.ai_result
    explanation = result["text"] if result else offline_insight(facts)
    source = result["source"] if result else "Offline summary — add a key and generate an AI explanation"
    if source.startswith("Offline summary ("):
        st.warning(source)
    else:
        st.caption(source)
    st.markdown(explanation)
    st.caption("Suggestions are hypotheses for investigation. Revenue alone does not establish demand, rep effectiveness, or causality.")

with method:
    st.subheader("Data flow")
    st.markdown("Synthetic CSV → Pandas validation → normalized SQLite tables → filtered SQL aggregations → Plotly charts → verified facts → LangChain explanation")
    st.markdown("**Q&A:** A fixed question router selects one read-only SQL tool for product movement, regional performance, or monthly trend. LangChain passes its aggregate result to OpenAI for a short explanation and recommendations.")
    st.markdown("**SQL used:** JOINs connect sales to product, region, and representative tables; GROUP BY produces summaries; a window function ranks reps.")
    st.code("""WITH rep_totals AS (
    SELECT rep.rep_name, SUM(s.revenue_paise) / 100.0 AS revenue_inr
    FROM sales s JOIN reps rep ON s.rep_id = rep.rep_id
    GROUP BY rep.rep_id, rep.rep_name
)
SELECT ROW_NUMBER() OVER (ORDER BY revenue_inr DESC) AS rank,
       rep_name, revenue_inr FROM rep_totals;""", language="sql")
    st.caption("Source data is synthetic. OpenAI receives your question and aggregate verified facts when you ask for AI help, never raw transaction rows.")
