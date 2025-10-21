import pandas as pd
import numpy as np
import logging
from typing import Optional, List, Tuple
from pathlib import Path


def setup_logging(log_file: str, log_level: str = "INFO") -> logging.Logger:
    logging.basicConfig(
        level=getattr(logging, log_level),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger(__name__)


def create_directories(dirs: List[str]) -> None:
    for dir_path in dirs:
        Path(dir_path).mkdir(parents=True, exist_ok=True)


def winsorize_series(series: pd.Series, lower: float = 0.01, upper: float = 0.99) -> pd.Series:
    """
    Winsorize a pandas Series at specified percentiles.

    Inputs:
        series: Input series
        lower: Lower percentile
        upper: Upper percentile

    Output:
        Winsorized series
    """
    lower_bound = series.quantile(lower)
    upper_bound = series.quantile(upper)

    # Handle cases where quantiles are NaN (for example, all values are NaN or insufficient data)
    if pd.isna(lower_bound) or pd.isna(upper_bound):
        return series

    return series.clip(lower=lower_bound, upper=upper_bound)


def zscore_series(series: pd.Series) -> pd.Series:

    mean = series.mean()
    std = series.std()
    # Handle pd.NA and zero std separately to avoid boolean ambiguity
    if pd.isna(std):
        return pd.Series(np.nan, index=series.index)
    if std == 0:
        return pd.Series(np.nan, index=series.index)
    return (series - mean) / std


def rank_zscore_series(series: pd.Series) -> pd.Series:
    """
    Calculate rank-based z-scores (used in QMJ paper).
    Converts values to ranks, then scales to [-1, 1].
    """

    ranks = series.rank(method='average')
    n = len(ranks)
    if n <= 1:
        return pd.Series(np.nan, index=series.index)
    # Scale ranks to [-1, 1]
    return (ranks - 1) / (n - 1) * 2 - 1


def apply_delisting_adjustment(
    ret: float,
    dlret: float,
    dlstcd: int,
    exchcd: int,
    performance_codes: List[int],
    nyse_amex_ret: float = -0.30,
    nasdaq_ret: float = -0.55
) -> float:
    """
    Apply Shumway (1997) delisting return adjustment.

    Inputs:
        ret: Last trading return
        dlret: Delisting return (may be NaN)
        dlstcd: Delisting code
        exchcd: Exchange code (1=NYSE, 2=AMEX, 3=NASDAQ)
        performance_codes: List of performance-related delisting codes
        nyse_amex_ret: Default return for NYSE/AMEX performance delists
        nasdaq_ret: Default return for NASDAQ performance delists

    Output:
        Adjusted total return
    """
    # If delisting return exists, use it
    if not pd.isna(dlret):
        return (1 + ret) * (1 + dlret) - 1

    # If delisting code indicates performance-related and dlret is missing
    if dlstcd in performance_codes:
        # Use appropriate default based on exchange
        default_dlret = nasdaq_ret if exchcd == 3 else nyse_amex_ret
        return (1 + ret) * (1 + default_dlret) - 1

    # Otherwise, just use trading return
    return ret


def calculate_value_weighted_return(
    returns: pd.Series,
    market_caps: pd.Series
) -> float:
    """
    Calculate value-weighted portfolio return.

    Inputs:
        returns: Series of stock returns
        market_caps: Series of market capitalizations (same index)

    Output:
        Value-weighted return
    """

    # Filter out missing values
    valid_mask = returns.notna() & market_caps.notna() & (market_caps > 0)
    returns_valid = returns[valid_mask]
    mcaps_valid = market_caps[valid_mask]

    if len(returns_valid) == 0:
        return np.nan

    # Calculate weights
    total_mcap = mcaps_valid.sum()
    weights = mcaps_valid / total_mcap

    # Value-weighted return
    return (returns_valid * weights).sum()


def fiscal_year_alignment(
    datadate: pd.Timestamp,
    fyr: int,
    lag_months: int = 4
) -> pd.Timestamp:
    """
    Determine when accounting data becomes available for portfolio formation.
    Following Fama-French methodology with conservative lag.

    Inputs:
        datadate: Fiscal year-end date
        fyr: Fiscal year-end month (1-12)
        lag_months: Lag in months for data availability (typically 4)

    Output:
        Date when data becomes available for use
    """
    # Data available lag_months after fiscal year end
    available_date = datadate + pd.DateOffset(months=lag_months)

    # Fama-French convention: Use in June of year t for fiscal year ending in t-1
    # We'll use a simpler approach: data available lag_months after fiscal year end
    #and used in portfolio formation from that point forward

    return available_date


def validate_data_coverage(
    df: pd.DataFrame,
    date_col: str,
    expected_start: str,
    expected_end: str
) -> Tuple[pd.Timestamp, pd.Timestamp, int]:

    actual_start = df[date_col].min()
    actual_end = df[date_col].max()
    n_months = df[date_col].nunique()

    print(f"\nData Coverage Report")
    print(f"Expected range: {expected_start} to {expected_end}")
    print(f"Actual range:   {actual_start} to {actual_end}")
    print(f"Number of months: {n_months}")
    print(f"Number of observations: {len(df):,}\n")

    return actual_start, actual_end, n_months


def calculate_summary_statistics(
    returns: pd.DataFrame,
    annualize: bool = True
) -> pd.DataFrame:

    mean_ret = returns.mean()
    std_ret = returns.std()
    sharpe = mean_ret / std_ret

    if annualize:
        mean_ret = mean_ret * 12 * 100  # Monthly to annual percentage
        std_ret = std_ret * np.sqrt(12) * 100
        sharpe = sharpe * np.sqrt(12)

    # Combine into DataFrame
    stats = pd.DataFrame({
        'Mean (%)': mean_ret,
        'Std (%)': std_ret,
        'Sharpe': sharpe,
        'N_months': returns.count()
    })

    return stats


def save_to_parquet(df: pd.DataFrame, filepath: str, description: str = "") -> None:

    df.to_parquet(filepath, index=False)
    size_mb = Path(filepath).stat().st_size / (1024 * 1024)
    print(f"Saved {description}: {filepath}")
    print(f"  Shape: {df.shape}, Size: {size_mb:.2f} MB")


def load_from_parquet(filepath: str, description: str = "") -> pd.DataFrame:

    df = pd.read_parquet(filepath)
    size_mb = Path(filepath).stat().st_size / (1024 * 1024)
    print(f"Loaded {description}: {filepath}")
    print(f"  Shape: {df.shape}, Size: {size_mb:.2f} MB")
    return df
