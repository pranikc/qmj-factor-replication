"""
This is the configuration file for QMJ Table replication.
Contains all parameters, constants, and paths for the replication.
"""

# WRDS Connection
WRDS_USERNAME = "pranikc"
WRDS_PASSWORD = "Pranik0993$Pranik0993$"

# Sample Period (Table IV Panel A - US Long Sample)
START_DATE = "1956-06-01"
END_DATE = "2012-12-31"

# Stock Universe Filters
VALID_SHARE_CODES = [10, 11]  # US common stocks only
VALID_EXCHANGE_CODES = [1, 2, 3]  # NYSE, AMEX, NASDAQ

# CCM Link Filters
VALID_LINK_TYPES = ['LC', 'LU']  # Link complete, Link by CUSIP
VALID_LINK_PRIMS = ['P', 'C']  # Primary links only

# Point-in-Time Data
ACCOUNTING_LAG_MONTHS = 6  # 6-month lag per Asness et al.: "end of fiscal year t-1 to June of year t"

# Portfolio Formation
N_PORTFOLIOS = 10  # Deciles for Table IV
USE_NYSE_BREAKPOINTS = True  # Calculate breakpoints using NYSE stocks only
VALUE_WEIGHTED = True  # Value-weighted portfolios

# Winsorization
WINSORIZE_LOWER = 0.01
WINSORIZE_UPPER = 0.99

# Delisting Return Adjustments (Shumway 1997)
DELISTING_RETURN_NYSE_AMEX = -0.30  # -30% for NYSE/AMEX performance delists
DELISTING_RETURN_NASDAQ = -0.30  # -30% for NASDAQ (paper uses -30% for ALL US stocks per AFP 2019)
PERFORMANCE_DELISTING_CODES = [500, 520] + list(range(551, 585))  # Performance-related

# File Paths
DATA_DIR = "/Users/pranikchainani/qmj_replication_FINAL/data"
INTERMEDIATE_DIR = "/Users/pranikchainani/qmj_replication_FINAL/data/intermediate"
OUTPUT_DIR = "/Users/pranikchainani/qmj_replication_FINAL/output"
CACHE_DIR = "/Users/pranikchainani/qmj_replication_FINAL/data/cache"

# AQR Validation Data URL
AQR_QMJ_10_PORTFOLIOS_URL = "https://www.aqr.com/-/media/AQR/Documents/Insights/Data-Sets/Quality-Minus-Junk-10-Quality-Sorted-Portfolios-Monthly.xlsx"

# Fama-French Factors
FF_DATA_URL = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/"

# Quality Score Components
# Each component will be calculated as average of z-scored measures
PROFITABILITY_MEASURES = [
    'gross_prof',  # (REVT - COGS) / AT
    'roe',         # IB / SEQ
    'roa',         # IB / AT
    'cf_assets',   # (IB + DP) / AT
    'gross_margin',# (REVT - COGS) / REVT
    'accruals'     # (IB - OANCF) / AT (negative = quality)
]

GROWTH_MEASURES = [
    'gross_prof_growth',
    'roe_growth',
    'roa_growth',
    'gross_margin_growth'
]

SAFETY_MEASURES = [
    'beta',        # Market beta (negative = quality)
    'idio_vol',    # Idiosyncratic volatility (negative = quality)
    'leverage',    # Total debt / assets (negative = quality)
    'z_score',     # Altman Z-score (higher = safer)
    'roe_vol'      # ROE volatility (negative = quality)
]

PAYOUT_MEASURES = [
    'div_payout',      # DVC / IB
    'net_issuance',    # Equity issuance (negative = quality)
    'total_payout'     # (DVC + PRSTKC) / IB
]

# Beta Estimation Parameters
BETA_WINDOW_MONTHS = 60  # 5 years
BETA_MIN_OBSERVATIONS = 36  # Minimum 3 years

# Logging
LOG_LEVEL = "INFO"
LOG_FILE = "/Users/pranikchainani/qmj_replication_FINAL/qmj_replication.log"
