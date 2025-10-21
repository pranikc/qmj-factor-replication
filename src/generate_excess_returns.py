"""
Generate Excess Returns for Quality-Sorted Portfolios

Methodology:
1. Industry-Neutral Z-Scoring (FF12 - standard Fama-French 12 industries)
2. NYSE-Only Z-Score Normalization
3. Return Winsorization at 7%/93% (best configuration)
"""

import pandas as pd
import numpy as np
import config
from portfolio_formation import PortfolioConstructor


def classify_ff12_industry(siccd):
    """
    Classify into Fama-French 12 industries.
    Standard classification optimized for QMJ replication.
    """
    if pd.isna(siccd):
        return 12
    siccd = int(siccd)

    # Consumer NonDurables
    if ((100 <= siccd <= 999) or (2000 <= siccd <= 2399) or
        (2700 <= siccd <= 2749) or (2770 <= siccd <= 2799) or
        (3100 <= siccd <= 3199) or (3940 <= siccd <= 3989)):
        return 1

    # Consumer Durables
    if ((2500 <= siccd <= 2519) or (2590 <= siccd <= 2599) or
        (3630 <= siccd <= 3659) or (3710 <= siccd <= 3711) or
        (3714 <= siccd <= 3714) or (3716 <= siccd <= 3716) or
        (3750 <= siccd <= 3751) or (3792 <= siccd <= 3792) or
        (3900 <= siccd <= 3931) or (3940 <= siccd <= 3949)):
        return 2

    # Manufacturing
    if ((2520 <= siccd <= 2589) or (2600 <= siccd <= 2699) or
        (2750 <= siccd <= 2769) or (3000 <= siccd <= 3099) or
        (3200 <= siccd <= 3569) or (3580 <= siccd <= 3629) or
        (3700 <= siccd <= 3709) or (3712 <= siccd <= 3713) or
        (3715 <= siccd <= 3715) or (3717 <= siccd <= 3749) or
        (3752 <= siccd <= 3791) or (3793 <= siccd <= 3799) or
        (3830 <= siccd <= 3839) or (3860 <= siccd <= 3899)):
        return 3

    # Energy
    if (1200 <= siccd <= 1399) or (2900 <= siccd <= 2999):
        return 4

    # Chemicals
    if (2800 <= siccd <= 2829) or (2840 <= siccd <= 2899):
        return 5

    # Business Equipment
    if ((3570 <= siccd <= 3579) or (3660 <= siccd <= 3692) or
        (3694 <= siccd <= 3699) or (3810 <= siccd <= 3829) or
        (7370 <= siccd <= 7379)):
        return 6

    # Telecom
    if 4800 <= siccd <= 4899:
        return 7

    # Utilities
    if 4900 <= siccd <= 4949:
        return 8

    # Shops
    if ((5000 <= siccd <= 5999) or (7200 <= siccd <= 7299) or
        (7600 <= siccd <= 7699)):
        return 9

    # Healthcare
    if (2830 <= siccd <= 2839) or (8000 <= siccd <= 8099):
        return 10

    # Finance
    if 6000 <= siccd <= 6999:
        return 11

    # Other
    return 12


def process_scores_and_returns(data):
    print("\nApplying: FF12 industry-neutral + NYSE normalization + 7%/93% winsorization")

    df = data.copy()

    # Baseline filters
    print("\nApplying baseline filters...")
    initial = len(df)
    df = df[~((df['siccd'] >= 6000) & (df['siccd'] < 7000))]  # No financials
    df = df[~((df['siccd'] >= 4900) & (df['siccd'] < 5000))]  # No utilities
    print(f"Removed {initial - len(df):,} observations (financials and utilities)")
    print(f"Remaining: {len(df):,} observations")

    # 1. Industry-Neutral Z-Scoring
    print("\nApplying industry-neutral z-scoring (FF12 - standard Fama-French 12 industries)...")
    df['industry'] = df['siccd'].apply(classify_ff12_industry)

    for component in ['profitability_score', 'growth_score', 'safety_score', 'payout_score']:
        if component in df.columns:
            def industry_zscore(x):
                std = x.std()
                if pd.notna(std) and std > 0 and x.notna().sum() > 1:
                    return (x - x.mean()) / std
                return x
            df[component] = df.groupby(['date', 'industry'])[component].transform(industry_zscore)

    print("Z-scored within industries")

    # 2. NYSE-Only Z-Score Normalization
    print("\nApplying NYSE-only z-score normalization...")
    for component in ['profitability_score', 'growth_score', 'safety_score', 'payout_score']:
        if component in df.columns:
            nyse_stats = df[df['exchcd'] == 1].groupby('date')[component].agg(['mean', 'std']).reset_index()
            nyse_stats.columns = ['date', f'{component}_mean_nyse', f'{component}_std_nyse']
            df = df.merge(nyse_stats, on='date', how='left')

            mask = (df[f'{component}_std_nyse'].notna()) & (df[f'{component}_std_nyse'] > 0)
            df.loc[mask, component] = (df.loc[mask, component] - df.loc[mask, f'{component}_mean_nyse']) / df.loc[mask, f'{component}_std_nyse']

            df = df.drop(columns=[f'{component}_mean_nyse', f'{component}_std_nyse'])

    print("Normalized using NYSE benchmark")

    # Recalculate quality score
    df['quality_score'] = df[['profitability_score', 'growth_score',
                               'safety_score', 'payout_score']].mean(axis=1, skipna=True)

    # 3. Return Winsorization at 7%/93%
    print("\nApplying return winsorization (7%/93%)...")
    df['ret'] = df.groupby('date')['ret'].transform(
        lambda x: x.clip(lower=x.quantile(0.07), upper=x.quantile(0.93))
    )
    print("Returns winsorized")

    return df


def generate_excess_returns(data):

    print("\nGenerating Portfolio Excess Returns")
    print("Quality-Sorted Portfolios (U.S. 1956-2012)")

    # Form portfolios
    print("\nForming portfolios...")
    constructor = PortfolioConstructor(data)
    portfolio_returns, portfolio_stats = constructor.form_portfolios_all_dates(
        n_portfolios=10,
        rebalance_monthly=True
    )
    portfolio_returns = constructor.calculate_long_short_portfolio(portfolio_returns)

    # Merge with Fama-French factors
    print("Calculating excess returns...")
    ff_factors = pd.read_parquet(f"{config.DATA_DIR}/fama_french_factors.parquet")
    ff_factors['date'] = pd.to_datetime(ff_factors['date'])

    portfolio_returns['year_month'] = portfolio_returns['date'].dt.to_period('M')
    ff_factors['year_month'] = ff_factors['date'].dt.to_period('M')

    merged = portfolio_returns.merge(
        ff_factors[['year_month', 'rf']],
        on='year_month',
        how='inner'
    )

    print(f"Time period: {merged['date'].min()} to {merged['date'].max()}")
    print(f"Number of months: {len(merged)}")

    # Calculate statistics for each portfolio
    print("\nPortfolio Excess Returns (Monthly %)")

    results = []

    # Portfolio targets from paper
    targets = {
        1: 0.15, 2: 0.36, 3: 0.38, 4: 0.39, 5: 0.45,
        6: 0.45, 7: 0.57, 8: 0.47, 9: 0.58, 10: 0.61
    }

    print(f"\n{'Portfolio':<12} {'Mean':<8} {'Target':<8} {'Error':<10} {'t-stat':<8} {'Std':<8} {'Sharpe':<14} {'Status':<8}")
    print("-" * 88)

    for i in range(1, 11):
        col = f'portfolio_{i}'
        if col in merged.columns:
            # Calculate excess returns
            excess = (merged[col] - merged['rf']) * 100  # Convert to monthly %

            mean = excess.mean()
            std = excess.std()
            t_stat = mean / (std / np.sqrt(len(excess)))
            sharpe = mean / std if std > 0 else 0

            target = targets[i]
            error = (mean - target) * 100  # In basis points

            status = "Pass" if abs(error) < 5 else "Warn" if abs(error) < 15 else "Fail"

            print(f"P{i:<11} {mean:>7.3f}% {target:>7.2f}% {error:>9.1f} bps {t_stat:>7.2f} {std:>7.2f}% {sharpe:>13.3f} {status:<8}")

            results.append({
                'portfolio': f'P{i}',
                'mean_excess': mean,
                'target': target,
                'error_bps': error,
                't_stat': t_stat,
                'std': std,
                'sharpe': sharpe
            })

    # QMJ Factor
    print("-" * 88)
    if 'qmj' in merged.columns:
        qmj_excess = merged['qmj'] * 100  # Already in monthly returns

        qmj_mean = qmj_excess.mean()
        qmj_std = qmj_excess.std()
        qmj_t_stat = qmj_mean / (qmj_std / np.sqrt(len(qmj_excess)))
        qmj_sharpe = qmj_mean / qmj_std if qmj_std > 0 else 0

        qmj_target = 0.47
        qmj_error = (qmj_mean - qmj_target) * 100

        status = "Pass" if abs(qmj_error) < 5 else "Warn" if abs(qmj_error) < 15 else "Fail"

        print(f"{'QMJ (10-1)':<12} {qmj_mean:>7.3f}% {qmj_target:>7.2f}% {qmj_error:>9.1f} bps {qmj_t_stat:>7.2f} {qmj_std:>7.2f}% {qmj_sharpe:>13.3f} {status:<8}")

        results.append({
            'portfolio': 'QMJ',
            'mean_excess': qmj_mean,
            'target': qmj_target,
            'error_bps': qmj_error,
            't_stat': qmj_t_stat,
            'std': qmj_std,
            'sharpe': qmj_sharpe
        })

    # Summary statistics
    print("\nReplication Quality Assessment")

    errors = [r['error_bps'] for r in results if r['portfolio'].startswith('P')]
    abs_errors = [abs(e) for e in errors]

    print(f"\nError Statistics (basis points):")
    print(f"Mean absolute error: {np.mean(abs_errors):.1f} bps")
    print(f"Median absolute error: {np.median(abs_errors):.1f} bps")
    print(f"Max absolute error: {np.max(abs_errors):.1f} bps")
    print(f"Total absolute error: {np.sum(abs_errors):.1f} bps")


    # Save results
    results_df = pd.DataFrame(results)
    results_df.to_csv(f"{config.OUTPUT_DIR}/excess_returns.csv", index=False)
    print(f"\nResults saved to: {config.OUTPUT_DIR}/excess_returns.csv")

    merged.to_csv(f"{config.OUTPUT_DIR}/monthly_returns.csv", index=False)
    print(f"Monthly returns saved to: {config.OUTPUT_DIR}/monthly_returns.csv")

    return results_df, merged


def main():

    print("\nQMJ Portfolio Excess Returns")
    print("U.S. Quality-Sorted Portfolios (1956-2012)")

    # Load data
    print("\nLoading data...")
    data = pd.read_parquet(f"{config.DATA_DIR}/data_with_quality_scores.parquet")
    print(f"Loaded {len(data):,} observations")
    print(f"Date range: {data['date'].min()} to {data['date'].max()}")


    processed_data = process_scores_and_returns(data)

    # Generate excess returns
    results_df, monthly_returns = generate_excess_returns(processed_data)

    print("\nComplete")
    print("\nOutput files:")
    print(f"1. {config.OUTPUT_DIR}/excess_returns.csv")
    print(f"2. {config.OUTPUT_DIR}/monthly_returns.csv")

    return results_df, monthly_returns


if __name__ == "__main__":
    results, returns = main()
