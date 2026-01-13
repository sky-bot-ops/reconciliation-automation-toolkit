# Reconciliation Automation Toolkit

A finance focused Python toolkit that automates reconciliation between **Bank Statements**, **General Ledger (GL)**, and **Subledger** exports. It performs matching with **tolerance rules**, flags breaks, and generates an Excel reconciliation pack for audit ready review.

## Purpose
Finance and audit teams often reconcile thousands of transactions across systems (bank vs GL vs subledger). Manual reconciliation is slow and inconsistent, especially when:
- bank descriptions don’t match GL text exactly
- amounts differ slightly due to FX/fees/timing
- duplicates and partial matches exist

This toolkit automates matching logic and produces a clean, explainable reconciliation output.

## What it does
- Matches transactions using:
  - **Exact amount match**
  - **Tolerance match** (e.g., ±$1.00)
  - **Date window match** (e.g., ±3 days)
  - **Reference/description similarity** (basic normalization)
- Flags:
  - Unmatched bank items
  - Unmatched GL items
  - Potential duplicates
  - Many-to-one / one-to-many situations (optional)

## Input files (CSV)
Expected files:
- `data/incoming/bank.csv`
- `data/incoming/gl.csv`

### Required columns
**bank.csv**
- `bank_id`
- `txn_date` (YYYY-MM-DD)
- `amount`
- `description`

**gl.csv**
- `gl_id`
- `posting_date` (YYYY-MM-DD)
- `amount`
- `memo`

## Output (Excel)
Generates an Excel pack in `reports/`:
- `matched` (final matched pairs + match_type)
- `unmatched_bank`
- `unmatched_gl`
- `summary` (counts by match_type)
