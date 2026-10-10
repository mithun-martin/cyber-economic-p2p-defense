# Raw Data Directory

## Dataset Source
This project uses the **Ausgrid Solar Home Electricity Dataset**, which monitors 300 solar-equipped households in New South Wales, Australia at 30-minute intervals from July 1, 2010 through June 30, 2013 (3 calendar years, 1,096 days).

### Required Input Files:
Place the three yearly Ausgrid CSV files in this directory:
- `Solar home 2010-2011.csv` (~61 MB)
- `Solar home 2011-2012.csv` (~62 MB)
- `Solar home 2012-2013.csv` (~61 MB)

### Consumption Categories:
- **GC**: General Consumption (household electricity usage in kWh)
- **CL**: Controlled Load (off-peak hot water / space heating in kWh)
- **GG**: Gross Generation (solar PV output in kWh)

### Cohort Preprocessing Rule:
Customer 2 is excluded during data preprocessing because it is missing 81 continuous days (2012-10-12 through 2012-12-31) in both GC and GG. The remaining **299 customers** have complete, contiguous records across all 1,096 days.
