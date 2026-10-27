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
- [ ] 2. Checkout choice model (logit) calibrated on the data
- [ ] 3. Service time regressions, breaks between customers, exceptions
- [ ] 4. Basic SimPy model with queue verification (Erlang C)
- [ ] 5. Full customer flow: shopping time, queue choice and switching, SCO assistant interventions
- [ ] 6. Experiments: variants W0 to W4, replications, common random numbers
- [ ] 7. Statistics, sensitivity analysis and charts

## Project structure

```
retail-pos-queue-simulation/
├── data/pos/          POS transaction files (not tracked, see below)
├── results/           generated output (not tracked)
├── pos_data.py        loading, cleaning, basket size distribution
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
```

Expected output: 162,930 valid transactions, 24.6% of them at self-checkouts, mean basket size of 15.5 items.

## Author

Andrzej Tracz, Lublin University of Technology