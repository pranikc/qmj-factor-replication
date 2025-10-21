# QMJ Table IV Replication - Technical Methodology

Complete technical details for replicating Table IV (Panel A) from Asness, Frazzini, and Pedersen (2019).

**Paper Reference:**
> Asness, Cliff S., Andrea Frazzini, and Lasse H. Pedersen. "Quality minus junk." *Review of Accounting Studies* 24.1 (2019): 34-112.

**Target:** Portfolio excess returns (monthly, value-weighted, 10 deciles sorted by quality)

---

## Data Sources

### CRSP Monthly Stock File
Variables:
- `PERMNO`: Unique stock identifier
- `date`: Month-end date
- `RET`: Monthly return (including dividends)
- `PRC`: Month-end price
- `SHROUT`: Shares outstanding
- `EXCHCD`: Exchange code (1=NYSE, 2=AMEX, 3=NASDAQ)
- `SHRCD`: Share code (10=ordinary common, 11=certificates)
- `DLRET`: Delisting return

### Compustat Fundamentals Annual
Variables:
- Profitability: `IB`, `SEQ`, `AT`
- Growth: `SALE`, `AT` (historical values)
- Safety: `LT`, `ACT`, `LCT`
- Payout: `DVT`, `DVC`, `PRSTKC`
- Additional: `FYEAR`, `DATADATE`, `FYR`

### Fama-French Factors
- `Mkt-RF`: Market excess return
- `RF`: Risk-free rate (1-month T-bill)

### Sample Period
- October 1956 - December 2012 (674 months)
- ~2.6 million firm-month observations

---

## Step 1: Data Extraction and Linking

### CRSP Filters
```python
SHRCD IN (10, 11)  # US common stocks
EXCHCD IN (1, 2, 3)  # NYSE, AMEX, NASDAQ
```

### CRSP-Compustat Linking
```python
LINKTYPE IN ('LC', 'LU')
LINKPRIM IN ('P', 'C')
```

### Date Alignment
```python
# 4-month accounting lag
# Fiscal year ending June 30, 2008 (datadate: 2008-06-30)
# Available for portfolio formation: November 1, 2008 onwards

available_date = datadate + pd.DateOffset(months=4)
```

### Market Capitalization
```python
mkt_cap = abs(PRC) * SHROUT / 1000  # in millions
```

### Delisting Returns
```python
if pd.notna(DLRET):
    if pd.isna(RET):
        final_ret = DLRET
    else:
        final_ret = (1 + RET) * (1 + DLRET) - 1
elif delisting_code in [500-591]:  # Performance-related
    final_ret = -0.30
```

---

## Step 2: Quality Score Calculation

### Profitability Component
Metrics:
1. ROE: `IB / SEQ`
2. ROA: `IB / AT`
3. Gross Profits to Assets: `(SALE - COGS) / AT`

```python
roe = IB / SEQ
roa = IB / AT
gp_to_assets = (SALE - COGS) / AT

# Z-score each metric cross-sectionally
roe_z = (roe - roe.mean()) / roe.std()
roa_z = (roa - roa.mean()) / roa.std()
gp_z = (gp_to_assets - gp_to_assets.mean()) / gp_to_assets.std()

# Average to get profitability score
profitability_score = (roe_z + roa_z + gp_z) / 3
```

### Growth Component (5-Year)
Metrics:
1. 5-Year Profitability Growth
2. 5-Year Asset Growth

```python
profitability_t0 = (IB / AT)[year=t]
profitability_t5 = (IB / AT)[year=t-5]

# Simple percentage change (not CAGR)
prof_growth = (profitability_t0 - profitability_t5) / abs(profitability_t5)
asset_growth = (AT[t] - AT[t-5]) / AT[t-5]

# Z-score and average
prof_growth_z = (prof_growth - prof_growth.mean()) / prof_growth.std()
asset_growth_z = (asset_growth - asset_growth.mean()) / asset_growth.std()

growth_score = (prof_growth_z + asset_growth_z) / 2
```

### Safety Component
Metrics:
1. Low Leverage: `-1 * (LT / SEQ)`
2. Low Beta: Negative of market beta (60-month rolling)
3. Low Volatility: Negative of return volatility (60-month rolling)

```python
leverage = -1 * (LT / SEQ)

# Beta (60-month rolling regression)
beta = rolling_regression(excess_returns, market_excess, window=60)
low_beta = -1 * beta

# Volatility (60-month rolling std)
volatility = returns.rolling(60).std()
low_volatility = -1 * volatility

# Z-score and average
leverage_z = (leverage - leverage.mean()) / leverage.std()
beta_z = (low_beta - low_beta.mean()) / low_beta.std()
vol_z = (low_volatility - low_volatility.mean()) / low_volatility.std()

safety_score = (leverage_z + beta_z + vol_z) / 3
```

### Payout Component
Metric: `(Dividends + Buybacks) / Net Income`

```python
net_payout = (DVT + PRSTKC) / IB
payout_score = (net_payout - net_payout.mean()) / net_payout.std()
```

### Composite Quality Score
```python
# Equal-weighted average
quality_score = (profitability_score + growth_score + safety_score + payout_score) / 4

# Use skipna=True to handle missing components
quality_score = df[components].mean(axis=1, skipna=True)
```

**From paper (Appendix IA.I):**
> "If a particular measure is missing due to lack of data availability, we simply average the remaining ones."

---

## Step 3: The Triple Combo Methodology

### 3.1 Industry-Neutral Z-Scoring
Uses Fama-French 12 industries based on SIC codes.

```python
def classify_ff12_industry(siccd):
    if pd.isna(siccd):
        return 12
    siccd = int(siccd)

    if 1 <= siccd <= 999: return 1
    elif 1000 <= siccd <= 1499: return 2
    # ... etc (see code for full mapping)
    else: return 12
```

Z-score each component within date-industry groups:
```python
for component in [profitability_score, growth_score, safety_score, payout_score]:
    df[component] = df.groupby(['date', 'industry'])[component].transform(
        lambda x: (x - x.mean()) / x.std() if x.std() > 0 else x
    )
```

Industry z-scoring happens FIRST.

### 3.2 NYSE-Only Normalization
```python
for component in [profitability_score, growth_score, safety_score, payout_score]:
    # Calculate mean and std using ONLY NYSE stocks
    nyse_stats = df[df['exchcd'] == 1].groupby('date')[component].agg(['mean', 'std'])

    # Apply to ALL stocks
    df = df.merge(nyse_stats, on='date', how='left')
    df[component] = (df[component] - nyse_mean) / nyse_std
```

NYSE normalization happens SECOND, after industry z-scoring.

### 3.3 Return Winsorization (7%/93%)
```python
df['ret'] = df.groupby('date')['ret'].transform(
    lambda x: x.clip(lower=x.quantile(0.07), upper=x.quantile(0.93))
)
```

This is symmetric and applied to returns, not quality scores.

---

## Step 4: Portfolio Formation

### Industry Filters
```python
# Exclude financial firms (SIC 6000-6999)
df = df[~((df['siccd'] >= 6000) & (df['siccd'] < 7000))]

# Exclude utilities (SIC 4900-4999)
df = df[~((df['siccd'] >= 4900) & (df['siccd'] < 5000))]
```

### NYSE Breakpoints
```python
# For each month:
# 1. Calculate decile breakpoints using ONLY NYSE stocks
nyse_breakpoints = df[df['exchcd'] == 1]['quality_score'].quantile([0.1, 0.2, ..., 0.9])

# 2. Assign ALL stocks to portfolios
df['portfolio'] = pd.cut(df['quality_score'],
                         bins=[-np.inf, *nyse_breakpoints, np.inf],
                         labels=range(1, 11))
```

### Value Weighting
```python
# For each portfolio-month
portfolio_return = sum(market_cap_i * return_i) / sum(market_cap_i)
```

Formula:
```
R_p,t = Σ(w_i,t * r_i,t)
where w_i,t = market_cap_i,t / Σ(market_cap_i,t)
```

### Monthly Rebalancing
Timeline example:
- Fiscal year ends: 2008-06-30
- Data available: 2008-10-31 (4-month lag)
- Sort stocks: 2008-10-31
- Hold portfolio: November 2008
- Record return: November 2008

---

## Step 5: Calculate Excess Returns

### Merge with Risk-Free Rate
```python
portfolio_returns['year_month'] = portfolio_returns['date'].dt.to_period('M')
ff_factors['year_month'] = ff_factors['date'].dt.to_period('M')

merged = portfolio_returns.merge(ff_factors[['year_month', 'rf']],
                                 on='year_month', how='inner')
```

### Calculate Excess Returns
```python
excess_return = portfolio_return - risk_free_rate
excess_return_pct = excess_return * 100  # for Table IV
```

### Time-Series Average
```python
mean_excess_return = excess_return_pct.mean()
```

---

## Common Implementation Issues

### Wrong Winsorization
❌ Asymmetric (7%/95%), one-sided, or different levels
✓ Symmetric 7%/93% on returns

### Wrong Portfolio Weighting
❌ Equal-weighted portfolios
✓ Value-weighted by market capitalization

### Wrong Order of Operations
❌ NYSE normalization before industry z-scoring
✓ Industry z-scoring FIRST, then NYSE normalization

### Too Restrictive Filters
❌ Price filters ($1, $5), requiring all 4 components
✓ Follow paper specifications only

### Wrong Link Criteria
❌ Only LINKTYPE='LU' and LINKPRIM='P'
✓ LINKTYPE IN ('LC','LU') and LINKPRIM IN ('P','C')

---

## Data Vintage Considerations

### Why Perfect Replication is Difficult

1. **Compustat Restatements**
   - Companies revise historical financials
   - Paper used 2012-2013 WRDS data
   - Current data reflects all subsequent restatements

2. **CRSP Corrections**
   - Historical returns occasionally corrected
   - Delisting events may be reclassified

3. **Undocumented Details**
   - Some implementation details not in paper
   - Proprietary data cleaning procedures

---

## References

Asness, C. S., Frazzini, A., & Pedersen, L. H. (2019). Quality minus junk. *Review of Accounting Studies*, 24(1), 34-112.

Fama, E. F., & French, K. R. (1993). Common risk factors in the returns on stocks and bonds. *Journal of Financial Economics*, 33(1), 3-56.
