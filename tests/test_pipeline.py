from datetime import date

import pytest
from langchain_core.language_models.fake_chat_models import FakeListChatModel

from pharma_insight.analytics import filter_options, query_dashboard, verified_facts
from pharma_insight.charts import monthly_chart, product_chart, region_chart
from pharma_insight.database import clean_sales, connect, load_database
from pharma_insight.generator import generate_csv
from pharma_insight.insights import (
    cloud_llm_insight, configured_api_key, offline_insight,
    safe_model_explanation,
    safe_qualitative_explanation,
)
from pharma_insight.qa import answer_question, choose_query, run_safe_tool


@pytest.fixture
def demo(tmp_path):
    csv_path = generate_csv(tmp_path / "sample.csv", count=300)
    db_path = tmp_path / "sample.sqlite3"
    report = load_database(csv_path, db_path)
    return csv_path, db_path, report


def test_cleaning_and_sql_integrity(demo):
    csv_path, db_path, report = demo
    clean, audit = clean_sales(csv_path)
    assert report == audit == {"raw_rows": 303, "accepted_rows": 300,
                               "invalid_rows": 2, "duplicate_rows": 1}
    assert clean["sale_id"].is_unique
    with connect(db_path) as connection:
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
        assert connection.execute("SELECT COUNT(*) FROM sales").fetchone()[0] == 300
        assert connection.execute("SELECT COUNT(*) FROM products").fetchone()[0] == 6
        assert connection.execute("SELECT COUNT(*) FROM reps").fetchone()[0] == 15


def test_filters_aggregations_and_rank(demo):
    _, db_path, _ = demo
    options = filter_options(db_path)
    all_data = query_dashboard(db_path, options["min_date"], options["max_date"])
    north = query_dashboard(db_path, options["min_date"], options["max_date"], region_ids=[1])
    north_one_product = query_dashboard(db_path, options["min_date"], options["max_date"],
                                        region_ids=[1], product_ids=[1])
    assert int(all_data["kpis"].iloc[0]["transactions"]) == 300
    assert int(north["kpis"].iloc[0]["transactions"]) < 300
    assert int(north_one_product["kpis"].iloc[0]["transactions"]) <= int(north["kpis"].iloc[0]["transactions"])
    assert north["regions"]["region_name"].tolist() == ["North"]
    assert set(north_one_product["products"]["product_name"]) == {"Cardivexa"}
    assert int(all_data["products"]["units"].sum()) == int(all_data["kpis"].iloc[0]["units"])
    assert all_data["reps"]["rank"].tolist() == list(range(1, 16))
    assert all_data["reps"]["revenue_inr"].is_monotonic_decreasing
    assert verified_facts(all_data)["transactions"] == 300


def test_empty_date_range_and_charts(demo):
    _, db_path, _ = demo
    empty = query_dashboard(db_path, date(2027, 1, 1), date(2027, 1, 31))
    assert verified_facts(empty)["transactions"] == 0
    populated = query_dashboard(db_path, date(2024, 1, 1), date(2025, 12, 31))
    assert len(monthly_chart(populated["monthly"]).data) == 1
    assert len(product_chart(populated["products"]).data) == 1
    assert len(region_chart(populated["regions"]).data) == 1


def test_offline_insight_and_langchain_pipeline(demo, monkeypatch):
    _, db_path, _ = demo
    facts = verified_facts(query_dashboard(db_path, date(2024, 1, 1), date(2025, 12, 31)))
    message = offline_insight(facts)
    assert facts["weakest_region"] in message
    assert f"₹{facts['revenue_inr']:,.2f}" in message

    captured = {}

    def fake_model(**kwargs):
        captured.update(kwargs)
        return FakeListChatModel(responses=[
            "- Revenue appears stronger in the latest period.\n"
            f"- {facts['weakest_region']} has the lowest revenue in this selection.\n"
            "- Review coverage and product mix before changing targets."
        ])

    monkeypatch.setattr("pharma_insight.insights.ChatOpenAI", fake_model)
    result, source = cloud_llm_insight(facts, "test-key")
    assert facts["weakest_region"] in result
    assert source.startswith("OpenAI explanation via LangChain")
    assert captured["api_key"] == "test-key"

    monkeypatch.setattr("pharma_insight.insights.ChatOpenAI", lambda **kwargs:
                        FakeListChatModel(responses=["Sales rose 12%."]))
    rejected, source = cloud_llm_insight(facts, "test-key")
    assert rejected == message
    assert "numerical claim" in source
    missing, source = cloud_llm_insight(facts, None)
    assert missing == message
    assert "key not configured" in source
    assert safe_model_explanation("Investigate regional coverage before changing targets.")
    assert not safe_model_explanation("Revenue rose twelve percent.")
    assert not safe_model_explanation("Revenue rose 12%.")
    cleaned = safe_qualitative_explanation(
        "- Check stock availability.\n- Only one region is in scope.\n- Review territory mix."
    )
    assert cleaned == "- Check stock availability.\n- Review territory mix."


def test_local_env_placeholder_and_key(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    env_path = tmp_path / ".env"
    env_path.write_text("OPENAI_API_KEY=PASTE_YOUR_OPENAI_API_KEY_HERE\n", encoding="utf-8")
    assert configured_api_key(env_path) is None
    env_path.write_text("OPENAI_API_KEY=local-test-value\n", encoding="utf-8")
    assert configured_api_key(env_path) == "local-test-value"


def test_safe_question_router_and_monthly_product_query(demo):
    _, db_path, _ = demo
    assert choose_query("Which medicine performed poorly last month?") == "product_movement"
    assert choose_query("Which region has lowest revenue?") == "regional_performance"
    assert choose_query("How did monthly sales change?") == "monthly_trend"
    assert choose_query("Tell me a joke") is None
    results = run_safe_tool("product_movement", db_path, date(2024, 1, 1),
                            date(2025, 12, 31), [], [])
    assert results["period"] in {"October 2025 vs November 2025",
                                  "November 2025 vs December 2025"}
    assert results["rows"] == sorted(results["rows"], key=lambda row: (row["change_inr"], row["product"]))
    assert any(row["status"] == "declined" for row in results["rows"])
    assert all(round(row["latest_revenue_inr"] - row["previous_revenue_inr"], 2)
               == row["change_inr"] for row in results["rows"])
    limited = run_safe_tool("product_movement", db_path, date(2024, 1, 1),
                            date(2025, 12, 31), [1], [1])
    assert {row["product"] for row in limited["rows"]} <= {"Cardivexa"}
    partial = run_safe_tool("product_movement", db_path, date(2024, 1, 1),
                            date(2025, 11, 15), [], [])
    assert partial["period"] == "September 2025 vs October 2025"
    too_short = run_safe_tool("product_movement", db_path, date(2025, 12, 1),
                              date(2025, 12, 31), [], [])
    assert not too_short["rows"]


def test_question_answer_uses_tool_facts_and_rejects_new_numbers(demo, monkeypatch):
    _, db_path, _ = demo
    monkeypatch.setattr("pharma_insight.insights.ChatOpenAI", lambda **kwargs:
                        FakeListChatModel(responses=["Review unit movement and territory mix before changing plans."]))
    response = answer_question("Which medicine performed poorly last month, and what should we do?",
                               db_path, date(2024, 1, 1), date(2025, 12, 31), [], [], "test-key")
    assert response["kind"] == "product_movement"
    assert response["rows"][0]["product"] in response["answer"]
    assert response["source"].startswith("LangChain + OpenAI")
    monkeypatch.setattr("pharma_insight.insights.ChatOpenAI", lambda **kwargs:
                        FakeListChatModel(responses=[f"{response['rows'][-1]['product']} declined."]))
    wrong_product = answer_question("Which medicine declined?", db_path, date(2024, 1, 1),
                                    date(2025, 12, 31), [], [], "test-key")
    assert "fact guard" in wrong_product["source"]
    monkeypatch.setattr("pharma_insight.insights.ChatOpenAI", lambda **kwargs:
                        FakeListChatModel(responses=["Revenue dropped 999%."]))
    guarded = answer_question("Which medicine declined?", db_path, date(2024, 1, 1),
                              date(2025, 12, 31), [], [], "test-key")
    assert "999" not in guarded["answer"]
    assert "fact guard" in guarded["source"]
    unsupported = answer_question("Tell me a joke", db_path, date(2024, 1, 1),
                                  date(2025, 12, 31), [], [], "test-key")
    assert unsupported["kind"] is None


def test_region_and_trend_tools_reconcile_to_dashboard(demo):
    _, db_path, _ = demo
    start, end = date(2024, 1, 1), date(2025, 12, 31)
    dashboard = query_dashboard(db_path, start, end, region_ids=[1])
    regions = run_safe_tool("regional_performance", db_path, start, end, [1], [])
    trend = run_safe_tool("monthly_trend", db_path, start, end, [1], [])
    expected_revenue = round(float(dashboard["kpis"].iloc[0]["revenue_inr"]), 2)
    assert [row["region"] for row in regions["rows"]] == ["North"]
    assert regions["rows"][0]["revenue_inr"] == expected_revenue
    assert round(sum(row["revenue_inr"] for row in trend["rows"]), 2) == expected_revenue
    assert sum(row["units"] for row in trend["rows"]) == int(dashboard["kpis"].iloc[0]["units"])
    answer = answer_question("Which region has the lowest revenue?", db_path, start, end,
                             [1], [], None)
    assert "Only North" in answer["answer"]


def test_bad_dates_rejected(demo):
    _, db_path, _ = demo
    with pytest.raises(ValueError):
        query_dashboard(db_path, date(2025, 1, 1), date(2024, 1, 1))
