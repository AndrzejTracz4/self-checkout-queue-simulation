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
- [x] 5. Full customer flow: shopping time, queue choice and switching, SCO assistant interventions
- [x] 6. Experiments: variants W0 to W4, replications, common random numbers
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
├── experiments.py     variants W0 to W4: saturation test, warm-up, load levels
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
python experiments.py   # about 8 minutes
```

Expected output:

- `pos_data.py`: 162,930 valid transactions, 24.6% of them at self-checkouts, mean basket size of 15.5 items.
- `calibration.py`: logit parameters a = 0.2624 and b = -0.6597 estimated with maximum likelihood. Brent's method then shifts a to 1.6782 so that 54% of customers prefer self-checkouts, the share reported by ECR Retail Loss (2026). It also fits service time regressions (ln T = b + a ln n) for staffed and self-checkouts, flags unusually long transactions with Tukey's rule (1.80% and 1.33%), fits a gamma distribution to breaks between customers at staffed checkouts (mean 17.1 s) and a regression for packing time at self-checkouts (mean 56.6 s).
- `validation.py`: runs a simplified M/M/4 version of the model (80 customers per hour, mean service 150 s) in 30 replications. The simulated mean wait (150.4 ± 28.2 s) matches the Erlang C formula (148.0 s), and Little's law holds (L = 6.72, λW = 6.70).
- `simulation.py`: runs variant W0 for 10 hours with 90 customers per hour. Each customer gets a basket size, shopping time, preferred checkout type and service time drawn from the calibrated distributions. At the checkouts the customer estimates the wait in each queue and picks the preferred checkout type, unless another queue is shorter by more than 173 s. While waiting, the customer checks every 10 s whether switching queues would pay off. At self-checkouts the assistant is called on average 0.1 times per transaction (about 30 s each, ECR Retail Loss 2026), and the terminal stays blocked until the assistant has finished. 1% of payments need a second card attempt (+48 s, Polasik et al. 2012). If the estimated wait is longer than 30 minutes, the customer leaves without buying (balking). Every customer has their own random number stream, so customer number 57 in replication 3 has the same basket and service times in every variant. With seed 1: 867 customers served, 53.1% prefer self-checkouts and 64.8% use them, mean wait 43 s at self-checkouts and 77 s at the staffed checkout, assistant busy 4.7% of the time.
- `experiments.py`: runs every variant 30 times (replications) for 10 hours and drops the first 2 hours (warm-up). A saturation test with 400 customers per hour gives the maximum throughput of each variant. Load levels of 50, 75, 90 and 115% of the W0 maximum are then run for all variants. Results go to `results/replications.csv` and `results/welch_curve.csv`.

## Results so far (stage 6)

Maximum throughput (saturation test, 400 customers per hour, mean ± 95% confidence interval):

| Variant | Customers per hour |
|---|---|
| W0 (baseline) | 122.0 ± 0.9 |
| W1 (+assistant) | 121.4 ± 0.8 |
| W2 (+staffed checkout) | 164.2 ± 1.1 |
| W3 (+SCO) | 141.5 ± 0.9 |
| W4 (+SCO +assistant) | 140.8 ± 1.1 |

Mean wait at 90% load (109.8 customers per hour): W0 254 s, W1 248 s, W2 34 s, W3 71 s, W4 71 s. The assistant is busy only about 6% of the time, so a second assistant has almost nothing to do. An extra staffed checkout helps the most. Statistical tests and charts come in stage 7.

## How it works, in plain words

Imagine one evening in the store, sped up so that 10 hours take half a second. Customers walk in at random moments, about 1.5 per minute. Each one picks up a random number of products, shops for around 15 minutes and walks to the checkouts. Someone with 3 items usually prefers a self-checkout. Someone with a full trolley prefers the cashier, unless the cashier queue is clearly much longer. While queuing, people look around and move to another queue if it pays off. At a self-checkout something sometimes goes wrong (an age check, a weight error) and the customer waits for the assistant.

We play this evening 30 times with different random numbers and average the results. Every variant (for example "add a second assistant") gets exactly the same 30 evenings with the same customers. So any difference between variants comes from the change in the store, not from luck.

## Key formulas

Load of a group of checkouts (must be below 1, otherwise the queue grows without limit):

$$\rho = \frac{\lambda \, \bar S}{c}$$

λ is arrivals per second, S̄ is the mean service time in seconds and c is the number of checkouts. Example: 90 customers per hour at 4 self-checkouts with 178 s each gives ρ = (90/3600 · 178) / 4 = 1.11. That would be too much if everyone went to the SCOs, which is why customers are split between the two checkout types.

Confidence interval for the mean of n replications:

$$\bar x \pm t_{0.975,\,n-1} \, \frac{s}{\sqrt n}$$

x̄ is the mean, s is the standard deviation across replications and t is the Student t quantile (2.045 for n = 30). Example: mean 122.0 and s = 2.4 give 122.0 ± 2.045 · 2.4 / √30 = 122.0 ± 0.9.

Paired difference with common random numbers:

$$\operatorname{Var}(X - Y) = \operatorname{Var}(X) + \operatorname{Var}(Y) - 2\operatorname{Cov}(X, Y)$$

Variants run on the same customers, so their results are positively correlated and the variance of the difference shrinks. That is why small differences between variants can still be detected.

## Author

Andrzej Tracz, Lublin University of Technology