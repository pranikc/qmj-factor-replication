"""
Extracts CRSP and Compustat data from WRDS and merges using CCM link table.
"""

import pandas as pd
import numpy as np
import wrds
from typing import Optional
import config
import utils


class WRDSDataExtractor:

    def __init__(self, username: str, password: str):
        self.username = username
        self.password = password
        self.db = None

    def connect(self) -> None:
        print("Connecting to WRDS...")
        self.db = wrds.Connection(wrds_username=self.username)
        print("Connected to WRDS")

    def disconnect(self) -> None:
        if self.db:
            self.db.close()
            print("Disconnected from WRDS")

    def extract_crsp_monthly(
        self,
        start_date: str,
        end_date: str,
        share_codes: list,
        exchange_codes: list
    ) -> pd.DataFrame:
        """
        Extract CRSP monthly stock file data.

        Inputs:
            start_date: Start date
            end_date: End date
            share_codes: Valid share codes (typically [10, 11])
            exchange_codes: Valid exchange codes (1=NYSE, 2=AMEX, 3=NASDAQ)

        Output:
            Dataframe with CRSP monthly data
        """
        print(f"\nExtracting CRSP monthly data from {start_date} to {end_date}...")

        # Query CRSP monthly stock file
        query = f"""
        SELECT
            a.permno,
            a.permco,
            a.date,
            a.ret,
            a.retx,
            a.vol,
            a.shrout,
            a.prc,
            a.cfacpr,
            a.cfacshr,
            b.shrcd,
            b.exchcd,
            b.siccd,
            b.ticker,
            b.ncusip,
            b.comnam
        FROM
            crsp.msf AS a
        LEFT JOIN
            crsp.msenames AS b
        ON
            a.permno = b.permno
            AND b.namedt <= a.date
            AND a.date <= b.nameendt
        WHERE
            a.date BETWEEN '{start_date}' AND '{end_date}'
            AND b.shrcd IN ({','.join(map(str, share_codes))})
            AND b.exchcd IN ({','.join(map(str, exchange_codes))})
        ORDER BY
            a.permno, a.date
        """

        crsp = self.db.raw_sql(query)

        # Calculate market cap (in millions)
        crsp['mkt_cap'] = crsp['shrout'] * crsp['prc'].abs() / 1000

        print(f"Extracted {len(crsp):,} CRSP observations")
        print(f"  Unique stocks: {crsp['permno'].nunique():,}")
        print(f"  Date range: {crsp['date'].min()} to {crsp['date'].max()}")

        return crsp

    def extract_crsp_delisting(
        self,
        start_date: str,
        end_date: str
    ) -> pd.DataFrame:
        """
        Extract CRSP delisting information.

        Inputs:
            start_date: Start date
            end_date: End date

        Output:
            Dataframe with delisting data
        """
        print(f"\nExtracting CRSP delisting data...")

        query = f"""
        SELECT
            permno,
            dlstdt AS date,
            dlret,
            dlstcd
        FROM
            crsp.msedelist
        WHERE
            dlstdt BETWEEN '{start_date}' AND '{end_date}'
        """

        delist = self.db.raw_sql(query)

        print(f"Extracted {len(delist):,} delisting records")

        return delist

    def extract_compustat_annual(
        self,
        start_date: str,
        end_date: str
    ) -> pd.DataFrame:
        """
        Extract Compustat annual fundamentals data.

        Inputs:
            start_date: Start date
            end_date: End date

        Returns:
            Dataframe with Compustat fundamentals
        """
        print(f"\nExtracting Compustat annual fundamentals...")

        # Query Compustat annual file
        # Variables needed for quality score calculation
        query = f"""
        SELECT
            gvkey,
            datadate,
            fyear,
            fyr,
            indfmt,
            datafmt,
            popsrc,
            consol,
            -- Assets and income
            at,          -- Total Assets
            ib,          -- Income Before Extraordinary Items
            revt,        -- Revenue/Sales
            cogs,        -- Cost of Goods Sold
            sale,        -- Sales (alternative to revt)
            -- Balance sheet items
            seq,         -- Stockholders' Equity
            ceq,         -- Common Equity
            pstk,        -- Preferred Stock
            txditc,      -- Deferred Taxes and Investment Tax Credit
            re,          -- Retained Earnings
            act,         -- Current Assets
            lct,         -- Current Liabilities
            lt,          -- Total Liabilities
            -- Cash flow
            dp,          -- Depreciation and Amortization
            oancf,       -- Operating Activities Cash Flow
            -- Debt
            dlc,         -- Debt in Current Liabilities
            dltt,        -- Long-Term Debt
            mibt,        -- Minority Interest - Balance Sheet
            -- Payout measures
            dvc,         -- Dividends Common
            prstkc,      -- Purchase of Common Stock
            -- Shares and price
            csho,        -- Common Shares Outstanding
            prcc_f       -- Price Close - Fiscal Year
        FROM
            comp.funda
        WHERE
            datadate BETWEEN '{start_date}' AND '{end_date}'
            AND indfmt = 'INDL'      -- Industrial format
            AND datafmt = 'STD'      -- Standardized format
            AND popsrc = 'D'         -- Domestic (US)
            AND consol = 'C'         -- Consolidated
        ORDER BY
            gvkey, datadate
        """

        compustat = self.db.raw_sql(query)

        # Ensure date column is datetime type
        compustat['datadate'] = pd.to_datetime(compustat['datadate'])

        print(f"Extracted {len(compustat):,} Compustat observations")
        print(f"  Unique firms: {compustat['gvkey'].nunique():,}")
        print(f"  Date range: {compustat['datadate'].min()} to {compustat['datadate'].max()}")

        return compustat

    def extract_ccm_link(self) -> pd.DataFrame:
        """
        Extract CRSP-Compustat Merged (CCM) link table.

        Output:
            Dataframe with CCM links
        """
        print(f"\nExtracting CCM link table...")

        query = """
        SELECT
            gvkey,
            lpermno AS permno,
            lpermco AS permco,
            linktype,
            linkprim,
            linkdt,
            linkenddt
        FROM
            crsp.ccmxpf_linktable
        WHERE
            linktype IN ('LC', 'LU')
            AND linkprim IN ('P', 'C')
        """

        ccm_link = self.db.raw_sql(query)

        # Ensure date columns are datetime type
        ccm_link['linkdt'] = pd.to_datetime(ccm_link['linkdt'])
        ccm_link['linkenddt'] = pd.to_datetime(ccm_link['linkenddt'])

        # Handle missing LINKENDDT (means current link)
        ccm_link['linkenddt'] = ccm_link['linkenddt'].fillna(pd.Timestamp('2099-12-31'))

        print(f"Extracted {len(ccm_link):,} CCM links")
        print(f"  Unique CRSP PERMNOs: {ccm_link['permno'].nunique():,}")
        print(f"  Unique Compustat GVKEYs: {ccm_link['gvkey'].nunique():,}")

        return ccm_link

    def merge_crsp_delisting(
        self,
        crsp: pd.DataFrame,
        delist: pd.DataFrame
    ) -> pd.DataFrame:
        """
        Merge CRSP returns with delisting returns and apply Shumway adjustment.

        Inputs:
            crsp: CRSP monthly data
            delist: Delisting data

        Output:
            CRSP data with adjusted returns
        """
        print("\nMerging delisting returns and applying Shumway (1997) adjustment...")

        # Merge delisting data
        crsp_merged = crsp.merge(
            delist[['permno', 'date', 'dlret', 'dlstcd']],
            on=['permno', 'date'],
            how='left'
        )

        # Apply delisting adjustment
        def apply_adjustment(row):
            if pd.isna(row['dlret']) and pd.notna(row['dlstcd']):
                # Check if performance-related delisting
                if row['dlstcd'] in config.PERFORMANCE_DELISTING_CODES:
                    # Paper specifies -30% for ALL US stocks (not differentiated by exchange)
                    default_dlret = -0.30
                    row['dlret'] = default_dlret
                    row['dlret_imputed'] = True

            # Compound returns if delisting return exists
            if pd.notna(row['dlret']) and pd.notna(row['ret']):
                row['ret_adjusted'] = (1 + row['ret']) * (1 + row['dlret']) - 1
            else:
                row['ret_adjusted'] = row['ret']

            return row

        # Mark imputed delisting returns
        crsp_merged['dlret_imputed'] = False
        crsp_merged = crsp_merged.apply(apply_adjustment, axis=1)

        n_imputed = crsp_merged['dlret_imputed'].sum()
        print(f"Imputed {n_imputed:,} delisting returns using Shumway adjustment")

        # Use adjusted returns going forward
        crsp_merged['ret_original'] = crsp_merged['ret']
        crsp_merged['ret'] = crsp_merged['ret_adjusted']

        return crsp_merged

    def merge_crsp_compustat(
        self,
        crsp: pd.DataFrame,
        compustat: pd.DataFrame,
        ccm_link: pd.DataFrame,
        lag_months: int = 4
    ) -> pd.DataFrame:
        """
        Merge CRSP and Compustat using CCM link table with point-in-time alignment.

        Inputs:
            crsp: CRSP monthly data
            compustat: Compustat annual data
            ccm_link: CCM link table
            lag_months: Lag in months for accounting data availability

        Output:
            Merged CRSP-Compustat data
        """
        print("\nMerging CRSP and Compustat with point-in-time alignment...")

        # Add accounting data availability date
        compustat['data_available_date'] = compustat['datadate'] + pd.DateOffset(months=lag_months)

        # Merge Compustat with CCM link
        compustat_linked = compustat.merge(
            ccm_link,
            on='gvkey',
            how='inner'
        )

        print(f"After CCM link: {len(compustat_linked):,} observations")

        crsp['date'] = pd.to_datetime(crsp['date'])
        compustat_linked['data_available_date'] = pd.to_datetime(compustat_linked['data_available_date'])
        compustat_linked['linkdt'] = pd.to_datetime(compustat_linked['linkdt'])
        compustat_linked['linkenddt'] = pd.to_datetime(compustat_linked['linkenddt'])

        # Merge CRSP with Compustat
        merged = crsp.merge(
            compustat_linked,
            on='permno',
            how='left',
            suffixes=('', '_comp')
        )

        # Filter for valid links and point-in-time data
        valid_mask = (
            (merged['date'] >= merged['linkdt']) &
            (merged['date'] <= merged['linkenddt']) &
            (merged['date'] >= merged['data_available_date'])
        )

        merged = merged[valid_mask].copy()

        # For each CRSP date, keep most recent Compustat data
        merged = merged.sort_values(['permno', 'date', 'datadate'])
        merged = merged.groupby(['permno', 'date']).tail(1)

        print(f"Merged CRSP-Compustat: {len(merged):,} observations")
        print(f"  Unique stocks: {merged['permno'].nunique():,}")
        print(f"  Coverage: {merged['date'].min()} to {merged['date'].max()}")

        # Check merge quality
        pct_with_fundamentals = (merged['gvkey'].notna().sum() / len(merged)) * 100
        print(f"  Percentage with fundamentals: {pct_with_fundamentals:.1f}%")

        return merged


def download_fama_french_factors(
    start_date: str = "1956-06-01",
    end_date: str = "2012-12-31",
    output_path: Optional[str] = None
) -> pd.DataFrame:
    """
    Download Fama-French research factors from Ken French's data library.

    Inputs:
        start_date: Start date
        end_date: End date
        output_path: Path to save parquet file

    Output:
        Dataframe with columns: date, mkt_rf, smb, hml, rf
    """
    import io
    import zipfile
    import requests

    print(f"\nDownloading Fama-French factors from {start_date} to {end_date}...")

    # Download the ZIP file
    url = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/F-F_Research_Data_Factors_CSV.zip"
    response = requests.get(url)
    response.raise_for_status()

    # Extract CSV from ZIP
    with zipfile.ZipFile(io.BytesIO(response.content)) as z:
        csv_filename = z.namelist()[0]
        with z.open(csv_filename) as f:
            content = f.read().decode('utf-8')

    # Parse the CSV content
    # The file has header lines, then data, then annual data section
    lines = content.split('\n')

    # Find where the monthly data starts (after header)
    data_start = 0
    for i, line in enumerate(lines):
        if line.strip() and line.strip()[0].isdigit():
            data_start = i
            break

    # Find where annual data starts (blank line or "Annual" marker)
    data_end = len(lines)
    for i in range(data_start, len(lines)):
        if not lines[i].strip() or 'Annual' in lines[i]:
            data_end = i
            break

    # Read the monthly data section
    monthly_data = '\n'.join(lines[data_start:data_end])
    df = pd.read_csv(io.StringIO(monthly_data), names=['date', 'mkt_rf', 'smb', 'hml', 'rf'])

    # Convert date from YYYYMM to datetime
    df['date'] = pd.to_datetime(df['date'].astype(str), format='%Y%m')

    # Convert from percentage to decimal
    for col in ['mkt_rf', 'smb', 'hml', 'rf']:
        df[col] = pd.to_numeric(df[col], errors='coerce') / 100.0

    # Filter to desired date range
    df = df[(df['date'] >= start_date) & (df['date'] <= end_date)]

    print(f"Downloaded {len(df)} months of factor data")
    print(f"Date range: {df['date'].min()} to {df['date'].max()}")

    # Save if output path specified
    if output_path:
        df.to_parquet(output_path, index=False)
        print(f"Saved to: {output_path}")

    return df


def main():

    # Create directories
    utils.create_directories([
        config.DATA_DIR,
        config.INTERMEDIATE_DIR,
        config.CACHE_DIR,
        config.OUTPUT_DIR
    ])

    # Initialize extractor
    extractor = WRDSDataExtractor(
        username=config.WRDS_USERNAME,
        password=config.WRDS_PASSWORD
    )

    try:
        extractor.connect()

        # Extract CRSP monthly data
        crsp = extractor.extract_crsp_monthly(
            start_date=config.START_DATE,
            end_date=config.END_DATE,
            share_codes=config.VALID_SHARE_CODES,
            exchange_codes=config.VALID_EXCHANGE_CODES
        )

        # Save intermediate result
        utils.save_to_parquet(
            crsp,
            f"{config.INTERMEDIATE_DIR}/crsp_monthly.parquet",
            "CRSP monthly data"
        )

        # Extract delisting data
        delist = extractor.extract_crsp_delisting(
            start_date=config.START_DATE,
            end_date=config.END_DATE
        )

        # Merge and adjust for delisting
        crsp = extractor.merge_crsp_delisting(crsp, delist)

        # Save adjusted CRSP
        utils.save_to_parquet(
            crsp,
            f"{config.INTERMEDIATE_DIR}/crsp_monthly_adjusted.parquet",
            "CRSP monthly with delisting adjustment"
        )

        # Extract Compustat
        compustat = extractor.extract_compustat_annual(
            start_date=config.START_DATE,
            end_date=config.END_DATE
        )

        # Save intermediate result
        utils.save_to_parquet(
            compustat,
            f"{config.INTERMEDIATE_DIR}/compustat_annual.parquet",
            "Compustat annual fundamentals"
        )

        # Extract CCM link table
        ccm_link = extractor.extract_ccm_link()

        # Save link table
        utils.save_to_parquet(
            ccm_link,
            f"{config.INTERMEDIATE_DIR}/ccm_link.parquet",
            "CCM link table"
        )

        # Merge CRSP and Compustat
        merged = extractor.merge_crsp_compustat(
            crsp=crsp,
            compustat=compustat,
            ccm_link=ccm_link,
            lag_months=config.ACCOUNTING_LAG_MONTHS
        )

        # Save final merged dataset
        utils.save_to_parquet(
            merged,
            f"{config.DATA_DIR}/crsp_compustat_merged.parquet",
            "Final merged CRSP-Compustat data"
        )

        print("\nCompleted Data Extraction and Merging")

        # Validate coverage
        utils.validate_data_coverage(
            merged,
            'date',
            config.START_DATE,
            config.END_DATE
        )

    finally:
        extractor.disconnect()


if __name__ == "__main__":
    main()
