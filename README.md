# Store Analytics

Generates matplotlib charts of your store's sales trends, pulled live from
your Supabase project (the same `orders`, `order_items`, `products`,
`product_variants`, and `categories` tables your FastAPI backend uses).

## Setup

1. Copy this folder next to your existing backend project, or copy your
   project's `database.py` into this folder (it needs a `.env` with
   `SUPABASE_URL` and `SUPABASE_KEY`, same as your API).
2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

## Run

```
python analytics.py                # save charts to ./charts/
python analytics.py --show         # also pop up windows for each chart
python analytics.py --days 90      # only last 90 days of orders
python analytics.py --out reports  # custom output folder
```

## Charts produced

- `revenue_over_time.png` — daily revenue line chart
- `orders_by_status.png` — bar chart of pending/paid/shipped/delivered/cancelled
- `order_volume_trend.png` — weekly order count trend
- `top_products.png` — top 10 products by revenue (needs order_items data)
- `revenue_by_category.png` — pie chart of revenue share per category

A short text summary (total revenue, average order value, status counts)
also prints to the console after each run.

## Notes

- Uses the same **anon or service** key your `database.py` already uses —
  since this runs locally (not in a browser), a `service_role` key is fine
  here if that's what your backend uses.
- `top_products` and `revenue_by_category` need `order_items` rows to exist
  (i.e. orders that went through checkout) — they'll be skipped with a note
  if there's no line-item data yet.
