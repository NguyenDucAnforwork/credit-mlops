"""
Credit Scoring UI — Streamlit frontend for the FastAPI /predict endpoint.

Two input modes:
  Mode A — load a REAL row from test_data.csv by ground-truth label + index, and send
           ALL of its non-null features (the full ~109-feature payload). This reproduces
           the API/harness results and lets you compare the model decision against the
           ground-truth label.
  Mode B — manual entry of the 14 headline features (quick test). This is a PARTIAL
           input: the other ~108 features are left null and KNN-imputed, so the
           probability will differ from the full-row result for the same customer.
"""
import os
import math

import requests
import streamlit as st

API_URL = os.getenv("API_URL", "http://localhost:8000")
# Mode A reads this CSV directly (mounted read-only into the container at /data).
# Falls back to the repo-relative path for local `streamlit run`.
TEST_DATA_PATH = os.getenv("TEST_DATA_PATH", "data/processed/test_data.csv")
_FALLBACK_TEST_DATA = "../data/processed/test_data.csv"

# Winsorizer bounds learned from training data.
# Values outside [lower, upper] are clipped to the nearest bound before scoring.
# ⚠️  The effective range is very narrow — likely a unit mismatch in training data
#     (balance may have been stored in a different scale). See reports/debug_workflows.md.
BAL_LOAN_BOUNDS = (1_000_000, 1_001_790)
BAL_ALL_BOUNDS  = (1_000_000, 1_002_770)

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Credit Scoring",
    page_icon="💳",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("💳 Credit Scoring System")


@st.cache_data(show_spinner=False)
def load_test_data():
    """Load test_data.csv for Mode A. Returns (DataFrame, path) or (None, tried_paths)."""
    import pandas as pd
    tried = []
    for path in (TEST_DATA_PATH, _FALLBACK_TEST_DATA):
        tried.append(path)
        if os.path.exists(path):
            df = pd.read_csv(path)
            return df, path
    return None, tried


def row_to_payload(row):
    """All non-null feature columns of a test_data.csv row, cast to float.
    Mirrors the harness exactly: drop NaN + the label column."""
    payload = {}
    for k, v in row.drop(labels=["label"]).to_dict().items():
        if isinstance(v, float) and math.isnan(v):
            continue
        payload[k] = float(v)
    return payload


# ── Sidebar: model/source selector ───────────────────────────────────────────
with st.sidebar:
    st.header("Model Settings")
    model_option = st.selectbox(
        "Model alias",
        ["scorecard", "champion", "challenger"],
        index=0,
        help=(
            "**scorecard** — WOE + LR, full breakdown (recommended)\n\n"
            "**champion** — XGBoost, highest AUC (0.822)\n\n"
            "**challenger** — LR + SMOTE baseline"
        ),
    )
    source_option = st.selectbox(
        "Registry source",
        ["auto", "local", "dagshub"],
        index=0,
        help=(
            "**auto** — try DagsHub registry, fall back to local if offline\n\n"
            "**local** — offline mode; uses local joblib artifact\n\n"
            "**dagshub** — require DagsHub; returns 503 if unavailable"
        ),
    )
    st.caption(f"Active: `{model_option}` · source: `{source_option}`")
    st.divider()
    st.caption(f"API: `{API_URL}`")

st.caption(f"API: `{API_URL}` · model: `{model_option}` · source: `{source_option}`")

# ── Input-mode toggle ─────────────────────────────────────────────────────────
mode = st.radio(
    "Input mode",
    [
        "🅰️  Mode A — Load a real row from test_data.csv (full features)",
        "🅱️  Mode B — Manual entry (14 fields, quick test)",
    ],
    index=1,
    help=(
        "**Mode A** sends ALL non-null features of a real applicant → matches the "
        "API/harness numbers and shows ground-truth vs model decision.\n\n"
        "**Mode B** sends only 14 fields (partial input) → fast, but the probability "
        "differs from the full-row result for the same customer."
    ),
)
is_mode_a = mode.startswith("🅰️")

# Shared state populated by whichever mode is active.
payload = None
submitted = False
ground_truth = None   # int 0/1 in Mode A, None in Mode B

left, right = st.columns([1, 1], gap="large")

# ── Left column: inputs ─────────────────────────────────────────────────────
with left:
    if is_mode_a:
        st.subheader("Load a real applicant")
        df_test, info = load_test_data()
        if df_test is None:
            st.error(
                "`test_data.csv` not found (Mode A). Tried: "
                + ", ".join(f"`{p}`" for p in info)
                + ".\n\nIn Docker it is mounted at `/data/processed/test_data.csv` "
                "(via the `./data:/data:ro` volume). Use Mode B instead, or check the mount."
            )
            st.stop()

        n_def  = int((df_test["label"] == 1).sum())
        n_good = int((df_test["label"] == 0).sum())
        st.caption(f"Loaded `{info}` — {len(df_test):,} rows ({n_def} defaulters, {n_good} good).")

        gt_label = st.selectbox(
            "Ground-truth label",
            [1, 0],
            index=0,
            format_func=lambda v: ("1 — DEFAULT (bad customer)" if v == 1
                                    else "0 — GOOD (repaid)"),
            help="Picks rows whose true outcome is this label, so you can compare it "
                 "against the model's decision.",
        )
        subset = df_test[df_test["label"] == gt_label].reset_index(drop=True)
        idx = st.number_input(
            f"Row index within label={gt_label} subset  (0 – {len(subset) - 1})",
            min_value=0, max_value=len(subset) - 1, value=0, step=1,
            help="The index is positional WITHIN the chosen label's rows — "
                 "e.g. label=1, index=0 is the first defaulter in the test set.",
        )

        row = subset.iloc[int(idx)]
        payload = row_to_payload(row)
        st.caption(f"This applicant has **{len(payload)} non-null features** (of 122).")

        # Preview the 14 headline features so the user sees what they're scoring.
        with st.expander("Preview headline features of this row", expanded=False):
            import pandas as pd
            UI14 = ["NUMBER_OF_LOANS", "NUMBER_OF_LOANS_NON_BANK", "SHORT_TERM_COUNT_BANK",
                    "SHORT_TERM_COUNT_NON_BANK", "NUMBER_OF_CREDIT_CARDS",
                    "NUMBER_OF_CREDIT_CARDS_BANK", "NUMBER_OF_RELATIONSHIP_BANK",
                    "NUMBER_OF_RELATIONSHIP_NON_BANK", "NUM_NEW_LOAN_TAKEN_3M",
                    "NUM_NEW_LOAN_TAKEN_6M", "ENQUIRIES_3M", "ENQUIRIES_6M",
                    "OUTSTANDING_BAL_LOAN_CURRENT", "OUTSTANDING_BAL_ALL_CURRENT"]
            preview = pd.DataFrame(
                [(f, row[f] if f in row else None) for f in UI14],
                columns=["Feature", "Value"],
            )
            st.dataframe(preview, use_container_width=True, hide_index=True)

        ground_truth = int(gt_label)
        submitted = st.button("🔍 Score this applicant", type="primary", use_container_width=True)

    else:
        st.subheader("Customer Information")
        st.caption(
            "Mode B sends only the legacy 14 headline fields. The remaining features stay "
            "null and are imputed by the model pipeline, so scores can differ from Mode A."
        )

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
            bal_loan_raw = st.number_input(
                "Outstanding loan balance (current)",
                min_value=0, max_value=10_000_000_000, value=50_000_000,
                step=1_000_000, format="%d",
                help=(
                    f"Model accepts {BAL_LOAN_BOUNDS[0]:,} – {BAL_LOAN_BOUNDS[1]:,} VND. "
                    "Values outside this range are clipped to the nearest bound before scoring."
                ),
            )
            bal_loan = int(max(BAL_LOAN_BOUNDS[0], min(BAL_LOAN_BOUNDS[1], bal_loan_raw)))
            if bal_loan != bal_loan_raw:
                bound = "maximum" if bal_loan_raw > BAL_LOAN_BOUNDS[1] else "minimum"
                st.caption(f"⚠️ Clipped to model {bound}: **{bal_loan:,} VND**")

            bal_all_raw = st.number_input(
                "Outstanding balance — all products (current)",
                min_value=0, max_value=10_000_000_000, value=55_000_000,
                step=1_000_000, format="%d",
                help=(
                    f"Model accepts {BAL_ALL_BOUNDS[0]:,} – {BAL_ALL_BOUNDS[1]:,} VND. "
                    "Values outside this range are clipped to the nearest bound before scoring."
                ),
            )
            bal_all = int(max(BAL_ALL_BOUNDS[0], min(BAL_ALL_BOUNDS[1], bal_all_raw)))
            if bal_all != bal_all_raw:
                bound = "maximum" if bal_all_raw > BAL_ALL_BOUNDS[1] else "minimum"
                st.caption(f"⚠️ Clipped to model {bound}: **{bal_all:,} VND**")

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
        submitted = st.button("🔍 Score this customer", type="primary", use_container_width=True)

# ── Results panel ─────────────────────────────────────────────────────────────
with right:
    st.subheader("Scoring Result")

    if not submitted:
        if is_mode_a:
            st.info("Pick a ground-truth label + row index on the left and click **Score this applicant**.")
        else:
            st.info("Fill in the customer details on the left and click **Score this customer**.")
        st.stop()

    with st.spinner("Calling scoring API…"):
        resp = None
        try:
            resp = requests.post(
                f"{API_URL}/predict",
                params={"model": model_option, "source": source_option},
                json=payload,
                timeout=30,
            )
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

    # ── Ground-truth comparison (Mode A only) ──────────────────────────────────
    if ground_truth is not None:
        gt_text = "DEFAULT (label = 1)" if ground_truth == 1 else "GOOD (label = 0)"
        model_flags_risk = decision in ("reject", "manual_review")
        if ground_truth == 1:
            if model_flags_risk:
                st.success(f"✔ Agreement — ground truth **{gt_text}**, model flags risk "
                           f"(**{decision}**). The model caught a true defaulter.")
            else:
                st.error(f"✘ MISS (false negative) — ground truth **{gt_text}**, but the model "
                         f"**approved**. A real defaulter slipped through.")
        else:
            if not model_flags_risk:
                st.success(f"✔ Agreement — ground truth **{gt_text}**, model **approved**. "
                           f"Correctly cleared a good customer.")
            else:
                st.warning(f"✗ Over-cautious (false positive) — ground truth **{gt_text}**, "
                           f"but the model flagged risk (**{decision}**). A good customer rejected.")
        st.caption("Note: the decision threshold is a business choice, so an "
                   "approve/reject vs. label mismatch is not necessarily a model error.")

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
    st.caption(f"Model: `{data['model_version']}` · Latency: {data['latency_ms']:.0f} ms "
               f"· features sent: {len(payload)} · trace: `{data.get('trace_id', '')[:8]}`")
