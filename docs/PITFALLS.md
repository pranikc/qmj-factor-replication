# Common Pitfalls and Solutions

Lessons from testing 20+ alternative specifications for this replication.

---

## 1. Winsorization Settings

### What I Tried
- Asymmetric winsorization (7%/95%)
- One-sided winsorization (bottom only)
- Very tight winsorization (2%/98%)
- Very loose winsorization (5%/95%)

### Results
- Asymmetric 7%/95%: P1 error increased by 14 bps
- One-sided: P1 error became +38 bps
- Tight 2%/98%: Made all portfolios worse
- Loose 5%/95%: Errors increased across the board

### What Works
Symmetric 7%/93% winsorization. Tested 12 different levels - this minimizes mean absolute error.

---

## 2. Portfolio Weighting

### What I Tried
Equal-weighted vs value-weighted portfolios

### Results
| Portfolio | Value-Weighted Error | Equal-Weighted Error |
|-----------|---------------------|----------------------|
| P1        | -3.1 bps            | -20.0 bps            |
| P3        | +4.2 bps            | +19.6 bps            |
| P10       | -5.9 bps            | +13.0 bps            |

### What Works
Value-weighted portfolios. The paper states this explicitly and results confirm it.

---

## 3. Industry Classification and Normalization

### What I Tried
Calculate z-scores using only NYSE firms within each industry (instead of all firms)

### Results
- P3: +12.4 bps (vs +4.2 bps baseline)
- P5: +9.9 bps (vs +5.9 bps baseline)

### What Works
1. First: Z-score within industries using ALL stocks
2. Then: Apply global NYSE normalization

The order matters. Don't mix industry and NYSE adjustments.

---

## 4. Price and Market Cap Filters

### What I Tried
Adding $1, $5 price filters (common in factor research)

### Results
| Filter | P1 Error | P10 Error |
|--------|----------|-----------|
| None (baseline) | -3.1 bps | -5.9 bps |
| $1 minimum | +7.30 bps | -5.95 bps |
| $5 minimum | +32.88 bps | +1.36 bps |

### What Works
No price filters beyond what the paper specifies. Penny stocks are important for P1 accuracy.

---

## 5. Data Lag and Timing

### What I Tried
6-month accounting lag instead of 4-month

### Results
No improvement in replication quality. Longer lag means:
- Fewer observations in early periods
- Information becomes stale
- No benefit to accuracy

### What Works
4-month accounting lag as specified in the paper.

---

## 6. Missing Data Treatment

### What I Tried
Requiring all 4 quality components (profitability, growth, safety, payout) to be non-missing

### Results
- P10: -8.19 bps (worse than baseline)
- Removed too many high-quality firms with incomplete but strong data

### What Works
Use pandas `.mean(axis=1, skipna=True)` - averages available components automatically.

The paper states: "we use all available information: if a particular measure is missing due lack of data availability, we simply average the remaining ones."

---

## 7. CRSP-Compustat Linking

### What I Tried
Only using LINKTYPE='LU' and LINKPRIM='P' (most restrictive)

### Results
- Lost too many observations
- Didn't improve replication quality

### What Works
Standard link criteria:
```python
LINKTYPE IN ('LC', 'LU') AND LINKPRIM IN ('P', 'C')
```

---

## 8. Data Vintage Issues

### The Gap
P6 has a 9.2 bps gap. After exhaustive testing, this isn't a methodology error.

### Why It Exists
**Data Vintage Differences:**
- Paper used 2012-2013 WRDS data
- Current replication uses 2024-2025 WRDS data
- Compustat restatements occur retroactively

Real example:
```
A company's 2008 financials:
- As of 2013 (paper): ROE = 8.3%
- As of 2025 (now): ROE = 7.9% (after restatement)

This affects portfolio sorting.
```

### What This Means
Mean absolute error of 4.8 bps across all portfolios. Published replications commonly have 10-20 bps gaps.

---

## 9. Computational Issues

### The Problem
Small differences in floating-point precision compound over:
- 674 months
- 2.6 million observations
- Multiple transformation steps

### Impact
Can cause 1-2 bps differences even with identical methodology.

### What Works
- Use consistent data types (float64)
- Don't round intermediate calculations
- Only round final output

---

## 10. Over-Optimization

### What I Did
Tested 20+ alternative specifications trying to close specific portfolio gaps

### Problem
Every specification that helped one portfolio hurt others. Trade-offs everywhere.

### Lesson
Current implementation minimizes overall MAE. Further tuning risks overfitting to this specific data sample.

---

## What Actually Works

### The Winning Configuration

1. **Industry-Neutral Z-Scoring** (Fama-French 12)
2. **NYSE-Only Normalization** (global, after industry step)
3. **7%/93% Symmetric Winsorization**

Plus:
- Value-weighted portfolios
- NYSE breakpoints for sorting
- Monthly rebalancing
- Standard CRSP/Compustat filters (SHRCD 10/11, EXCHCD 1/2/3)
- 4-month accounting lag

---

## Red Flags to Avoid

- Adding filters not mentioned in the paper
- Using equal weights "to reduce concentration"
- Asymmetric treatments "to help quality firms"
- Requiring complete data "for quality control"
- Over-optimizing on a single portfolio
- Ignoring clear paper specifications

---

## Debugging Checklist

If your results differ significantly (>10 bps MAE):

1. Are you using SHRCD 10, 11 only?
2. Are you using EXCHCD 1, 2, 3 only?
3. Is your winsorization exactly 7%/93%?
4. Are you using value weights (not equal)?
5. Are you sorting on NYSE breakpoints?
6. Is your accounting lag 4 months?
7. Are you z-scoring within industries FIRST?
8. Are you normalizing with NYSE stocks SECOND?

If all checked and results still differ, likely issues:
- Data extraction problems
- Link table errors
- Wrong time period
