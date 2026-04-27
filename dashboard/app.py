from __future__ import annotations

import os
from datetime import UTC, datetime
from typing import Any

import pandas as pd
import psycopg
import requests
import streamlit as st

STATS_URL = os.getenv("METERA_STATS_URL", "http://localhost:8000/stats/summary")
HEALTH_URL = os.getenv("METERA_HEALTH_URL", "http://localhost:8000/health")
DB_DSN = os.getenv("METERA_POLICY_STORE_DSN") or os.getenv("METERA_SEMANTIC_STORE_DSN")
EMBEDDER_MODEL = os.getenv("METERA_SEMANTIC_MODEL_NAME", "sentence-transformers/all-MiniLM-L6-v2")
AUTO_REFRESH_SECONDS = int(os.getenv("METERA_DASHBOARD_REFRESH_SECONDS", "15"))
SHADOW_TABLE_LIMIT = int(os.getenv("METERA_DASHBOARD_SHADOW_TABLE_LIMIT", "100"))
BRAND_GRADIENT = "linear-gradient(135deg, #0f172a 0%, #111827 45%, #1d4ed8 100%)"


@st.cache_data(ttl=15)
def load_stats_summary() -> dict[str, Any]:
    response = requests.get(STATS_URL, timeout=10)
    response.raise_for_status()
    return response.json()


@st.cache_data(ttl=15)
def load_health() -> dict[str, Any]:
    response = requests.get(HEALTH_URL, timeout=10)
    response.raise_for_status()
    return response.json()


@st.cache_data(ttl=15)
def load_shadow_analytics(limit: int = SHADOW_TABLE_LIMIT) -> pd.DataFrame:
    if not DB_DSN:
        return pd.DataFrame()
    query = """
        SELECT
            created_at,
            request_id,
            namespace,
            similarity_score,
            calculated_savings_usd,
            live_threshold,
            shadow_threshold
        FROM semantic_shadow_analytics
        ORDER BY created_at DESC
        LIMIT %s
    """
    with psycopg.connect(DB_DSN) as conn:
        return pd.read_sql_query(query, conn, params=(limit,))


@st.cache_data(ttl=15)
def load_shadow_savings_total() -> float:
    if not DB_DSN:
        return 0.0
    query = """
        SELECT COALESCE(SUM(calculated_savings_usd), 0.0) AS safety_tax_total
        FROM semantic_shadow_analytics
    """
    with psycopg.connect(DB_DSN) as conn:
        with conn.cursor() as cur:
            cur.execute(query)
            row = cur.fetchone()
            return float(row[0] or 0.0)


@st.cache_data(ttl=15)
def load_db_health() -> bool:
    if not DB_DSN:
        return False
    try:
        with psycopg.connect(DB_DSN) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                cur.fetchone()
        return True
    except Exception:
        return False


@st.cache_data(ttl=15)
def load_policy_thresholds() -> tuple[float, float]:
    if not DB_DSN:
        return 0.9, 0.8
    query = """
        SELECT overrides, semantic_shadow_threshold
        FROM admin_policy_overrides
        WHERE policy_name = 'default'
        LIMIT 1
    """
    try:
        with psycopg.connect(DB_DSN) as conn:
            with conn.cursor() as cur:
                cur.execute(query)
                row = cur.fetchone()
                if row is None:
                    return 0.9, 0.8
                overrides = row[0] or {}
                if isinstance(overrides, str):
                    import json

                    overrides = json.loads(overrides)
                live = float(overrides.get("semantic_threshold", 0.9))
                shadow = float(row[1] if row[1] is not None else overrides.get("semantic_shadow_threshold", 0.8))
                return live, shadow
    except Exception:
        return 0.9, 0.8



def get_realized_savings(stats: dict[str, Any]) -> float:
    return float(stats.get("costs_usd", {}).get("savings_total", 0.0))



def get_upstream_spend(stats: dict[str, Any]) -> float:
    return float(stats.get("costs_usd", {}).get("upstream_total", 0.0))



def get_hit_rate(stats: dict[str, Any]) -> float:
    return float(stats.get("requests", {}).get("cache_outcomes", {}).get("hit_rate", 0.0))



def get_cache_backend(stats: dict[str, Any]) -> str:
    backends = stats.get("cache_backends", {})
    if backends.get("redis", 0) > 0:
        return "Redis"
    if backends.get("memory", 0) > 0:
        return "Memory"
    return "Unknown"



def get_health_badges(stats: dict[str, Any], health: dict[str, Any], db_ok: bool) -> dict[str, str]:
    return {
        "embedder_status": "Healthy" if health.get("status") == "ok" else "Unavailable",
        "embedder_model": EMBEDDER_MODEL,
        "db_status": "Healthy" if db_ok else "Unavailable",
        "cache_backend": get_cache_backend(stats),
    }



def render_header() -> None:
    st.set_page_config(page_title="Metera Dashboard", layout="wide")
    st.markdown(
        f"""
        <style>
        .stApp {{
            background: #f8fafc;
        }}
        .metera-hero {{
            background: {BRAND_GRADIENT};
            color: white;
            padding: 1.5rem 1.75rem;
            border-radius: 18px;
            margin-bottom: 1rem;
            box-shadow: 0 12px 30px rgba(15, 23, 42, 0.18);
        }}
        .metera-hero h1 {{
            margin: 0;
            font-size: 2rem;
            font-weight: 700;
        }}
        .metera-hero p {{
            margin: 0.5rem 0 0 0;
            font-size: 1rem;
            opacity: 0.92;
        }}
        .metric-card {{
            background: white;
            border-radius: 18px;
            padding: 1rem 1.1rem;
            border: 1px solid #e2e8f0;
            box-shadow: 0 8px 24px rgba(15, 23, 42, 0.08);
        }}
        .metric-card .label {{
            color: #475569;
            font-size: 0.9rem;
            font-weight: 600;
            margin-bottom: 0.35rem;
        }}
        .metric-card .value {{
            color: #0f172a;
            font-size: 1.85rem;
            font-weight: 800;
            line-height: 1.1;
        }}
        .metric-card .hint {{
            color: #64748b;
            font-size: 0.82rem;
            margin-top: 0.4rem;
        }}
        .status-strip {{
            background: white;
            border: 1px solid #e2e8f0;
            border-radius: 14px;
            padding: 0.85rem 1rem;
            margin: 0.75rem 0 1rem 0;
            box-shadow: 0 6px 18px rgba(15, 23, 42, 0.05);
        }}
        .status-pill {{
            display: inline-block;
            background: #dbeafe;
            color: #1d4ed8;
            padding: 0.2rem 0.6rem;
            border-radius: 999px;
            font-size: 0.8rem;
            font-weight: 700;
            margin-right: 0.5rem;
        }}
        </style>
        <div class="metera-hero">
            <h1>Metera Dashboard — AI Cost Control Overview</h1>
            <p>Realized savings, unrealized safety-tax opportunity, and system health in one view.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )



def render_executive_cards(realized: float, safety_tax: float, upstream: float, hit_rate: float) -> None:
    c1, c2, c3, c4 = st.columns(4)
    cards = [
        (c1, "Realized Savings", f"${realized:,.6f}", "Value already captured through live caching"),
        (c2, "Safety Tax", f"${safety_tax:,.6f}", "Persisted shadow savings opportunity"),
        (c3, "Observed Upstream Cost", f"${upstream:,.6f}", "Spend still reaching the model provider"),
        (c4, "Cache Hit Rate", f"{hit_rate * 100:.2f}%", "Combined exact + semantic live hit rate"),
    ]
    for column, label, value, hint in cards:
        column.markdown(
            f"""
            <div class="metric-card">
                <div class="label">{label}</div>
                <div class="value">{value}</div>
                <div class="hint">{hint}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )



def render_financial_chart(realized: float, safety_tax: float) -> None:
    st.subheader("Realized Savings vs. Safety Tax")
    st.caption("Shadow mode quantifies what stricter production safety currently costs.")
    chart_df = pd.DataFrame(
        {
            "Category": ["Realized Savings", "Safety Tax"],
            "USD": [realized, safety_tax],
        }
    )
    st.bar_chart(chart_df.set_index("Category"))



def render_threshold_panel(live_threshold: float, shadow_threshold: float) -> None:
    st.subheader("Active Policy")
    c1, c2 = st.columns(2)
    c1.metric("Live Threshold", f"{live_threshold:.2f}")
    c2.metric("Shadow Threshold", f"{shadow_threshold:.2f}")
    st.caption(
        "Live threshold protects production accuracy. Shadow threshold measures lower-threshold opportunity without changing production responses."
    )



def render_health_row(badges: dict[str, str]) -> None:
    st.subheader("System Health")
    c1, c2, c3 = st.columns(3)
    c1.metric("Local Embedder", badges["embedder_status"])
    c1.caption(badges["embedder_model"])
    c2.metric("Postgres / pgvector", badges["db_status"])
    c3.metric("Exact Cache Backend", badges["cache_backend"])



def render_operational_metrics(stats: dict[str, Any]) -> None:
    st.subheader("Operational Metrics")
    left, right = st.columns(2)

    requests_block = stats.get("requests", {})
    outcomes = requests_block.get("cache_outcomes", {})
    semantic = stats.get("semantic", {})
    latency = stats.get("latency_ms", {})

    left.json(
        {
            "total_requests": requests_block.get("total", 0),
            "exact_hits": outcomes.get("exact_hits", 0),
            "semantic_hits": outcomes.get("semantic_hits", 0),
            "misses": outcomes.get("misses", 0),
            "semantic_candidates_indexed": semantic.get("candidates_indexed", 0),
            "shadow_hits": semantic.get("shadow_hits", 0),
            "shadow_logs_written": semantic.get("shadow_logs_written", 0),
        }
    )

    right.json(
        {
            "overall_avg_latency_ms": latency.get("overall", {}).get("avg", 0.0),
            "upstream_avg_latency_ms": latency.get("upstream", {}).get("avg", 0.0),
            "semantic_hit_avg_latency_ms": latency.get("semantic_hit", {}).get("avg", 0.0),
            "overall_max_latency_ms": latency.get("overall", {}).get("max", 0.0),
        }
    )



def render_shadow_table(rows: pd.DataFrame) -> None:
    st.subheader("Shadow Analytics Evidence")
    if rows.empty:
        st.info("No shadow analytics rows available.")
        return
    st.dataframe(rows, use_container_width=True, hide_index=True)



def render_status_strip(*, db_ok: bool, cache_backend: str, live_threshold: float, shadow_threshold: float) -> None:
    db_label = "DB Healthy" if db_ok else "DB Unavailable"
    st.markdown(
        f"""
        <div class="status-strip">
            <span class="status-pill">Read-only</span>
            <span class="status-pill">{db_label}</span>
            <span class="status-pill">Cache: {cache_backend}</span>
            <span class="status-pill">Live {live_threshold:.2f}</span>
            <span class="status-pill">Shadow {shadow_threshold:.2f}</span>
            <div style="margin-top:0.55rem;color:#475569;font-size:0.9rem;">
                Last refresh: {datetime.now(UTC).isoformat()} • Local embedder model: {EMBEDDER_MODEL}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )



def render_footer() -> None:
    st.markdown("---")
    st.caption("See docs: ENGINEERING_VALIDATION.md, ECONOMIC_IMPACT.md, SECURITY_GOVERNANCE.md")



def main() -> None:
    render_header()

    with st.sidebar:
        st.markdown("## Metera")
        st.caption("Financial Control Panel")
        st.write("Use this dashboard to track realized savings, Safety Tax, and system health without changing live policy.")
        st.write(f"Auto-refresh target: {AUTO_REFRESH_SECONDS}s cache TTL")
        if st.button("Refresh now", use_container_width=True):
            st.cache_data.clear()
            st.rerun()
        st.info("Read-only dashboard. No write controls or threshold toggles are enabled in this version.")

    stats = load_stats_summary()
    health = load_health()
    db_ok = load_db_health()
    rows = load_shadow_analytics()

    realized = get_realized_savings(stats)
    safety_tax = load_shadow_savings_total()
    upstream = get_upstream_spend(stats)
    hit_rate = get_hit_rate(stats)
    live_threshold, shadow_threshold = load_policy_thresholds()
    badges = get_health_badges(stats, health, db_ok)

    render_status_strip(
        db_ok=db_ok,
        cache_backend=badges["cache_backend"],
        live_threshold=live_threshold,
        shadow_threshold=shadow_threshold,
    )
    render_executive_cards(realized, safety_tax, upstream, hit_rate)
    st.markdown("---")
    render_financial_chart(realized, safety_tax)
    st.markdown("---")
    render_threshold_panel(live_threshold, shadow_threshold)
    st.markdown("---")
    render_health_row(badges)
    st.markdown("---")
    render_operational_metrics(stats)
    st.markdown("---")
    render_shadow_table(rows)
    render_footer()


if __name__ == "__main__":
    main()
