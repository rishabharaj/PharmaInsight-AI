"""Grounded AI explanations through LangChain, with an offline fallback."""

import json
import os
import re
from pathlib import Path

from dotenv import dotenv_values
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI


DEFAULT_MODEL = "gpt-6-luna"


_NUMERICAL_LANGUAGE = re.compile(
    r"[0-9₹$%]|\b(?:zero|one|two|three|four|five|six|seven|eight|nine|ten|"
    r"eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|"
    r"twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety|hundred|thousand|"
    r"million|billion|lakh|crore|percent|percentage|first|second|third|fourth|"
    r"fifth|sixth|seventh|eighth|ninth|tenth|half|quarter|double|triple|twice)\b",
    re.IGNORECASE,
)


def safe_model_explanation(answer: str) -> bool:
    """Keep numerical reporting in the verified dashboard, not generated prose."""
    return bool(answer.strip()) and len(answer) <= 1400 and not _NUMERICAL_LANGUAGE.search(answer)


def configured_api_key(env_path: Path) -> str | None:
    """Read a local process variable or .env without exposing the value in output."""
    local_values = dotenv_values(env_path) if env_path.exists() else {}
    for candidate in (os.getenv("OPENAI_API_KEY"), local_values.get("OPENAI_API_KEY")):
        value = (candidate or "").strip()
        if value and not value.startswith("PASTE_"):
            return value
    return None


def chat_model(api_key: str):
    """Create the one configured OpenAI model for both AI features."""
    return ChatOpenAI(model=DEFAULT_MODEL, api_key=api_key, timeout=40,
                      max_retries=1, use_responses_api=False, reasoning_effort="none")


def offline_insight(facts: dict) -> str:
    if not facts.get("transactions"):
        return "No sales match these filters. Widen the date, product, or region selection."
    lines = [f"**Portfolio:** {facts['transactions']:,} transactions produced ₹{facts['revenue_inr']:,.2f} from {facts['units']:,} units."]
    if facts.get("regions_in_scope", 0) > 1:
        lines.append(
            f"**Regional opportunity:** {facts['weakest_region']} has the lowest filtered revenue "
            f"(₹{facts['weakest_region_revenue_inr']:,.2f}); {facts['strongest_region']} leads "
            f"(₹{facts['strongest_region_revenue_inr']:,.2f}). Review coverage and product mix before changing targets."
        )
    else:
        lines.append(f"**Regional context:** Only {facts['strongest_region']} is in view. "
                     "Widen the region filter before comparing territories.")
    lines.append(f"**Product focus:** {facts['top_product']} leads at ₹{facts['top_product_revenue_inr']:,.2f}. "
                 "Check whether its demand pattern is repeatable across regions.")
    if "month_change_pct" in facts:
        direction = "rose" if facts["month_change_pct"] >= 0 else "fell"
        lines.append(
            f"**Recent movement:** Revenue {direction} {abs(facts['month_change_pct']):.1f}% "
            f"from {facts['previous_month']} to {facts['latest_month']}. "
            "Check period completeness and product mix before interpreting this as a sustained trend."
        )
    return "\n\n".join(lines)


def cloud_llm_insight(facts: dict, api_key: str | None) -> tuple[str, str]:
    """Explain SQL facts through LangChain; never generate metrics."""
    fallback = offline_insight(facts)
    if not facts.get("transactions"):
        return fallback, "Offline summary"
    if not api_key:
        return fallback, "Offline summary (API key not configured)"
    try:
        prompt = ChatPromptTemplate.from_messages([
            ("system", "You are a commercial analytics assistant. All data is synthetic. "
             "Use only the verified JSON facts. Write short qualitative bullet points about the "
             "trend, regional context, and business action. If regions_in_scope is one, do not "
             "claim that region is weak compared with others. Describe possible explanations as hypotheses, "
             "never as proven causes. Do not include any numbers, percentages, dates, currencies, "
             "or numerical words; the dashboard shows verified numbers separately. "
             "Use hyphen bullets, not numbered bullets. Never invent metrics, external market facts, "
             "or medical advice."),
            ("human", "Verified facts: {facts}"),
        ])
        chain = prompt | chat_model(api_key) | StrOutputParser()
        answer = chain.invoke({"facts": json.dumps(facts, sort_keys=True)})
        # Reject a response with numerical claims; verified quantities remain in the UI.
        if not safe_model_explanation(answer):
            return fallback, "Offline summary (AI output contained a numerical claim or was malformed)"
        return answer.strip(), f"OpenAI explanation via LangChain · {DEFAULT_MODEL}"
    except Exception as exc:
        # Avoid displaying exception messages because SDK errors can contain credentials.
        return fallback, f"Offline summary (API request failed: {type(exc).__name__})"
