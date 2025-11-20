# README: Construction of the Livestock Layers
This repository contains scripts for processing AgCensus data, filling statistical gaps, and assigning farm populations to geographic cells (GLW).

## Project Overview
The core process involves three main stages:
1.  **Data Cleaning (`gaps`):** Fill in missing values and rectify inconsistencies in the AgCensus data using optimization methods (ILP and IPF).
2.  **Assignment (via `instances`):** Generate and run jobs that assign livestock populations from farms to GLW cells within each county using Integer Linear Programming (ILP).
3.  **Collection and Cleanup (`collect`, `upres`, `clean`):** Aggregate results and manage output files.

***

## Main Functions and Descriptions

The primary entry point is the `master` shell script, which exposes the following functions:

| Function Name | Description | Python Script/Core Logic |
| :--- | :--- | :--- |
| **`gaps`** | **Fills gaps** in AgCensus county totals, state-by-farmsize, and county-by-farmsize data. It uses **Integer Linear Programming (ILP)** to minimize deviation from bounds and **Iterative Proportional Fitting (IPF)** to ensure county-by-farmsize distributions match state and county totals. | `../scripts/fill_gaps.py` |
| **`instances`** | **Generates livestock-county instances** and creates a job execution script (`run.sh`) to process each instance sequentially or in parallel. This is the **setup step** for the main assignment process. | `../scripts/generate_instances.py` |
| **`collect`** | **Aggregates all results** from successfully completed individual job files (`farms_to_cells_*.csv.zip` and `stats_*.csv`) into consolidated output ZIP files. | `../scripts/collect_results.py` |
| **`upres`** | **Moves final output files** (assignments, statistics, and the filled AgCensus data) to the designated `../results/` folder for archival. | Shell utility (mv) |
| **`status`** | **Checks the progress** of the assignment jobs by reading log files (`log_*`). Reports the number of successful and incomplete assignments. | Shell utility (grep/wc/tail) |
| **`clean`** | **Removes all temporary files** and logs generated during the process, including `log_*`, `farms_to_cells*`, and `stats_*` files. | Shell utility (rm) |
| **`egf2c`** | **Runs example farm-to-cell assignments** to demonstrate the functionality of `farms_to_cells.py`. | `../scripts/farms_to_cells.py` |
| **`tests`** | **Runs specific test cases** for the farm-to-cell assignment to check known corner cases and data issues. | `../scripts/farms_to_cells.py` |

***

## Usage

### Prerequisites

* The environment must be set up to run the Python scripts, typically within a **Gurobi environment** for the optimization tasks.

### Running a Function

To execute any of the main functions, call the `master` script followed by the function name:

```bash
./master [function_name]