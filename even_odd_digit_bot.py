# even_odd_digit_bot.py - Converted from your DBot XML (Even/Odd Digit Strategy)
import asyncio
from deriv_api import DerivAPI

async def run_strategy(api, params):
    # Parameters from your form
    symbol = params.get('market', '1HZ75V')  # Volatility 75
    stake = float(params.get('stake', 0.35))
    duration = int(params.get('duration', 1))  # ticks
    contract_type = params.get('contract_type', 'DIGITEVEN')  # Default to Even

    # Settings from your XML
    max_losses = 100
    take_profit = 5
    initial_stake = 1.0
    value_after_first_win = 1.0
    max_followed_loss_stop = 20
    martingale_enabled = True
    martingale_multiplier = 1.1

    # Counters and trackers
    even_counter = 0
    odd_counter = 0
    loss_counter = 0
    loss_account_gale = 0
    current_stake = initial_stake

    print("Even/Odd Digit Bot started. Monitoring ticks on", symbol)

    # Subscribe to ticks
    await api.ticks({'ticks': symbol, 'subscribe': 1})

    while True:
        try:
            msg = await api.recv()
            if 'tick' in msg:
                tick_value = msg['tick']['quote']
                last_digit = int(str(tick_value)[-1])  # Get last digit

                if last_digit % 2 == 0:
                    even_counter += 1
                    odd_counter = 0
                    print(f"Even digit ({last_digit}) - Even counter: {even_counter}")
                    purchase_type = "DIGITEVEN"
                else:
                    odd_counter += 1
                    even_counter = 0
                    print(f"Odd digit ({last_digit}) - Odd counter: {odd_counter}")
                    purchase_type = "DIGITODD"

                # Purchase logic from your XML
                if even_counter < 2:
                    # Buy Even
                    await place_purchase(api, "DIGITEVEN", current_stake, duration)
                else:
                    # Reset and buy Odd
                    even_counter = 0
                    odd_counter = 0
                    await place_purchase(api, "DIGITODD", current_stake, duration)

                # Simplified after-purchase logic (real bot needs contract finish event)
                # For now, assume win/loss after purchase - adjust stake with Martingale
                # In full version, listen for 'proposal_open_contract' or 'sell' to get result
                # Here we simulate adjustment
                if loss_counter > 0:  # On loss
                    loss_counter += 1
                    loss_account_gale += 1
                    if martingale_enabled:
                        current_stake = current_stake * martingale_multiplier
                else:
                    # Win - reset
                    loss_counter = 0
                    loss_account_gale = 0
                    current_stake = value_after_first_win

                # Stop conditions
                profit = await get_profit(api)  # Placeholder - use real profit call
                if profit >= take_profit:
                    print("Take Profit reached! Stopping.")
                    break
                if loss_counter >= max_followed_loss_stop:
                    print("Max followed loss reached! Stopping.")
                    break

        except Exception as e:
            print("Error in loop:", e)
            break

async def place_purchase(api, purchase_type, stake, duration):
    proposal = {
        "proposal": 1,
        "amount": stake,
        "basis": "stake",
        "contract_type": purchase_type,
        "currency": "USD",
        "duration": duration,
        "duration_unit": "t",
        "symbol": "1HZ75V"
    }
    prop_resp = await api.proposal(proposal)
    if 'error' in prop_resp:
        print("Proposal error:", prop_resp['error'])
        return

    buy_resp = await api.buy({
        "buy": prop_resp['proposal']['id'],
        "price": prop_resp['proposal']['ask_price']
    })
    print("Trade placed:", buy_resp)

async def get_profit(api):
    # Placeholder - real implementation needs account statement or profit call
    return 0.0  # Replace with actual profit check
