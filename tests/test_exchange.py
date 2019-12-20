import time
import random
from itertools import permutations
from .simulation import Curve
from .conftest import UU, PRECISIONS

N_COINS = 3


def test_few_trades(w3, coins, cerc20s, swap):
    sam = w3.eth.accounts[0]  # Sam owns the bank
    from_sam = {'from': sam}
    bob = w3.eth.accounts[1]  # Bob the customer
    from_bob = {'from': bob}

    # Allow $1000 of each coin
    deposits = []
    for c, cc, u in zip(coins, cerc20s, UU):
        rate = cc.caller.exchangeRateStored() * (1 + len(deposits))
        cc.functions.set_exchange_rate(rate).transact(from_sam)
        c.functions.approve(cc.address, 1000 * u).transact(from_sam)
        cc.functions.mint(1000 * u).transact(from_sam)
        balance = cc.caller.balanceOf(sam)
        deposits.append(balance)
        cc.functions.approve(swap.address, balance).transact(from_sam)

    # Adding $100 liquidity of each coin
    swap.functions.add_liquidity(
        [b // 10 for b in deposits], int(time.time()) + 3600
    ).transact(from_sam)

    # Fund the customer with $100 of each coin
    for c, u in zip(coins, UU):
        c.functions.transfer(bob, 100 * u).transact(from_sam)

    # Customer approves
    coins[0].functions.approve(swap.address, 50 * UU[0]).transact(from_bob)

    # And trades
    swap.functions.exchange_underlying(
        0, 1, 1 * UU[0], int(0.9 * UU[1]), int(time.time()) + 3600
    ).transact(from_bob)

    assert coins[0].caller.balanceOf(bob) == 99 * UU[0]
    assert coins[1].caller.balanceOf(bob) > int(100.9 * UU[1])
    assert coins[1].caller.balanceOf(bob) < 101 * UU[1]

    # Why not more
    swap.functions.exchange_underlying(
        0, 1, 1 * UU[0], int(0.9 * UU[1]), int(time.time()) + 3600
    ).transact(from_bob)

    assert coins[0].caller.balanceOf(bob) == 98 * UU[0]
    assert coins[1].caller.balanceOf(bob) > int(101.9 * UU[1])
    assert coins[1].caller.balanceOf(bob) < 102 * UU[1]


def test_simulated_exchange(w3, coins, cerc20s, swap):
    sam = w3.eth.accounts[0]  # Sam owns the bank
    bob = w3.eth.accounts[1]  # Bob the customer
    from_sam = {'from': sam}
    from_bob = {'from': bob}

    # Allow $1000 of each coin
    deposits = []
    for c, cc, u in zip(coins, cerc20s, UU):
        c.functions.approve(cc.address, 1000 * u).transact(from_sam)
        cc.functions.mint(1000 * u).transact(from_sam)
        balance = cc.caller.balanceOf(sam)
        deposits.append(balance)
        cc.functions.approve(swap.address, balance).transact(from_sam)

    # Adding $100 liquidity of each coin
    liquidity = [b // 10 for b in deposits]
    swap.functions.add_liquidity(
        liquidity, int(time.time()) + 3600
    ).transact(from_sam)

    # Model
    balances = [int(swap.caller.balances(i)) for i in range(3)]
    rates = [int(c.caller.exchangeRateStored()) * p for c, p in zip(cerc20s, PRECISIONS)]
    curve = Curve(2 * 360, balances, N_COINS, rates)

    for c, u in zip(coins, UU):
        # Fund the customer with $100 of each coin
        c.functions.transfer(bob, 100 * u).transact(from_sam)
        # Approve by Bob
        c.functions.approve(swap.address, 100 * u).transact(from_bob)

    # Start trading!
    for k in range(50):
        i, j = random.choice(list(permutations(range(N_COINS), 2)))
        value = random.randrange(5 * UU[i])
        x_0 = coins[i].caller.balanceOf(bob)
        y_0 = coins[j].caller.balanceOf(bob)
        coins[i].functions.approve(swap.address, value).transact(from_bob)
        swap.functions.exchange_underlying(
            i, j, value,
            int(0.5 * value * UU[j] / UU[i]),
            int(time.time()) + 3600
        ).transact(from_bob)
        x_1 = coins[i].caller.balanceOf(bob)
        y_1 = coins[j].caller.balanceOf(bob)

        dy_m = curve.exchange(i, j, value * max(UU) // UU[i]) * UU[j] // max(UU)

        assert x_0 - x_1 == value
        assert (y_1 - y_0) - dy_m < dy_m * 1e-10

    # Let's see what we have left
    x = [swap.caller.balances(i) for i in range(N_COINS)]
    assert tuple(round(a / b, 10) for a, b in zip(x, curve.x)) == (1.0,) * N_COINS

    assert sum(x[i] * rates[i] / 1e18 for i in range(N_COINS)) > 300 * max(UU)
