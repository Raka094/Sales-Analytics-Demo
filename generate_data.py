"""
Step 1: Generate fake sales data for a chemical supplier.

Why fake data: never use real company data in a public demo.
Why this design: the data is built so that ABC segmentation and
price analysis give realistic, interesting results:
  - a few big customers bring most of the revenue (Pareto effect)
  - big customers get bigger discounts (volume discounts)
  - some customers are underpriced by chance (pricing opportunities)
"""

import numpy as np
import pandas as pd

rng = np.random.default_rng(seed=42)  # fixed seed = same data every run

N_CUSTOMERS = 300
N_PRODUCTS = 40
MONTHS = pd.date_range("2025-01-01", "2025-12-01", freq="MS")

regions = ["DACH", "France", "Benelux", "Italy", "Iberia", "Nordics"]
industries = ["Automotive", "Construction", "Packaging", "Agriculture", "Consumer Goods"]
families = ["Coatings", "Polymers", "Additives", "Catalysts"]

# --- Customers --------------------------------------------------------
# Lognormal size: most customers are small, a few are very large.
customers = pd.DataFrame({
    "customer_id": [f"C{i:04d}" for i in range(1, N_CUSTOMERS + 1)],
    "region": rng.choice(regions, N_CUSTOMERS),
    "industry": rng.choice(industries, N_CUSTOMERS),
    "size_factor": rng.lognormal(mean=0, sigma=1.3, size=N_CUSTOMERS),
})

# --- Products ---------------------------------------------------------
products = pd.DataFrame({
    "product_id": [f"P{i:03d}" for i in range(1, N_PRODUCTS + 1)],
    "product_family": rng.choice(families, N_PRODUCTS),
    "list_price_eur_per_kg": rng.uniform(2, 20, N_PRODUCTS).round(2),
})
products["unit_cost_eur_per_kg"] = (
    products["list_price_eur_per_kg"] * rng.uniform(0.55, 0.8, N_PRODUCTS)
).round(2)

# --- Transactions -----------------------------------------------------
rows = []
for _, c in customers.iterrows():
    # Bigger customers buy more products and more often.
    n_products = int(np.clip(rng.poisson(2 + c.size_factor * 2), 1, 15))
    bought = products.sample(n_products, random_state=rng.integers(1e9))

    # Volume discount grows with size, plus random noise
    # -> some customers end up underpriced compared to peers.
    base_discount = np.clip(0.05 + 0.04 * np.log1p(c.size_factor), 0, 0.30)

    for _, p in bought.iterrows():
        discount = np.clip(base_discount + rng.normal(0, 0.05), 0, 0.40)
        for month in MONTHS:
            if rng.random() < 0.6:  # not every month has an order
                volume = rng.gamma(2, 400 * c.size_factor)
                net_price = p.list_price_eur_per_kg * (1 - discount)
                rows.append({
                    "month": month.date(),
                    "customer_id": c.customer_id,
                    "region": c.region,
                    "industry": c.industry,
                    "product_id": p.product_id,
                    "product_family": p.product_family,
                    "volume_kg": round(volume, 1),
                    "list_price_eur_per_kg": p.list_price_eur_per_kg,
                    "net_price_eur_per_kg": round(net_price, 2),
                    "revenue_eur": round(volume * net_price, 2),
                    "cost_eur": round(volume * p.unit_cost_eur_per_kg, 2),
                })

sales = pd.DataFrame(rows)
sales.to_csv("sales_data.csv", index=False)

print(f"Rows: {len(sales):,}")
print(f"Customers: {sales.customer_id.nunique()}, Products: {sales.product_id.nunique()}")
print(f"Total revenue: EUR {sales.revenue_eur.sum():,.0f}")
print(sales.head())
