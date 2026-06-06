"""
Credit Scoring UI — Streamlit frontend for the FastAPI /predict endpoint.

Layout:
  Left column  : Input form (grouped into 4 sections)
  Right column : Results (decision badge, score gauge, breakdown chart)
"""
import os

import requests
import streamlit as st

API_URL = os.getenv("API_URL", "http://localhost:8000")

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Credit Scoring",
    page_icon="💳",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.title("💳 Credit Scoring System")
st.caption(f"Model API: `{API_URL}` · Scorecard WOE-LR with full interpretability")

# ── Input form ────────────────────────────────────────────────────────────────
left, right = st.columns([1, 1], gap="large")

with left:
    st.subheader("Customer Information")

    with st.expander("🏦 Loan Portfolio", expanded=True):
        c1, c2 = st.columns(2)
        n_loans       = c1.number_input("Total loans",              min_value=0, max_value=50, value=3, step=1)
        n_loans_nb    = c2.number_input("Loans (non-bank)",         min_value=0, max_value=50, value=1, step=1)
        st_bank       = c1.number_input("Short-term loans (bank)",  min_value=0, max_value=30, value=1, step=1)
        st_non_bank   = c2.number_input("Short-term loans (non-bank)", min_value=0, max_value=30, value=0, step=1)

    with st.expander("💳 Credit Cards & Relationships", expanded=True):
        c1, c2 = st.columns(2)
        n_cc          = c1.number_input("Credit cards (total)",     min_value=0, max_value=20, value=2, step=1)
        n_cc_bank     = c2.number_input("Credit cards (bank)",      min_value=0, max_value=20, value=2, step=1)
        n_rel_bank    = c1.number_input("Relationships (bank)",     min_value=0, max_value=20, value=3, step=1)
        n_rel_non     = c2.number_input("Relationships (non-bank)", min_value=0, max_value=20, value=1, step=1)

    with st.expander("📈 Recent Activity (last 3–6 months)", expanded=True):
        c1, c2 = st.columns(2)
        new_loan_3m   = c1.number_input("New loans taken (3M)",  min_value=0, max_value=20, value=0, step=1)
        new_loan_6m   = c2.number_input("New loans taken (6M)",  min_value=0, max_value=20, value=0, step=1)
        enq_3m        = c1.number_input("Credit enquiries (3M)", min_value=0, max_value=50, value=2, step=1)
        enq_6m        = c2.number_input("Credit enquiries (6M)", min_value=0, max_value=50, value=3, step=1)

    with st.expander("💰 Outstanding Balances (VND)", expanded=True):
        bal_loan = st.number_input(
            "Outstanding loan balance (current)",
            min_value=0, max_value=10_000_000_000, value=50_000_000,
            step=1_000_000, format="%d",
        )
        bal_all = st.number_input(
            "Outstanding balance — all products (current)",
            min_value=0, max_value=10_000_000_000, value=55_000_000,
            step=1_000_000, format="%d",
        )

    submitted = st.button("🔍 Score this customer", type="primary", use_container_width=True)

# ── Results panel ─────────────────────────────────────────────────────────────
with right:
    st.subheader("Scoring Result")

    if not submitted:
        st.info("Fill in the customer details on the left and click **Score this customer**.")
        st.stop()

    payload = {
        "NUMBER_OF_LOANS":               n_loans,
        "NUMBER_OF_LOANS_NON_BANK":      n_loans_nb,
        "SHORT_TERM_COUNT_BANK":         st_bank,
        "SHORT_TERM_COUNT_NON_BANK":     st_non_bank,
        "NUMBER_OF_CREDIT_CARDS":        n_cc,
        "NUMBER_OF_CREDIT_CARDS_BANK":   n_cc_bank,
        "NUMBER_OF_RELATIONSHIP_BANK":   n_rel_bank,
        "NUMBER_OF_RELATIONSHIP_NON_BANK": n_rel_non,
        "NUM_NEW_LOAN_TAKEN_3M":         new_loan_3m,
        "NUM_NEW_LOAN_TAKEN_6M":         new_loan_6m,
        "ENQUIRIES_3M":                  enq_3m,
        "ENQUIRIES_6M":                  enq_6m,
        "OUTSTANDING_BAL_LOAN_CURRENT":  bal_loan,
        "OUTSTANDING_BAL_ALL_CURRENT":   bal_all,
    }

    with st.spinner("Calling scoring API…"):
        try:
            resp = requests.post(f"{API_URL}/predict", json=payload, timeout=30)
            resp.raise_for_status()
            data = resp.json()
        except requests.exceptions.ConnectionError:
            st.error(f"Cannot reach API at `{API_URL}`. Is the API container running?")
            st.stop()
        except Exception as exc:
            st.error(f"API error: {exc}")
            if resp is not None:
                st.code(resp.text)
            st.stop()

    # ── Decision badge ────────────────────────────────────────────────────────
    decision  = data["decision"]
    risk_band = data["risk_band"]
    prob      = data["default_probability"]
    score     = data["credit_score"]
    sc_score  = data.get("scorecard_score")
    breakdown = data.get("scorecard_breakdown") or []

    DECISION_COLOR = {
        "approve":       ("#1a7a4a", "✅ APPROVED"),
        "manual_review": ("#b45309", "⚠️ MANUAL REVIEW"),
        "reject":        ("#b91c1c", "❌ REJECTED"),
    }
    BAND_COLOR = {
        "Excellent": "#1a7a4a",
        "Good":      "#2563eb",
        "Fair":      "#b45309",
        "Poor":      "#dc2626",
        "Very Poor": "#7f1d1d",
    }

    bg, label = DECISION_COLOR[decision]
    st.markdown(
        f"""<div style="background:{bg};color:white;padding:16px 24px;border-radius:8px;
        font-size:1.4rem;font-weight:700;text-align:center;margin-bottom:16px">
        {label}</div>""",
        unsafe_allow_html=True,
    )

    # ── Key metrics row ───────────────────────────────────────────────────────
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Credit Score", score, help="300–850; higher = safer customer")
    m2.metric("Default Probability", f"{prob:.1%}", help="Model's P(default)")
    m3.metric("Risk Band", risk_band)
    if sc_score is not None:
        m4.metric("Scorecard Score", f"{sc_score:.1f}", help="WOE-based scorecard raw value")

    # ── Score gauge (progress bar) ────────────────────────────────────────────
    band_color = BAND_COLOR.get(risk_band, "#6b7280")
    pct = (score - 300) / (850 - 300)
    st.markdown(f"""
    <div style="margin:8px 0 16px 0">
      <div style="display:flex;justify-content:space-between;font-size:0.75rem;color:#6b7280">
        <span>300 — Very Poor</span><span>580 — Fair</span><span>850 — Excellent</span>
      </div>
      <div style="background:#e5e7eb;border-radius:99px;height:12px;margin-top:4px">
        <div style="background:{band_color};width:{pct*100:.1f}%;height:12px;border-radius:99px"></div>
      </div>
    </div>""", unsafe_allow_html=True)

    # ── Scorecard breakdown ───────────────────────────────────────────────────
    if breakdown:
        st.markdown("#### Score contribution by feature")
        st.caption("Negative = raises risk (lowers score) · Positive = lowers risk (raises score)")

        import pandas as pd

        df = pd.DataFrame(breakdown)[["feature", "bin", "raw_value", "woe", "score_contribution", "iv"]]
        df.columns = ["Feature", "Bin", "Value", "WOE", "Score Δ", "IV"]

        # Color-coded bar chart
        bar_df = df[["Feature", "Score Δ"]].set_index("Feature")
        bar_df["color"] = bar_df["Score Δ"].apply(lambda x: "positive" if x >= 0 else "negative")
        st.bar_chart(bar_df["Score Δ"], use_container_width=True, height=280)

        # Detailed table
        with st.expander("Detailed breakdown table", expanded=False):
            st.dataframe(
                df.style
                  .format({"Value": "{:.2f}", "WOE": "{:.4f}", "Score Δ": "{:+.2f}", "IV": "{:.4f}"})
                  .background_gradient(subset=["Score Δ"], cmap="RdYlGn", vmin=-80, vmax=80),
                use_container_width=True,
                hide_index=True,
            )
    else:
        st.info("Breakdown only available for the **scorecard** model alias.")

    # ── Model version footer ──────────────────────────────────────────────────
    st.caption(f"Model: `{data['model_version']}` · Latency: {data['latency_ms']:.0f} ms")
