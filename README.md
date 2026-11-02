# Retail POS Queue Simulation

Discrete-event simulation of a hybrid supermarket checkout zone: staffed checkouts, self-checkouts (SCO) and an SCO assistant. The model is calibrated on real point-of-sale data and built with Python and SimPy.

This repository contains the code for my master's thesis *"Analysis of throughput and reliability of transaction processes in self-checkout systems"* (Computer Science, Lublin University of Technology).

## Research question

During peak hours, a store manager usually has one extra employee. Should that person become a second SCO assistant, or open another staffed checkout? The simulation compares five layouts of the checkout zone:

| Variant | Staffed | SCO | Assistants |
|---|---|---|---|
| W0 (baseline) | 1 | 4 | 1 |
| W1 | 1 | 4 | 2 |
| W2 | 2 | 4 | 1 |
| W3 | 1 | 5 | 1 |
| W4 | 1 | 5 | 2 |

## Status

Work in progress. The model is being built step by step:

- [x] 1. Load and clean POS data, basket size distribution
- [x] 2. Checkout choice model (logit) calibrated on the data
- [x] 3. Service time regressions, breaks between customers, exceptions
- [x] 4. Basic SimPy model with queue verification (Erlang C)
- [ ] 5. Full customer flow: shopping time, queue choice and switching, SCO assistant interventions
- [ ] 6. Experiments: variants W0 to W4, replications, common random numbers
- [ ] 7. Statistics, sensitivity analysis and charts

## Project structure

```
self-checkout-queue-simulation/
├── data/pos/          POS transaction files (not tracked, see below)
├── results/           generated output (not tracked)
├── pos_data.py        loading, cleaning, basket size distribution
├── calibration.py     model parameters estimated from the data (logit, service times)
├── params.py          model parameters and store layout (variant W0)
├── simulation.py      full checkout zone model (staffed checkouts + SCO)
├── model.py           simplified M/M/c model used for verification
├── validation.py      model checks against queueing theory (Erlang C, Little's law)
├── main.py            entry point
└── requirements.txt
```

## Data

The model uses the open POS dataset by Antczak and Weron:

T. Antczak, R. Weron, *Point of Sale (POS) Data from a Supermarket: Transactions and Cashier Operations*, Data 4(2) (2019) 67, https://doi.org/10.3390/data4020067

The data is licensed under CC BY-NC, so it is not included here. Download the supplementary files from the article page and put these three files in `data/pos/`:

- `POS_transactions_20171207-20171219.csv`
- `POS_transactions_20190213-20190226.csv`
- `POS_transactions_20190328-20190410.csv`

## Getting started

```
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python pos_data.py
python calibration.py
python validation.py
python simulation.py
```

Expected output:

- `pos_data.py`: 162,930 valid transactions, 24.6% of them at self-checkouts, mean basket size of 15.5 items.
- `calibration.py`: logit parameters a = 0.2624 and b = -0.6597 estimated with maximum likelihood. Brent's method then shifts a to 1.6782 so that 54% of customers prefer self-checkouts, the share reported by ECR Retail Loss (2026). It also fits service time regressions (ln T = b + a ln n) for staffed and self-checkouts, flags unusually long transactions with Tukey's rule (1.80% and 1.33%), fits a gamma distribution to breaks between customers at staffed checkouts (mean 17.1 s) and a regression for packing time at self-checkouts (mean 56.6 s).
- `validation.py`: runs a simplified M/M/4 version of the model (80 customers per hour, mean service 150 s) in 30 replications. The simulated mean wait (150.4 ± 28.2 s) matches the Erlang C formula (148.0 s), and Little's law holds (L = 6.72, λW = 6.70).
- `simulation.py`: runs variant W0 for 10 hours with 90 customers per hour. Each customer gets a basket size, shopping time, preferred checkout type and service time drawn from the calibrated distributions. Queue choice and SCO assistant interventions come in the next step.

## Author

Andrzej Tracz, Lublin University of Technology