from pathlib import Path
import pandas as pd

IN_DIR = Path("data/incoming")
OUT_DIR = Path("reports")
OUT_DIR.mkdir(parents=True, exist_ok=True)

BANK_FILE = IN_DIR / "bank.csv"
GL_FILE = IN_DIR / "gl.csv"

# Matching rules
TOLERANCE = 1.00       # +/- $1 allowed difference
DATE_WINDOW_DAYS = 3   # +/- 3 days allowed difference


def normalize_text(s: str) -> str:
    """Basic text normalization for memo/description matching."""
    if pd.isna(s):
        return ""
    s = str(s).lower()
    for ch in [",", ".", "|", "/", "\\", "-", "_", ":", ";", "#", "(", ")", "[", "]"]:
        s = s.replace(ch, " ")
    return " ".join(s.split())


def load_inputs():
    if not BANK_FILE.exists() or not GL_FILE.exists():
        raise FileNotFoundError(
            "Missing input files. Ensure these exist:\n"
            " - data/incoming/bank.csv\n"
            " - data/incoming/gl.csv"
        )

    bank = pd.read_csv(BANK_FILE)
    gl = pd.read_csv(GL_FILE)

    # Standardize columns
    bank.columns = [c.strip().lower() for c in bank.columns]
    gl.columns = [c.strip().lower() for c in gl.columns]

    # Parse types
    bank["txn_date"] = pd.to_datetime(bank["txn_date"], errors="coerce")
    gl["posting_date"] = pd.to_datetime(gl["posting_date"], errors="coerce")

    bank["amount"] = pd.to_numeric(bank["amount"], errors="coerce")
    gl["amount"] = pd.to_numeric(gl["amount"], errors="coerce")

    # Normalized text fields for tie-breaking
    bank["desc_norm"] = bank["description"].apply(normalize_text)
    gl["memo_norm"] = gl["memo"].apply(normalize_text)

    bank["matched"] = False
    gl["matched"] = False

    return bank, gl


def match_exact_amount(bank, gl):
    """Match bank ↔ GL using exact amount match (fast, clean wins)."""
    matches = []
    gl_open = gl[~gl["matched"]].copy()

    for i, b in bank[~bank["matched"]].iterrows():
        candidates = gl_open[gl_open["amount"] == b["amount"]]
        if len(candidates) == 1:
            g = candidates.iloc[0]
            matches.append((b["bank_id"], g["gl_id"], "exact_amount"))
            bank.at[i, "matched"] = True
            gl.loc[gl["gl_id"] == g["gl_id"], "matched"] = True
            gl_open = gl[~gl["matched"]].copy()

    return bank, gl, matches


def match_tolerance_date(bank, gl):
    """
    Match using tolerance + date window.
    If multiple candidates exist, prefer the one with higher token overlap in description/memo.
    """
    matches = []
    gl_open = gl[~gl["matched"]].copy()

    for i, b in bank[~bank["matched"]].iterrows():
        if pd.isna(b["txn_date"]) or pd.isna(b["amount"]):
            continue

        lo = b["txn_date"] - pd.Timedelta(days=DATE_WINDOW_DAYS)
        hi = b["txn_date"] + pd.Timedelta(days=DATE_WINDOW_DAYS)

        candidates = gl_open[
            (gl_open["posting_date"] >= lo) &
            (gl_open["posting_date"] <= hi) &
            (gl_open["amount"].between(b["amount"] - TOLERANCE, b["amount"] + TOLERANCE))
        ].copy()

        if candidates.empty:
            continue

        # Tie-breaker: token overlap between bank description and GL memo
        b_tokens = set(str(b["desc_norm"]).split())
        candidates["token_overlap"] = candidates["memo_norm"].apply(
            lambda m: len(b_tokens.intersection(set(str(m).split())))
        )

        candidates = candidates.sort_values(by=["token_overlap"], ascending=False)
        best = candidates.iloc[0]

        # Accept if only one candidate OR overlap looks reasonable
        if len(candidates) == 1 or best["token_overlap"] >= 1:
            matches.append((b["bank_id"], best["gl_id"], "tolerance_date"))
            bank.at[i, "matched"] = True
            gl.loc[gl["gl_id"] == best["gl_id"], "matched"] = True
            gl_open = gl[~gl["matched"]].copy()

    return bank, gl, matches


def build_outputs(bank, gl, matches):
    matched = pd.DataFrame(matches, columns=["bank_id", "gl_id", "match_type"])

    unmatched_bank = bank[bank["matched"] == False].drop(columns=["desc_norm", "matched"], errors="ignore")
    unmatched_gl = gl[gl["matched"] == False].drop(columns=["memo_norm", "matched"], errors="ignore")

    # Build a detailed matched view
    bank_clean = bank.drop(columns=["desc_norm", "matched"], errors="ignore")
    gl_clean = gl.drop(columns=["memo_norm", "matched"], errors="ignore")

    matched_full = matched.merge(bank_clean, on="bank_id", how="left") \
                          .merge(gl_clean, on="gl_id", how="left", suffixes=("_bank", "_gl"))

    summary = matched.groupby("match_type").size().reset_index(name="count")
    summary = pd.concat([summary, pd.DataFrame([{"match_type": "TOTAL_MATCHED", "count": len(matched)}])],
                        ignore_index=True)

    return matched_full, unmatched_bank, unmatched_gl, summary


def main():
    bank, gl = load_inputs()

    bank, gl, m1 = match_exact_amount(bank, gl)
    bank, gl, m2 = match_tolerance_date(bank, gl)

    matches = m1 + m2

    matched_full, unmatched_bank, unmatched_gl, summary = build_outputs(bank, gl, matches)

    out_file = OUT_DIR / "reconciliation_pack.xlsx"
    with pd.ExcelWriter(out_file, engine="openpyxl") as writer:
        matched_full.to_excel(writer, index=False, sheet_name="matched")
        unmatched_bank.to_excel(writer, index=False, sheet_name="unmatched_bank")
        unmatched_gl.to_excel(writer, index=False, sheet_name="unmatched_gl")
        summary.to_excel(writer, index=False, sheet_name="summary")

    print(f"✅ Reconciliation complete. Output saved to: {out_file}")


if __name__ == "__main__":
    main()
