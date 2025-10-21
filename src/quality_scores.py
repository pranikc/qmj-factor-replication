"""
Quality Score Calculation
Calculates the four QMJ quality components: Profitability, Growth, Safety, and Payout.
"""

import pandas as pd
import numpy as np
from scipy import stats
from typing import List, Optional
import config
import utils


class QualityScoreCalculator:

    def __init__(self, data: pd.DataFrame):
        self.data = data.copy()
        self.data['date'] = pd.to_datetime(self.data['date'])

    def calculate_profitability_measures(self) -> pd.DataFrame:
        """
        Calculate profitability measures.

        Measures:
        1. Gross Profitability = (REVT - COGS) / AT
        2. ROE = IB / SEQ
        3. ROA = IB / AT
        4. Cash Flow / Assets = (IB + DP) / AT
        5. Gross Margin = (REVT - COGS) / REVT
        6. Accruals = (IB - OANCF) / AT (negative = quality)

        Output:
            Dataframe with profitability measures
        """
        print("\nCalculating profitability measures...")

        df = self.data.copy()

        # 1. Gross Profitability
        df['gross_prof'] = (df['revt'] - df['cogs']) / df['at']

        # 2. ROE
        df['roe'] = df['ib'] / df['seq']

        # 3. ROA
        df['roa'] = df['ib'] / df['at']

        # 4. Cash Flow / Assets
        df['cf_assets'] = (df['ib'] + df['dp']) / df['at']

        # 5. Gross Margin
        df['gross_margin'] = (df['revt'] - df['cogs']) / df['revt']

        # 6. Accruals (LOWER = BETTER, so flip sign)
        df['accruals'] = -1 * (df['ib'] - df['oancf']) / df['at']

        # Count non-missing measures
        prof_measures = ['gross_prof', 'roe', 'roa', 'cf_assets', 'gross_margin', 'accruals']
        df['n_prof_measures'] = df[prof_measures].notna().sum(axis=1)

        print("Calculated profitability measures")
        for measure in prof_measures:
            pct_available = (df[measure].notna().sum() / len(df)) * 100
            print(f"  {measure}: {pct_available:.1f}% available")

        self.data = df
        return self.data

    def calculate_growth_measures(self, window_years: int = 5) -> pd.DataFrame:
        """
        Calculate growth measures (5-year changes in profitability).

        Input:
            window_years: Number of years for growth calculation

        Output:
            DataFrame with growth measures
        """
        print(f"\nCalculating {window_years}-year growth measures...")

        df = self.data.copy()
        window_months = window_years * 12

        # Growth in profitability measures
        growth_base_measures = ['gross_prof', 'roe', 'roa', 'gross_margin']

        for measure in growth_base_measures:
            growth_col = f'{measure}_growth'
            # Calculate percent change over window
            df[growth_col] = df.groupby('permno')[measure].pct_change(periods=window_months)

        # Count non-missing growth measures
        growth_measures = [f'{m}_growth' for m in growth_base_measures]
        df['n_growth_measures'] = df[growth_measures].notna().sum(axis=1)

        print("Calculated growth measures")
        for measure in growth_measures:
            pct_available = (df[measure].notna().sum() / len(df)) * 100
            print(f"  {measure}: {pct_available:.1f}% available")

        self.data = df
        return self.data

    def calculate_safety_measures(self) -> pd.DataFrame:
        """
        Calculate safety measures.

        Measures:
        1. Beta (negative = quality) - estimated from monthly returns if not provided
        2. Idiosyncratic volatility (negative = quality) - estimated from monthly returns if not provided
        3. Leverage = (DLC + DLTT) / AT (negative = quality)
        4. Z-score (Altman) - higher = safer
        5. ROE volatility (negative = quality)

        NOTE: We flip signs for measures where LOWER = BETTER before z-scoring
        This ensures all measures point in the same direction (higher = better quality)

        Output:
            Dataframe with safety measures
        """
        print("\nCalculating safety measures...")

        df = self.data.copy()

        # 1. Leverage (LOWER = BETTER, so flip sign)
        df['leverage'] = -1 * (df['dlc'] + df['dltt']) / df['at']

        # 2. Altman Z-score
        # Z = 1.2*X1 + 1.4*X2 + 3.3*X3 + 0.6*X4 + 1.0*X5
        # X1 = Working Capital / Total Assets
        # X2 = Retained Earnings / Total Assets
        # X3 = EBIT / Total Assets
        # X4 = Market Value of Equity / Book Value of Total Liabilities
        # X5 = Sales / Total Assets
        df['z_score'] = (
            1.2 * ((df['act'] - df['lct']) / df['at']).fillna(0) +  # Working capital ratio
            1.4 * (df['re'] / df['at']).fillna(0) +  # Retained earnings ratio
            3.3 * (df['ib'] / df['at']).fillna(0) +  # Profitability
            0.6 * (df['mkt_cap'] / (df['dlc'] + df['dltt']).replace(0, np.nan)).fillna(0) +  # Market value of equity / debt
            1.0 * (df['revt'] / df['at']).fillna(0)  # Asset turnover
        )

        # 3. ROE volatility (LOWER = BETTER, so flip sign after calculating std)
        df['roe_vol'] = -1 * df.groupby('permno')['roe'].transform(
            lambda x: x.rolling(window=60, min_periods=36).std()
        )

        # 4. Beta - if not already in data, we can estimate separately
        # Note: Beta values will be stored as-is initially, then flipped before z-scoring
        if 'beta' not in df.columns:
            df['beta'] = np.nan
        # Apply sign flip: low beta = high safety quality
        # Only flip non-NaN values to preserve NaN structures
        df['beta_raw'] = df['beta']
        df['beta'] = np.where(df['beta'].notna(), -1 * df['beta'], np.nan)

        # 5. Idiosyncratic volatility - if not already in data, will also be estimated separately
        if 'idio_vol' not in df.columns:
            df['idio_vol'] = np.nan

        df['idio_vol_raw'] = df['idio_vol']
        df['idio_vol'] = np.where(df['idio_vol'].notna(), -1 * df['idio_vol'], np.nan)

        # Count non-missing measures
        safety_measures = ['leverage', 'z_score', 'roe_vol', 'beta', 'idio_vol']
        df['n_safety_measures'] = df[safety_measures].notna().sum(axis=1)

        print("Calculated safety measures")
        for measure in safety_measures:
            pct_available = (df[measure].notna().sum() / len(df)) * 100
            print(f"  {measure}: {pct_available:.1f}% available")

        self.data = df
        return self.data

    def calculate_payout_measures(self) -> pd.DataFrame:
        """
        Calculate payout measures.

        Measures:
        1. Dividend Payout = DVC / IB
        2. Net Equity Issuance (negative = quality)
        3. Total Payout = (DVC + PRSTKC) / IB

        Output:
            Dataframe with payout measures
        """
        print("\nCalculating payout measures...")

        df = self.data.copy()

        # 1. Dividend payout ratio
        df['div_payout'] = df['dvc'] / df['ib'].replace(0, np.nan)

        # 2. Net equity issuance (LOWER = BETTER, so flip sign)
        # Change in market equity = (Shares_t * Price_t) - (Shares_t-1 * Price_t-1)
        df['lag_market_equity'] = df.groupby('permno').apply(
            lambda x: (x['csho'] * x['prcc_f']).shift(1)
        ).reset_index(level=0, drop=True)

        df['current_market_equity'] = df['csho'] * df['prcc_f']

        df['net_issuance'] = -1 * (
            (df['current_market_equity'] - df['lag_market_equity']) /
            df['lag_market_equity'].replace(0, np.nan)
        )

        # 3. Total payout ratio
        df['total_payout'] = (df['dvc'] + df['prstkc']) / df['ib'].replace(0, np.nan)

        # Count non-missing measures
        payout_measures = ['div_payout', 'net_issuance', 'total_payout']
        df['n_payout_measures'] = df[payout_measures].notna().sum(axis=1)

        print("Calculated payout measures")
        for measure in payout_measures:
            pct_available = (df[measure].notna().sum() / len(df)) * 100
            print(f"  {measure}: {pct_available:.1f}% available")

        self.data = df
        return self.data

    def winsorize_and_standardize(
        self,
        measures: List[str],
        lower: float = 0.01,
        upper: float = 0.99
    ) -> pd.DataFrame:
        """
        Winsorize and z-score standardize measures cross-sectionally.

        Inputs:
            measures: List of measure column names
            lower: Lower percentile for winsorization
            upper: Upper percentile for winsorization

        Output:
            Dataframe with winsorized and standardized measures
        """
        print(f"\nWinsorizing and standardizing {len(measures)} measures...")

        df = self.data.copy()

        for measure in measures:
            if measure not in df.columns:
                print(f"  Warning: {measure} not found, skipping")
                continue

            # Cross-sectional winsorization (by date)
            wins_col = f'{measure}_wins'
            df[wins_col] = df.groupby('date')[measure].transform(
                lambda x: utils.winsorize_series(x, lower, upper)
            )

            # Cross-sectional z-score standardization
            z_col = f'{measure}_z'
            df[z_col] = df.groupby('date')[wins_col].transform(
                lambda x: utils.zscore_series(x)
            )

        print("Winsorized and standardized measures")

        self.data = df
        return self.data

    def calculate_component_scores(self) -> pd.DataFrame:
        """
        Calculate the four quality component scores by averaging z-scored measures.

        Output:
            Dataframe with corresponding component scores
        """
        print("\nCalculating quality component scores...")

        df = self.data.copy()

        # Profitability score (all signs have been flipped before z-scoring, so we just average)
        prof_measures = ['gross_prof_z', 'roe_z', 'roa_z', 'cf_assets_z', 'gross_margin_z', 'accruals_z']
        df['profitability_score'] = df[prof_measures].mean(axis=1)

        # Growth score
        growth_measures = [
            'gross_prof_growth_z', 'roe_growth_z',
            'roa_growth_z', 'gross_margin_growth_z'
        ]
        df['growth_score'] = df[growth_measures].mean(axis=1)

        # Safety score
        safety_measures = ['z_score_z', 'leverage_z', 'beta_z', 'idio_vol_z', 'roe_vol_z']
        df['safety_score'] = df[safety_measures].mean(axis=1)

        # Payout score
        payout_measures = ['div_payout_z', 'total_payout_z', 'net_issuance_z']
        df['payout_score'] = df[payout_measures].mean(axis=1)

        # Overall quality score (average of four components)
        component_scores = ['profitability_score', 'growth_score', 'safety_score', 'payout_score']
        df['quality_score_raw'] = df[component_scores].mean(axis=1)

        # Z-score standardize overall quality score
        df['quality_score'] = df.groupby('date')['quality_score_raw'].transform(
            lambda x: utils.zscore_series(x)
        )

        print("Calculated quality component scores")
        for component in component_scores + ['quality_score']:
            pct_available = (df[component].notna().sum() / len(df)) * 100
            mean_val = df[component].mean()
            std_val = df[component].std()
            print(f"  {component}: {pct_available:.1f}% available, mean={mean_val:.3f}, std={std_val:.3f}")

        self.data = df
        return self.data

    def calculate_all_scores(self) -> pd.DataFrame:
        """
        Calculate all quality scores in sequence.

        Output:
            Dataframe with all quality scores
        """
        print("\nCompleted Quality Score Calculation")

        # Calculate raw measures
        self.calculate_profitability_measures()
        self.calculate_growth_measures()
        self.calculate_safety_measures()
        self.calculate_payout_measures()

        # Collect all measures to winsorize and standardize
        all_measures = (
            config.PROFITABILITY_MEASURES +
            config.GROWTH_MEASURES +
            config.SAFETY_MEASURES +
            config.PAYOUT_MEASURES
        )

        # Filter to measures that exist in data
        existing_measures = [m for m in all_measures if m in self.data.columns]

        # Winsorize and standardize
        self.winsorize_and_standardize(
            existing_measures,
            lower=config.WINSORIZE_LOWER,
            upper=config.WINSORIZE_UPPER
        )

        # Calculate component scores
        self.calculate_component_scores()

        print("\nPhase 2 Complete: Quality Scores Calculated")

        return self.data


def estimate_beta_from_monthly_returns(
    data: pd.DataFrame,
    market_returns: pd.DataFrame,
    window_months: int = 60,
    min_obs: int = 36
) -> pd.DataFrame:
    """
    Estimate market beta using monthly returns (use as fallback when daily data unavailable).

    NOTE: Less precise than daily returns but better than missing betas entirely.
    Uses rolling 60-month window regression of stock returns on market returns.

    Inputs:
        data: DataFrame with columns ['permno', 'date', 'ret']
        market_returns: DataFrame with columns ['date', 'mkt_ret']
        window_months: Rolling window in months (default 60)
        min_obs: Minimum observations required (default 36)

    Output:
        Dataframe with columns ['permno', 'date', 'beta', 'idio_vol']
    """
    print(f"\nEstimating beta from monthly returns ({window_months}-month window)...")

    # Merge stock returns with market returns
    merged = data[['permno', 'date', 'ret']].merge(
        market_returns[['date', 'mkt_ret']],
        on='date',
        how='left'
    )

    # Sort by stock and date
    merged = merged.sort_values(['permno', 'date'])

    # Calculate rolling beta for each stock
    def calc_rolling_beta(group):
        betas = []
        idio_vols = []

        for i in range(len(group)):
            # Get rolling window
            start_idx = max(0, i - window_months + 1)
            window = group.iloc[start_idx:i+1]

            # Remove NaN values
            mask = window['ret'].notna() & window['mkt_ret'].notna()
            y = window.loc[mask, 'ret'].values
            x = window.loc[mask, 'mkt_ret'].values

            # Check if we have minimum observations
            if len(y) >= min_obs:
                # OLS regression: ret = alpha + beta * mkt_ret + epsilon
                slope, intercept, r, p, se = stats.linregress(x, y)

                # Beta is simply the slope
                betas.append(slope)

                # Idiosyncratic volatility is std of residuals
                predicted = intercept + slope * x
                residuals = y - predicted
                idio_vols.append(np.std(residuals))
            else:
                betas.append(np.nan)
                idio_vols.append(np.nan)

        group['beta'] = betas
        group['idio_vol'] = idio_vols

        return group[['permno', 'date', 'beta', 'idio_vol']]

    # Apply to each stock
    results = merged.groupby('permno', group_keys=False).apply(calc_rolling_beta)

    # Calculate coverage
    beta_coverage = (results['beta'].notna().sum() / len(results)) * 100
    idio_coverage = (results['idio_vol'].notna().sum() / len(results)) * 100

    print(f"Estimated beta for {results['permno'].nunique():,} stocks")
    print(f"  Beta coverage: {beta_coverage:.1f}%")
    print(f"  Idiosyncratic vol coverage: {idio_coverage:.1f}%")

    return results


def calculate_beta_from_daily_returns(
    daily_returns: pd.DataFrame,
    window_months: int = 60,
    min_obs: int = 36
) -> pd.DataFrame:
    """
    Calculate rolling market beta using daily returns.
    This is a separate function because it requires daily data.

    Inputs:
        daily_returns: DataFrame with columns ['permno', 'date', 'ret', 'mkt_ret']
        window_months: Rolling window in months
        min_obs: Minimum observations required

    Output:
        Dataframe with monthly betas
    """
    print(f"\nCalculating {window_months}-month rolling betas...")

    daily_returns = daily_returns.sort_values(['permno', 'date'])

    def calc_beta(group):
        window_days = window_months * 21  # Approximate trading days

        betas = []
        dates = []

        for i in range(len(group)):
            # Get window of data
            start_idx = max(0, i - window_days)
            window_data = group.iloc[start_idx:i+1]

            # Require minimum observations
            if len(window_data) >= min_obs * 21:
                # Estimate beta
                y = window_data['ret'].values
                x = window_data['mkt_ret'].values

                # Remove NaN values
                mask = ~(np.isnan(y) | np.isnan(x))
                y_clean = y[mask]
                x_clean = x[mask]

                if len(y_clean) >= min_obs * 21:
                    # OLS regression
                    slope, intercept, r, p, se = stats.linregress(x_clean, y_clean)
                    betas.append(slope)
                    dates.append(group.iloc[i]['date'])
                else:
                    betas.append(np.nan)
                    dates.append(group.iloc[i]['date'])
            else:
                betas.append(np.nan)
                dates.append(group.iloc[i]['date'])

        return pd.DataFrame({
            'date': dates,
            'beta': betas
        })

    # Calculate for all stocks
    beta_df = daily_returns.groupby('permno').apply(calc_beta).reset_index(drop=True)

    # Convert to monthly by taking month-end beta
    beta_df['month'] = pd.to_datetime(beta_df['date']).dt.to_period('M')
    monthly_beta = beta_df.groupby(['permno', 'month']).last().reset_index()
    monthly_beta['date'] = monthly_beta['month'].dt.to_timestamp()
    monthly_beta = monthly_beta[['permno', 'date', 'beta']]

    print(f"Calculated betas for {monthly_beta['permno'].nunique():,} stocks")

    return monthly_beta


def main():

    # Load merged data
    print("Loading merged CRSP-Compustat data...")
    data = utils.load_from_parquet(
        f"{config.DATA_DIR}/crsp_compustat_merged.parquet",
        "Merged CRSP-Compustat"
    )

    # Estimate beta and idiosyncratic volatility from monthly returns
    # We need market returns for this, therefore extract from the return data
    print("\nPreparing market returns for beta estimation...")

    # Create market returns DataFrame (value-weighted average of all stocks each month)
    market_data = data[['date', 'ret', 'mkt_cap']].copy()
    market_data = market_data[market_data['ret'].notna() & market_data['mkt_cap'].notna()]

    # Calculate value-weighted market return for each month
    market_returns = market_data.groupby('date').apply(
        lambda x: np.average(x['ret'], weights=x['mkt_cap'])
    ).reset_index()
    market_returns.columns = ['date', 'mkt_ret']

    # Estimate beta and idiosyncratic volatility
    beta_results = estimate_beta_from_monthly_returns(
        data=data,
        market_returns=market_returns,
        window_months=config.BETA_WINDOW_MONTHS,
        min_obs=config.BETA_MIN_OBSERVATIONS
    )

    # Merge beta and idio_vol back into main data
    print("\nMerging beta estimates into main dataset...")
    data = data.merge(
        beta_results[['permno', 'date', 'beta', 'idio_vol']],
        on=['permno', 'date'],
        how='left',
        suffixes=('', '_estimated')
    )

    # Use estimated values if original beta/idio_vol columns don't exist or are NaN
    if 'beta' not in data.columns or data['beta'].isna().all():
        data['beta'] = data['beta_estimated']
        data = data.drop(columns=['beta_estimated'], errors='ignore')

    if 'idio_vol' not in data.columns or data['idio_vol'].isna().all():
        data['idio_vol'] = data['idio_vol_estimated']
        data = data.drop(columns=['idio_vol_estimated'], errors='ignore')

    # Initialize calculator
    calculator = QualityScoreCalculator(data)

    # Calculate all scores
    data_with_scores = calculator.calculate_all_scores()

    # Save results
    utils.save_to_parquet(
        data_with_scores,
        f"{config.DATA_DIR}/data_with_quality_scores.parquet",
        "Data with quality scores"
    )

    # Summary statistics
    print("\nQuality Score Summary Statistics")

    quality_cols = [
        'profitability_score', 'growth_score',
        'safety_score', 'payout_score', 'quality_score'
    ]

    summary = data_with_scores[quality_cols].describe()
    print(summary)


if __name__ == "__main__":
    main()
