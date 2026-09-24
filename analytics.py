import argparse
import os
import sys
from datetime import datetime, timedelta, timezone

import matplotlib
import pandas as pd


try:
    from database import supabase
except ImportError:
    from dotenv import load_dotenv
    from supabase import create_client

    load_dotenv()
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    if not url or not key:
        sys.exit(
            "Could not import database.py and no SUPABASE_URL/SUPABASE_KEY "
            "found in .env. Copy your project's database.py into this folder, "
            "or set those two env vars."
        )
    supabase = create_client(url, key)

def fetch_data(days: int | None):
    """Pull orders, order_items, product_variants, products, categories."""
    orders = pd.DataFrame(supabase.table("orders").select("*").execute().data)
    order_items = pd.DataFrame(supabase.table("order_items").select("*").execute().data)
    variants = pd.DataFrame(supabase.table("product_variants").select("*").execute().data)
    products = pd.DataFrame(supabase.table("products").select("*").execute().data)
    categories = pd.DataFrame(supabase.table("categories").select("*").execute().data)

    if orders.empty:
        sys.exit("No orders found in the database — nothing to chart yet.")

    orders["created_at"] = pd.to_datetime(orders["created_at"], utc=True)

    if days:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        orders = orders[orders["created_at"] >= cutoff]

    return orders, order_items, variants, products, categories


def build_line_items(order_items, variants, products, categories, orders):
    """Join order_items -> variants -> products -> categories -> orders (for date/status)."""
    if order_items.empty:
        return pd.DataFrame()

    df = order_items.merge(
        variants[["id", "product_id"]], left_on="variant_id", right_on="id",
        suffixes=("", "_variant"),
    )
    df = df.merge(
        products[["id", "name", "category_id"]], left_on="product_id", right_on="id",
        suffixes=("", "_product"),
    )
    if not categories.empty:
        df = df.merge(
            categories[["id", "name"]], left_on="category_id", right_on="id",
            suffixes=("", "_category"),
        )
        df = df.rename(columns={"name_category": "category_name"})
    else:
        df["category_name"] = "Uncategorized"

    df = df.rename(columns={"name": "product_name"})
    df["line_total"] = df["quantity"] * df["price_at_time"]

    df = df.merge(
        orders[["id", "created_at", "status"]], left_on="order_id", right_on="id",
        suffixes=("", "_order"),
    )
    return df


def chart_revenue_over_time(orders, out_dir, plt):
    daily = (
        orders.set_index("created_at")["total"]
        .resample("D").sum()
        .fillna(0)
    )
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(daily.index, daily.values, marker="o", linewidth=2, color="#5b5bd6")
    ax.fill_between(daily.index, daily.values, alpha=0.15, color="#5b5bd6")
    ax.set_title("Daily Revenue")
    ax.set_xlabel("Date")
    ax.set_ylabel("Revenue (ZAR)")
    ax.grid(alpha=0.3)
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(os.path.join(out_dir, "revenue_over_time.png"), dpi=150)
    return fig


def chart_orders_by_status(orders, out_dir, plt):
    counts = orders["status"].value_counts()
    fig, ax = plt.subplots(figsize=(7, 5))
    colors = {"pending": "#e0a72e", "paid": "#4a9ded", "shipped": "#8a6fd6",
              "delivered": "#3fae6a", "cancelled": "#d64545"}
    bar_colors = [colors.get(s, "#999999") for s in counts.index]
    ax.bar(counts.index, counts.values, color=bar_colors)
    ax.set_title("Orders by Status")
    ax.set_xlabel("Status")
    ax.set_ylabel("Number of Orders")
    for i, v in enumerate(counts.values):
        ax.text(i, v, str(v), ha="center", va="bottom")
    fig.tight_layout()
    fig.savefig(os.path.join(out_dir, "orders_by_status.png"), dpi=150)
    return fig


def chart_order_volume_trend(orders, out_dir, plt):
    weekly = orders.set_index("created_at").resample("W").size()
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(weekly.index, weekly.values, marker="o", linewidth=2, color="#3fae6a")
    ax.set_title("Weekly Order Volume")
    ax.set_xlabel("Week")
    ax.set_ylabel("Orders Placed")
    ax.grid(alpha=0.3)
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(os.path.join(out_dir, "order_volume_trend.png"), dpi=150)
    return fig


def chart_top_products(line_items, out_dir, plt, top_n=10):
    if line_items.empty:
        return None
    top = (
        line_items.groupby("product_name")["line_total"]
        .sum().sort_values(ascending=False).head(top_n)
    )
    fig, ax = plt.subplots(figsize=(9, 6))
    ax.barh(top.index[::-1], top.values[::-1], color="#5b5bd6")
    ax.set_title(f"Top {top_n} Products by Revenue")
    ax.set_xlabel("Revenue (ZAR)")
    fig.tight_layout()
    fig.savefig(os.path.join(out_dir, "top_products.png"), dpi=150)
    return fig


def chart_revenue_by_category(line_items, out_dir, plt):
    if line_items.empty:
        return None
    by_cat = line_items.groupby("category_name")["line_total"].sum().sort_values(ascending=False)
    fig, ax = plt.subplots(figsize=(7, 7))
    ax.pie(by_cat.values, labels=by_cat.index, autopct="%1.0f%%", startangle=90,
           colors=plt.cm.Pastel1.colors)
    ax.set_title("Revenue Share by Category")
    fig.tight_layout()
    fig.savefig(os.path.join(out_dir, "revenue_by_category.png"), dpi=150)
    return fig

def main():
    parser = argparse.ArgumentParser(description="Generate store analytics charts.")
    parser.add_argument("--out", default="charts", help="Output directory for PNG charts")
    parser.add_argument("--show", action="store_true", help="Also display charts in a window")
    parser.add_argument("--days", type=int, default=None, help="Only include orders from the last N days")
    args = parser.parse_args()

    if not args.show:
        matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    os.makedirs(args.out, exist_ok=True)

    print("Fetching data from Supabase...")
    orders, order_items, variants, products, categories = fetch_data(args.days)
    line_items = build_line_items(order_items, variants, products, categories, orders)

    print(f"{len(orders)} orders, {len(order_items)} order items loaded.")
    print("Generating charts...")

    chart_revenue_over_time(orders, args.out, plt)
    chart_orders_by_status(orders, args.out, plt)
    chart_order_volume_trend(orders, args.out, plt)
    chart_top_products(line_items, args.out, plt)
    chart_revenue_by_category(line_items, args.out, plt)

    print(f"Done. Charts saved to ./{args.out}/")
    print(f"  Total revenue: {orders['total'].sum():.2f}")
    print(f"  Avg order value: {orders['total'].mean():.2f}")
    print(f"  Orders by status:\n{orders['status'].value_counts().to_string()}")

    if args.show:
        plt.show()


if __name__ == "__main__":
    main()
