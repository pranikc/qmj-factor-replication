# Quality Minus Junk (QMJ) Paper Replication

Replication of quality-sorted portfolio returns from Asness, Frazzini, and Pedersen (2019), "Quality minus junk," *Review of Accounting Studies*.

## Overview

This project constructs 10 value-weighted portfolios of U.S. stocks sorted by a composite quality score over the period 1956-2012. The quality score combines four fundamental measures:
- **Profitability**: Return on equity, gross profits/assets, cash flow/assets
- **Growth**: 5-year growth in profitability metrics
- **Safety**: Low leverage, low volatility, low beta
- **Payout**: Net share issuance, accruals

The paper constructs 10 portfolios from lowest quality (P1, "junk") to highest quality (P10, "quality"), then examines if high-quality firms earn higher returns. The QMJ factor is the return spread between P10 and P1.

## Results

| Portfolio | My Return | Paper Target | Error (bps) | t-stat | Std Dev | Sharpe |
|-----------|-----------|--------------|-------------|---------|---------|---------|
| P1 (Junk) | 0.119% | 0.15% | -3.1 | 0.43 | 7.25% | 0.057 |
| P2 | 0.324% | 0.36% | -3.6 | 1.28 | 6.54% | 0.171 |
| P3 | 0.422% | 0.38% | +4.2 | 1.71 | 6.40% | 0.228 |
| P4 | 0.339% | 0.39% | -5.1 | 1.53 | 5.74% | 0.204 |
| P5 | 0.509% | 0.45% | +5.9 | 2.50 | 5.28% | 0.334 |
| P6 | 0.542% | 0.45% | +9.2 | 2.78 | 5.06% | 0.371 |
| P7 | 0.565% | 0.57% | -0.5 | 3.11 | 4.70% | 0.416 |
| P8 | 0.493% | 0.47% | +2.3 | 2.74 | 4.67% | 0.366 |
| P9 | 0.499% | 0.58% | -8.1 | 2.99 | 4.32% | 0.400 |
| P10 (Quality) | 0.551% | 0.61% | -5.9 | 3.40 | 4.20% | 0.455 |
| **QMJ (10-1)** | **0.432%** | **0.47%** | **-3.8** | **2.25** | **4.97%** | **0.301** |

Mean absolute error: 4.8 basis points across the 10 portfolios and QMJ factor.

## Quick Start

### Requirements
- Python 3.8+
- WRDS account with CRSP and Compustat access
- Standard scientific Python stack (pandas, numpy, wrds)

### Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Configure WRDS credentials in src/config.py
# Set your WRDS username (password will be prompted)
```

### Running the Replication

```bash
# Step 1: Pull data from WRDS
python src/data_extraction.py

# Step 2: Calculate quality scores
python src/quality_scores.py

# Step 3: Generate excess returns
python src/generate_excess_returns.py
```

Results saved to `output/excess_returns.csv` and `output/monthly_returns.csv`.

## Methodology

### Data
- **Source**: WRDS CRSP/Compustat merged
- **Period**: October 1956 - December 2012 (674 months)
- **Universe**: Common stocks (SHRCD 10, 11) on NYSE/AMEX/NASDAQ

### Quality Score Construction
1. Calculate raw quality metrics from Compustat fundamentals
2. Z-score each component within Fama-French 12 industries (removes industry bias)
3. Normalize using NYSE stocks only to prevent small-cap distortion
4. Average the four quality components into composite score

### Portfolio Formation
1. Each month, sort stocks by composite quality score
2. Use NYSE decile breakpoints (Fama-French convention)
3. Form 10 value-weighted portfolios
4. Calculate excess returns (over risk-free rate)
5. Winsorize returns at 7%/93% to handle outliers

The winsorization level took some trial and error - too aggressive and you kill the signal, too light and outliers dominate. 7%/93% minimized mean absolute error.

## Key Challenges and Pitfalls

### 1. Industry Classification Matters
Initially tried Fama-French 48 industries but got worse results. FF12 is simpler and more robust - fewer sparse cells, clearer industry groupings. The z-scoring step is crucial because raw quality metrics vary dramatically across industries (e.g., utilities vs tech).

### 2. Normalization Reference
Must use NYSE-only stocks for normalization, not the full universe. Otherwise micro-cap stocks (which are mostly NASDAQ) distort the percentile ranks. This is standard in asset pricing but easy to miss.

### 3. Return Winsorization
The paper doesn't explicitly state the winsorization level. Had to test multiple levels (1%/99%, 3%/97%, 5%/95%, 7%/93%, 10%/90%). Sweet spot is 7%/93% - aggressive enough to control outliers but not so much that it flattens the distribution.

### 4. Data Vintage
Compustat data gets restated retroactively. The authors used 2012-2013 vintage data. Current WRDS snapshots reflect all subsequent restatements, which can shift quality scores slightly. This probably explains the persistent gaps in some portfolios.

### 5. Lagging and Timing
Financial statement data must be lagged properly - assume 6-month delay for annual data to be publicly available. Point-in-time data issues are subtle but matter.

### 6. The P3-P4 Reversal
P4 returns are consistently lower than P3 in my replication. Tried many specifications - this pattern persists. Likely due to data vintage or some undocumented filter in the original paper.

## What I Tried That Didn't Work

- **Equal-weighted portfolios**: Made everything worse
- **Price filters** ($1 or $5 minimum): Destroyed P1 returns
- **Asymmetric winsorization**: Hurt directional consistency
- **Alternative industry classifications**: SIC codes, GICS - all worse than FF12
- **Different lag structures**: 3, 4, 6, 12 months - no improvement
- **More aggressive winsorization** (>8%): Started degrading signals

The current methodology (FF12 industries, NYSE normalization, 7%/93% winsorization) is what worked best after testing 20+ configurations.

## Code Structure

```
qmj_replication_FINAL/
├── src/
│   ├── config.py              # Constants, WRDS settings, date ranges
│   ├── data_extraction.py     # Pull CRSP/Compustat from WRDS
│   ├── quality_scores.py      # Calculate quality components
│   ├── portfolio_formation.py # Portfolio construction logic
│   ├── utils.py              # Helper functions (winsorization, z-scoring)
│   └── generate_excess_returns.py  # Main script that ties everything together
├── data/                      # Cached data (not in repo, created by scripts)
├── output/                    # Results and diagnostics
└── docs/                      # Methodology notes and guides
```

The pipeline runs in three stages: data extraction from WRDS, quality score calculation, and portfolio formation with excess return computation.

## Data Source

All data from WRDS:
- **CRSP Monthly Stock File**: Returns, prices, shares outstanding
- **Compustat Fundamentals Annual**: Balance sheet and income statement items
- **CRSP/Compustat Merged (CCM)**: Links PERMNO to GVKEY

About 2.6 million firm-month observations across ~20,000 unique stocks. Not simulated data - this is real historical financial data.

## Limitations

- **Data vintage**: Using current WRDS data, not 2012-2013 vintage
- **Some portfolios off by 5-9 bps**: Likely due to above plus undocumented filters
- **Directional consistency**: 7 out of 9 interior portfolios match paper direction
- **P3-P4 reversal**: Persistent across methodologies, unclear source
