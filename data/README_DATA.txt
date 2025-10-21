This directory contains data files after running the extraction script.

Data files are NOT included in this package.

Download data from WRDS:
    python src/data_extraction.py

Expected files after extraction:
--------------------------------
1. crsp_monthly.parquet
   - CRSP Monthly Stock File
   - Filters: SHRCD 10/11, EXCHCD 1/2/3
   - Period: 1950-2012

2. compustat_annual.parquet
   - Compustat Fundamentals Annual
   - Period: 1950-2012

3. ccm_links.parquet
   - CRSP-Compustat Link Table
   - Link criteria: LC/LU, P/C

4. crsp_compustat_merged.parquet
   - Merged CRSP and Compustat
   - 4-month accounting lag applied

5. data_with_quality_scores.parquet
   - Full dataset with quality scores
   - Created by quality_scores.py
   - Used by generate_excess_returns.py
