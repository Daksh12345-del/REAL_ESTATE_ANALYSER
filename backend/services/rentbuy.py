"""Rent vs buy: month-by-month comparison of a buyer's net worth against a renter who invests the difference.

Buyer : pays down payment + buying costs up front, then EMI + upkeep. Net worth = sale value after selling costs - loan left.
Renter: invests the same up-front cash, then every month invests (buyer's outflow - rent). Net worth = that portfolio.
Break-even = first month after which the buyer stays ahead. Taxes (home-loan deductions, capital gains) are ignored.
"""
import numpy as np


def emi(principal: float, annual_rate_pct: float, years: int) -> float:
    n = years * 12
    r = annual_rate_pct / 100 / 12
    if r == 0:
        return principal / n
    f = (1 + r) ** n
    return principal * r * f / (f - 1)


def simulate(price_lakh, monthly_rent, down_payment_pct=20, loan_rate_pct=8.0, tenure_years=20,
             appreciation_pct=5.0, rent_growth_pct=5.0, investment_return_pct=8.0,
             buying_cost_pct=6.0, upkeep_pct=0.75, selling_cost_pct=2.0, horizon_years=25) -> dict:
    price = price_lakh * 1e5
    down = price * down_payment_pct / 100
    loan0 = price - down
    upfront = down + price * buying_cost_pct / 100
    payment = emi(loan0, loan_rate_pct, tenure_years) if loan0 > 0 else 0.0
    r_loan, r_inv = loan_rate_pct / 100 / 12, investment_return_pct / 100 / 12
    n_loan = tenure_years * 12

    bal, portfolio = loan0, upfront
    months = horizon_years * 12
    buyer_series, renter_series, yearly = [], [], []
    for m in range(1, months + 1):
        value = price * (1 + appreciation_pct / 100) ** (m / 12)
        rent = monthly_rent * (1 + rent_growth_pct / 100) ** ((m - 1) // 12)
        outflow = upkeep_pct / 100 * value / 12
        if m <= n_loan and bal > 0:
            interest = bal * r_loan
            bal = max(bal - (payment - interest), 0.0)
            outflow += payment
        portfolio = portfolio * (1 + r_inv) + (outflow - rent)
        buyer = value * (1 - selling_cost_pct / 100) - bal
        buyer_series.append(buyer)
        renter_series.append(portfolio)
        if m % 12 == 0:
            yearly.append({"year": m // 12, "buyer_net_worth_lakh": buyer / 1e5, "renter_net_worth_lakh": portfolio / 1e5,
                           "property_value_lakh": value / 1e5, "loan_balance_lakh": bal / 1e5, "monthly_rent": rent})

    ahead = np.array(buyer_series) >= np.array(renter_series)
    break_even = None
    if ahead[-1]:
        behind = np.where(~ahead)[0]
        first_month = (behind[-1] + 2) if len(behind) else 1   # first month after the last time the buyer was behind
        break_even = round(first_month / 12, 1)
    final = yearly[-1]
    return {
        "inputs": {"price_lakh": price_lakh, "monthly_rent": monthly_rent, "down_payment_pct": down_payment_pct,
                   "loan_rate_pct": loan_rate_pct, "tenure_years": tenure_years, "appreciation_pct": appreciation_pct,
                   "rent_growth_pct": rent_growth_pct, "investment_return_pct": investment_return_pct,
                   "buying_cost_pct": buying_cost_pct, "upkeep_pct": upkeep_pct, "selling_cost_pct": selling_cost_pct,
                   "horizon_years": horizon_years},
        "emi": round(payment), "upfront_cash_lakh": round(upfront / 1e5, 2),
        "first_year_monthly_outflow": round(payment + upkeep_pct / 100 * price / 12),
        "price_to_annual_rent": round(price / (monthly_rent * 12), 1),
        "gross_rental_yield_pct": round(monthly_rent * 12 / price * 100, 2),
        "break_even_years": break_even, "buyer_wins_at_horizon": bool(ahead[-1]),
        "final_gap_lakh": round(final["buyer_net_worth_lakh"] - final["renter_net_worth_lakh"], 2),
        "yearly": [{k: round(v, 2) for k, v in y.items()} for y in yearly],
    }
