# Step 2 Handoff — Benchmark Dataset Reference

This directory points to the finalized and frozen benchmark dataset files transferred from Step 1.2 for Step 2 modeling.

## Required Benchmark Files:
1. `ausgrid_solar_attacked.parquet`
   - Size: 173,015,190 bytes (165.00 MB)
   - SHA-256: `176fa03152359472b544f2197427bca92f51127e4c2becad84e31ec72f6ca1b4`
2. `ausgrid_solar_attacked.csv`
   - Size: 1,705,889,911 bytes (1,626.86 MB)
   - SHA-256: `819ce00d29b5de917bdf2ff86e76da8befa092f59ca7c15ca32b233ad2747682`

Both representations contain 15,729,792 observations across 299 customers and 19 columns.

See `../HANDOFF_README.md` for full implementation guidelines for Step 2 (Local AI Defense, sliding window construction, and 1D-CNN autoencoder design).
