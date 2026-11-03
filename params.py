from dataclasses import dataclass

# wartości policzone w calibration.py (etapy 2 i 3)


@dataclass
class Params:
    # konfiguracja strefy kasowej (wariant W0)
    trad_checkouts: int = 1
    sco_checkouts: int = 4
    assistants: int = 1

    arrivals_per_hour: float = 90.0

    # czas zakupów: lognormalny, średnio 15 min (założenie)
    shopping_mean_s: float = 900.0
    shopping_cv: float = 0.6

    # wybór kasy: logit przesunięty do 54% SCO (ECR 2026)
    logit_a: float = 1.6782
    logit_b: float = -0.6597

    # kasa tradycyjna: ln T = b + a ln n + sigma z
    trad_b: float = 2.1218
    trad_a: float = 0.6972
    trad_sigma: float = 0.4150
    trad_break_k: float = 4.536        # przerwa gamma
    trad_break_theta: float = 3.771
    trad_exception_p: float = 0.018    # wyjątki u kasjera
    trad_exception_mean_s: float = 75.3
    trad_exception_cv: float = 0.75

    # kasa SCO: skanowanie i pakowanie
    sco_b: float = 3.1117
    sco_a: float = 0.6721
    sco_sigma: float = 0.4166
    pack_b: float = 3.4315
    pack_a: float = 0.2612
    pack_sigma: float = 0.4912

    # wybór kolejki: klient szacuje czekanie ze średnich czasów obsługi
    est_trad_s: float = 86.7           # średnia obsługa u kasjera
    est_sco_s: float = 178.0           # średnia obsługa na SCO
    switch_threshold_s: float = 173.0  # zmiana kolejki, gdy zysk > 2 obsługi u kasjera
    jockey_check_s: float = 10.0       # co ile sekund klient rozgląda się w kolejce

    # interwencje asystenta na SCO (ECR 2026): Poisson na transakcję
    intervention_rate: float = 0.1
    intervention_mean_s: float = 30.0
    intervention_cv: float = 0.5

    # Ponowna płatność kartą (Polasik i in. 2012)
    card_retry_p: float = 0.01
    card_retry_s: float = 48.0

    # rezygnacja z zakupów, gdy szacowane czekanie przekracza 30 min (założenie)
    balk_wait_s: float = 1800.0

    # eksperyment: rozgrzewka odrzucana z wyników, potem pomiar
    warmup_h: float = 2.0

    hours: float = 10.0