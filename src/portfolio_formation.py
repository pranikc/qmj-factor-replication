"""
Portfolio Formation (Fama French)
Forms quality-sorted portfolios using NYSE breakpoints and calculates returns.
"""

import pandas as pd
import numpy as np
from typing import Tuple, Dict
import config
import utils


class PortfolioConstructor:

    def __init__(self, data: pd.DataFrame):

        self.data = data.copy()
        self.data['date'] = pd.to_datetime(self.data['date'])

    def calculate_nyse_breakpoints(
        self,
        date: pd.Timestamp,
        n_portfolios: int = 10
    ) -> np.ndarray:
        """
        Calculate quality score breakpoints using NYSE stocks only.

        Inputs:
            date: Date for breakpoint calculation
            n_portfolios: Number of portfolios (10 for deciles)

        Output:
            Array of breakpoints
        """
        # Get NYSE stocks for this date
        nyse_stocks = self.data[
            (self.data['date'] == date) &
            (self.data['exchcd'] == 1) &  # NYSE only
            (self.data['quality_score'].notna()) &
            (self.data['mkt_cap'] > 0)
        ]

        if len(nyse_stocks) < n_portfolios:
            return None

        # Calculate percentile breakpoints
        percentiles = np.linspace(0, 100, n_portfolios + 1)[1:-1]
        breakpoints = np.percentile(nyse_stocks['quality_score'], percentiles)

        return breakpoints

    def assign_portfolios(
        self,
        date: pd.Timestamp,
        breakpoints: np.ndarray,
        n_portfolios: int = 10
    ) -> pd.DataFrame:
        """
        Assign all stocks to quality-sorted portfolios.

        Inputs:
            date: Date for portfolio assignment
            breakpoints: Quality score breakpoints (from NYSE)
            n_portfolios: Number of portfolios

        Output:
            DataFrame with portfolio assignments
        """

        # We only need quality_score and mkt_cap at formation date
        # We also do NOT filter by ret here as that's only needed at return calculation date
        stocks = self.data[
            (self.data['date'] == date) &
            (self.data['quality_score'].notna()) &
            (self.data['mkt_cap'] > 0)
        ].copy()

        if len(stocks) == 0:
            return pd.DataFrame()

        # Remove duplicate breakpoints manually to handle edge case where many stocks have same quality
        unique_breakpoints = np.unique(breakpoints)

        # Create bins with -inf and +inf
        bins = np.concatenate([[-np.inf], unique_breakpoints, [np.inf]])

        # Number of actual bins after removing duplicates
        n_bins = len(bins) - 1

        # Create labels for actual number of bins
        labels = list(range(1, n_bins + 1))

        # Assign to portfolios using breakpoints
        stocks['portfolio'] = pd.cut(
            stocks['quality_score'],
            bins=bins,
            labels=labels,
            include_lowest=True
        )

        return stocks[['permno', 'portfolio', 'quality_score', 'mkt_cap']]

    def calculate_portfolio_returns(
        self,
        portfolio_assignments: pd.DataFrame,
        returns_date: pd.Timestamp
    ) -> Dict[int, float]:
        """
        Calculate value-weighted returns for each portfolio.

        Inputs:
            portfolio_assignments: DataFrame with portfolio assignments
            returns_date: Date for which to calculate returns

        Output:
            Dictionary mapping portfolio number to return
        """
        # Get returns for next period
        returns = self.data[
            (self.data['date'] == returns_date) &
            (self.data['ret'].notna())
        ][['permno', 'ret']].copy()

        # Merge with portfolio assignments
        merged = portfolio_assignments.merge(returns, on='permno', how='inner')

        if len(merged) == 0:
            return {}

        # Calculate value-weighted returns for each portfolio
        portfolio_returns = {}

        for portfolio in merged['portfolio'].unique():
            portfolio_data = merged[merged['portfolio'] == portfolio]

            # Value-weighted return
            total_mcap = portfolio_data['mkt_cap'].sum()
            if total_mcap > 0:
                weights = portfolio_data['mkt_cap'] / total_mcap
                vw_return = (portfolio_data['ret'] * weights).sum()
                portfolio_returns[int(portfolio)] = vw_return

        return portfolio_returns

    def form_portfolios_all_dates(
        self,
        n_portfolios: int = 10,
        rebalance_monthly: bool = True
    ) -> pd.DataFrame:
        """
        Form portfolios for all dates and calculate returns.

        Inputs:
            n_portfolios: Number of portfolios
            rebalance_monthly: Whether to rebalance monthly (True for QMJ)

        Output:
            Dataframe with portfolio returns time series
        """
        print("\nCompleted Portfolio Formation")
        print(f"Forming {n_portfolios} quality-sorted portfolios...")
        print(f"Rebalancing: {'Monthly' if rebalance_monthly else 'Annually'}")

        # Get unique dates
        dates = sorted(self.data['date'].unique())
        print(f"Time period: {dates[0]} to {dates[-1]}")
        print(f"Number of months: {len(dates)}")

        # Store portfolio returns
        portfolio_returns_list = []
        portfolio_stats_list = []

        for i, date in enumerate(dates[:-1]):  # Exclude last date (no forward return)
            if i % 120 == 0: # every 10 years...
                print(f"  Processing: {date} ({i+1}/{len(dates)-1})")

            # Calculate NYSE breakpoints
            breakpoints = self.calculate_nyse_breakpoints(date, n_portfolios)

            if breakpoints is None:
                continue

            # Assign portfolios
            assignments = self.assign_portfolios(date, breakpoints, n_portfolios)

            if len(assignments) == 0:
                continue

            # Get next date for returns
            next_date = dates[i + 1]

            # Calculate returns
            returns = self.calculate_portfolio_returns(assignments, next_date)

            if len(returns) > 0:
                # Store returns
                return_row = {'date': next_date}
                return_row.update({f'portfolio_{p}': returns.get(p, np.nan)
                                  for p in range(1, n_portfolios + 1)})
                portfolio_returns_list.append(return_row)

                # Store portfolio statistics
                for portfolio in range(1, n_portfolios + 1):
                    portfolio_data = assignments[assignments['portfolio'] == portfolio]
                    if len(portfolio_data) > 0:
                        portfolio_stats_list.append({
                            'date': date,
                            'portfolio': portfolio,
                            'n_stocks': len(portfolio_data),
                            'avg_quality': portfolio_data['quality_score'].mean(),
                            'median_quality': portfolio_data['quality_score'].median(),
                            'total_mkt_cap': portfolio_data['mkt_cap'].sum()
                        })

        # Convert to dfs
        portfolio_returns = pd.DataFrame(portfolio_returns_list)
        portfolio_stats = pd.DataFrame(portfolio_stats_list)

        print("\nPortfolio Formation Complete")
        print(f"Number of months with returns: {len(portfolio_returns)}")
        print(f"\nAverage number of stocks per portfolio:")
        avg_stocks = portfolio_stats.groupby('portfolio')['n_stocks'].mean()
        for p, n in avg_stocks.items():
            print(f"  Portfolio {p}: {n:.0f} stocks")

        # Check monotonicity of quality scores
        print(f"\nAverage quality score by portfolio:")
        avg_quality = portfolio_stats.groupby('portfolio')['avg_quality'].mean()
        for p, q in avg_quality.items():
            print(f"  Portfolio {p}: {q:.3f}")

        return portfolio_returns, portfolio_stats

    def calculate_long_short_portfolio(
        self,
        portfolio_returns: pd.DataFrame
    ) -> pd.DataFrame:
        """
        Calculate the QMJ factor (High - Low portfolio).

        Inputs:
            portfolio_returns: DataFrame with portfolio returns

        Output:
            Dataframe with QMJ factor returns
        """

        # QMJ = High quality (P10) - Low quality (P1)
        portfolio_returns['qmj'] = (
            portfolio_returns['portfolio_10'] - portfolio_returns['portfolio_1']
        )

        print("\nQMJ Factor (High - Low) Statistics:")
        qmj_stats = utils.calculate_summary_statistics(
            portfolio_returns[['qmj']],
            annualize=True
        )
        print(qmj_stats)

        return portfolio_returns


def main():

    # Load data with quality scores
    print("Loading data with quality scores...")
    data = utils.load_from_parquet(
        f"{config.DATA_DIR}/data_with_quality_scores.parquet",
        "Data with quality scores"
    )

    # Initialize constructor
    constructor = PortfolioConstructor(data)

    # Form portfolios
    portfolio_returns, portfolio_stats = constructor.form_portfolios_all_dates(
        n_portfolios=config.N_PORTFOLIOS,
        rebalance_monthly=True
    )

    # Calculate QMJ factor
    portfolio_returns = constructor.calculate_long_short_portfolio(portfolio_returns)

    # Save results
    utils.save_to_parquet(
        portfolio_returns,
        f"{config.OUTPUT_DIR}/portfolio_returns.parquet",
        "Portfolio returns"
    )

    utils.save_to_parquet(
        portfolio_stats,
        f"{config.OUTPUT_DIR}/portfolio_stats.parquet",
        "Portfolio statistics"
    )

    # Calculate and display summary statistics
    print("\nPortfolio Return Summary Statistics")

    portfolio_cols = [f'portfolio_{i}' for i in range(1, config.N_PORTFOLIOS + 1)]
    summary_stats = utils.calculate_summary_statistics(
        portfolio_returns[portfolio_cols],
        annualize=True
    )
    print(summary_stats)

    # Save to CSV
    summary_stats.to_csv(f"{config.OUTPUT_DIR}/portfolio_summary_stats.csv")
    print(f"\nSaved summary statistics to {config.OUTPUT_DIR}/portfolio_summary_stats.csv")


if __name__ == "__main__":
    main()
