import sys
import traceback

SHEET_ID = "1kLvCbD-uNMD-ljwZOj8ZtcMu_-irjRp_TMcVNncAlP0"
SERVICE_ACCOUNT = r"C:\Users\HYPER\Desktop\mon_dashboard_gs\service_account.json"
EXCEL_FALLBACK = r"C:\Users\HYPER\Desktop\mon_dashboard_gs\erp system (3).xlsx"

ALL_SHEETS = [
    "Products", "Sales", "SaleItems", "Clients", "Categories",
    "Purchases", "PurchaseItems", "Payments", "Refunds", "Devis",
    "DevisItems", "StockMovements", "PaymentAllocations", "CashLogs", "RefundItems"
]

use_gsheets = False
data = {}

# ---------------------------------------------------------------------------
# 1. Try Google Sheets via gspread
# ---------------------------------------------------------------------------
try:
    import gspread
    from gspread.utils import extract_id_from_url
    gc = gspread.service_account(filename=SERVICE_ACCOUNT)
    sh = gc.open_by_key(SHEET_ID)
    worksheets = sh.worksheets()
    print(f"=== Connected to Google Sheet: {sh.title} ===")
    print(f"Found {len(worksheets)} worksheet(s)")
    for ws in worksheets:
        title = ws.title
        records = ws.get_all_records()
        if not records:
            print(f"\n  [{title}] – empty sheet")
            data[title] = (0, 0, [], [])
            continue
        import pandas as pd
        df = pd.DataFrame(records)
        data[title] = (df.shape[0], df.shape[1], list(df.columns), df.head(5).to_dict("records"))
    use_gsheets = True
    print("\n=== Data loaded from Google Sheets ===\n")
except ImportError:
    print("gspread not installed, falling back to Excel", file=sys.stderr)
except Exception as e:
    print(f"Google Sheets connection failed: {e}", file=sys.stderr)
    traceback.print_exc(file=sys.stderr)

# ---------------------------------------------------------------------------
# 2. Fallback: local Excel via pandas + openpyxl
# ---------------------------------------------------------------------------
if not use_gsheets:
    try:
        import pandas as pd
        xls = pd.ExcelFile(EXCEL_FALLBACK, engine="openpyxl")
        print(f"=== Opened Excel file: {EXCEL_FALLBACK} ===")
        print(f"Sheet names: {xls.sheet_names}")
        for sheet in xls.sheet_names:
            df = pd.read_excel(xls, sheet_name=sheet)
            data[sheet] = (df.shape[0], df.shape[1], list(df.columns), df.head(5).to_dict("records"))
        print("\n=== Data loaded from Excel ===\n")
    except Exception as e:
        print(f"Excel fallback also failed: {e}", file=sys.stderr)
        sys.exit(1)

# ---------------------------------------------------------------------------
# 3. Print overview for every sheet
# ---------------------------------------------------------------------------
for name in ALL_SHEETS:
    if name not in data:
        print(f"\n{'='*60}")
        print(f"  [{name}] – NOT FOUND in source")
        print(f"{'='*60}")
        continue
    rows, cols, columns, sample = data[name]
    print(f"\n{'='*60}")
    print(f"  [{name}]  Shape: {rows} rows x {cols} cols")
    print(f"  Columns: {columns}")
    print(f"  Sample (first 5 rows):")
    if sample:
        import pandas as pd
        print(pd.DataFrame(sample).to_string(index=False))
    else:
        print("    (empty)")
    print(f"{'='*60}")

# ---------------------------------------------------------------------------
# 4. Anomaly detection helpers
# ---------------------------------------------------------------------------
def get_df(name):
    """Return a full DataFrame for a sheet if available."""
    if name not in data:
        return None
    rows, cols, columns, _ = data[name]
    if rows == 0:
        return None
    # Re-read full data (we only stored head earlier)
    return None  # signal we need to re-read

def read_full(name):
    """Read full sheet content."""
    if use_gsheets:
        try:
            import gspread
            import pandas as pd
            gc = gspread.service_account(filename=SERVICE_ACCOUNT)
            sh = gc.open_by_key(SHEET_ID)
            ws = sh.worksheet(name)
            records = ws.get_all_records()
            if not records:
                return pd.DataFrame()
            return pd.DataFrame(records)
        except Exception as e:
            print(f"    [WARN] Could not re-read '{name}' from sheets: {e}")
            return pd.DataFrame()
    else:
        try:
            import pandas as pd
            return pd.read_excel(EXCEL_FALLBACK, sheet_name=name, engine="openpyxl")
        except Exception as e:
            print(f"    [WARN] Could not re-read '{name}' from Excel: {e}")
            return pd.DataFrame()

def normalize_currency(val):
    """Try to convert a value to float, handling strings with €/$ and commas."""
    if isinstance(val, (int, float)):
        return float(val)
    if val is None:
        return None
    s = str(val).replace("€", "").replace("$", "").replace(",", ".").replace(" ", "").strip()
    try:
        return float(s)
    except:
        return None

print("\n\n" + "="*60)
print("  ANOMALY DETECTION RESULTS")
print("="*60)

anomalies_found = 0

# ---------------------------------------------------------------------------
# Sales + SaleItems anomalies
# ---------------------------------------------------------------------------
print("\n--- Sales & SaleItems ---")
df_sales = read_full("Sales")
df_items = read_full("SaleItems")

if df_sales is not None and not df_sales.empty:
    # Normalize financial columns
    for col in ["total", "subtotal", "tax", "discount"]:
        if col in df_sales.columns:
            df_sales[col] = df_sales[col].apply(normalize_currency)

    # 4a. Sale total != subtotal + tax - discount
    if all(c in df_sales.columns for c in ["total", "subtotal", "tax", "discount"]):
        mismatch_total = df_sales[
            abs(df_sales["total"] - (df_sales["subtotal"] + df_sales["tax"] - df_sales["discount"])) > 0.01
        ]
        if not mismatch_total.empty:
            anomalies_found += 1
            print(f"  [!] {len(mismatch_total)} sale(s) where total != subtotal + tax - discount:")
            print(mismatch_total[["total", "subtotal", "tax", "discount"]].to_string(index=True))
        else:
            print("  [OK] All sale totals match subtotal + tax - discount")
    else:
        missing = [c for c in ["total","subtotal","tax","discount"] if c not in df_sales.columns]
        print(f"  [-] Cannot check total formula – missing columns: {missing}")

    # 4d. Sales with 0 or negative total
    if "total" in df_sales.columns:
        bad_totals = df_sales[df_sales["total"] <= 0]
        if not bad_totals.empty:
            anomalies_found += 1
            print(f"  [!] {len(bad_totals)} sale(s) with total <= 0:")
            print(bad_totals[["total"]].to_string(index=True))
        else:
            print("  [OK] No sales with zero/negative total")

    # 4e. Missing client_id
    if "client_id" in df_sales.columns:
        missing_client = df_sales[df_sales["client_id"].isna() | (df_sales["client_id"].astype(str).str.strip() == "")]
        if not missing_client.empty:
            anomalies_found += 1
            print(f"  [!] {len(missing_client)} sale(s) with missing client_id:")
            print(missing_client[["client_id"]].to_string(index=True))
        else:
            print("  [OK] No missing client_id")
    else:
        print("  [-] Column 'client_id' not found in Sales")

else:
    print("  [-] Sales sheet empty or not available")

if df_items is not None and not df_items.empty:
    # Normalize
    for col in ["quantity", "price", "total"]:
        if col in df_items.columns:
            df_items[col] = df_items[col].apply(normalize_currency)

    # 4b. Items where total != quantity * price
    if all(c in df_items.columns for c in ["quantity", "price", "total"]):
        df_items["calc_total"] = df_items["quantity"] * df_items["price"]
        bad_line = df_items[abs(df_items["total"] - df_items["calc_total"]) > 0.01]
        if not bad_line.empty:
            anomalies_found += 1
            print(f"  [!] {len(bad_line)} item(s) where total != quantity * price:")
            print(bad_line[["quantity", "price", "total", "calc_total"]].to_string(index=True))
        else:
            print("  [OK] All item totals match quantity * price")
        df_items.drop(columns=["calc_total"], inplace=True)
    else:
        missing = [c for c in ["quantity","price","total"] if c not in df_items.columns]
        print(f"  [-] Cannot check item totals – missing columns: {missing}")

    # 4c. Negative quantity, price, or total
    for col in ["quantity", "price", "total"]:
        if col in df_items.columns:
            neg = df_items[df_items[col] < 0]
            if not neg.empty:
                anomalies_found += 1
                print(f"  [!] {len(neg)} item(s) with negative {col}:")
                print(neg[[col]].to_string(index=True))
            else:
                print(f"  [OK] No negative {col} in items")

    # 4f. Missing sale_id
    if "sale_id" in df_items.columns:
        missing_sid = df_items[df_items["sale_id"].isna() | (df_items["sale_id"].astype(str).str.strip() == "")]
        if not missing_sid.empty:
            anomalies_found += 1
            print(f"  [!] {len(missing_sid)} item(s) with missing sale_id:")
            print(missing_sid[["sale_id"]].to_string(index=True))
        else:
            print("  [OK] No missing sale_id in items")
    else:
        print("  [-] Column 'sale_id' not found in SaleItems")
else:
    print("  [-] SaleItems sheet empty or not available")

# ---------------------------------------------------------------------------
# 5. StockMovements
# ---------------------------------------------------------------------------
print("\n--- StockMovements ---")
df_stock = read_full("StockMovements")
if df_stock is not None and not df_stock.empty:
    for col in ["quantity"]:
        if col in df_stock.columns:
            df_stock[col] = df_stock[col].apply(normalize_currency)
            neg = df_stock[df_stock[col] < 0]
            if not neg.empty:
                anomalies_found += 1
                print(f"  [!] {len(neg)} stock movement(s) with negative {col}:")
                print(neg[[col]].to_string(index=True))
            else:
                print(f"  [OK] No negative {col} in StockMovements")

    if "type" in df_stock.columns:
        valid_types = {"in", "out", "entry", "exit", "positive", "negative", "adjustment", "correction", "inventory"}
        df_stock["type_str"] = df_stock["type"].astype(str).str.lower().str.strip()
        unknown = df_stock[~df_stock["type_str"].isin(valid_types)]
        if not unknown.empty:
            anomalies_found += 1
            print(f"  [!] {len(unknown)} stock movement(s) with unknown type:")
            print(unknown[["type"]].to_string(index=True))
        else:
            print("  [OK] All stock movement types are recognized")
    else:
        print("  [-] Column 'type' not found in StockMovements")
else:
    print("  [-] StockMovements sheet empty or not available")

# ---------------------------------------------------------------------------
# 6. Purchases / PurchaseItems
# ---------------------------------------------------------------------------
print("\n--- Purchases & PurchaseItems ---")
for sname in ["Purchases", "PurchaseItems"]:
    df = read_full(sname)
    if df is not None and not df.empty:
        for col in ["quantity", "price", "total"]:
            if col in df.columns:
                df[col] = df[col].apply(normalize_currency)
                neg = df[df[col] < 0]
                if not neg.empty:
                    anomalies_found += 1
                    print(f"  [!] [{sname}] {len(neg)} record(s) with negative {col}:")
                    print(neg[[col]].to_string(index=True))
                else:
                    print(f"  [OK] [{sname}] No negative {col}")
    else:
        print(f"  [-] {sname} empty or not available")

# ---------------------------------------------------------------------------
# 7. Payments vs Sale total mismatch
# ---------------------------------------------------------------------------
print("\n--- Payments vs Sales ---")
df_payments = read_full("Payments")
if df_payments is not None and not df_payments.empty and df_sales is not None and not df_sales.empty:
    if "amount" in df_payments.columns and "sale_id" in df_payments.columns and "total" in df_sales.columns and "id" in df_sales.columns:
        df_payments["amount"] = df_payments["amount"].apply(normalize_currency)
        sale_totals = df_sales[["id", "total"]].copy()
        sale_totals.rename(columns={"id": "sale_id"}, inplace=True)
        # Try to match sale_id from payments to sales id
        merged = df_payments.merge(sale_totals, on="sale_id", how="left")
        mismatched = merged[merged["total"].notna() & (abs(merged["amount"] - merged["total"]) > 0.01)]
        if not mismatched.empty:
            anomalies_found += 1
            print(f"  [!] {len(mismatched)} payment(s) where amount doesn't match sale total:")
            print(mismatched[["sale_id", "amount", "total"]].to_string(index=True))
        else:
            print("  [OK] All payment amounts match corresponding sale totals")
    else:
        missing = [c for c in ["amount","sale_id"] if c not in df_payments.columns]
        missing += [c for c in ["id","total"] if c not in df_sales.columns]
        print(f"  [-] Cannot compare payments vs sales – missing columns: {missing}")
else:
    print("  [-] Payments or Sales data not available for comparison")

print(f"\n{'='*60}")
print(f"  ANALYSIS COMPLETE – {anomalies_found} anomaly type(s) detected")
print(f"{'='*60}")
