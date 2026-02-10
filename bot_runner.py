import sqlite3
import json
import websocket
import os
import threading
import asyncio
from cryptography.fernet import Fernet

DATABASE = 'users.db'
ENCRYPTION_KEY = b'4M-facj1b_t1QInD9SAr0swkafcL7pkuvaX9MVbN72g='
cipher_suite = Fernet(ENCRYPTION_KEY)

class EncryptionHandler:
    @staticmethod
    def decrypt_token(encrypted_token):
        return cipher_suite.decrypt(encrypted_token.encode()).decode()

def get_user_token(user_id):
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    user = conn.execute('SELECT deriv_token_encrypted FROM users WHERE id = ?', (user_id,)).fetchone()
    conn.close()
    
    if user and user['deriv_token_encrypted']:
        try:
            return EncryptionHandler.decrypt_token(user['deriv_token_encrypted'])
        except Exception as e:
            print(f"Decryption error: {e}")
    return None

def get_all_accounts(user_id):
    token = get_user_token(user_id)
    if not token:
        return []

    try:
        ws = websocket.create_connection("wss://ws.binaryws.com/websockets/v3?app_id=117276", timeout=15)
        ws.send(json.dumps({"authorize": token}))
        auth = json.loads(ws.recv())
        if 'error' in auth:
            ws.close()
            return []

        # Fetch all accounts (loginids)
        ws.send(json.dumps({"get_account_status": 1}))
        response = json.loads(ws.recv())
        ws.close()

        if 'error' in response or 'accounts_list' not in response:
            return []

        accounts = []
        for acc in response['accounts_list']:
            accounts.append({
                'loginid': acc['loginid'],
                'currency': acc['currency'],
                'balance': acc.get('balance', 0.0),
                'type': 'Real' if 'CR' in acc['loginid'] else 'Demo'
            })
        print("Fetched accounts:", accounts)  # Debug
        return accounts
    except Exception as e:
        print("Accounts fetch error:", str(e))
        return []

def get_account_balance_display(user_id, selected_loginid=None):
    token = get_user_token(user_id)
    if not token:
        return "Not connected"

    try:
        ws = websocket.create_connection("wss://ws.binaryws.com/websockets/v3?app_id=117276", timeout=15)
        ws.send(json.dumps({"authorize": token}))
        auth = json.loads(ws.recv())
        if 'error' in auth:
            ws.close()
            return f"Auth error: {auth['error']['message']}"

        # Use selected or default
        loginid = selected_loginid if selected_loginid else auth['authorize']['loginid']
        print(f"Using loginid for balance: {loginid}")

        ws.send(json.dumps({"balance": 1, "account": loginid}))
        balance_response = json.loads(ws.recv())
        ws.close()

        if 'error' in balance_response:
            return f"Balance error: {balance_response['error']['message']}"

        bal = balance_response['balance']
        amount = float(bal['balance'])
        currency = bal['currency']
        account_type = "Real" if "CR" in loginid else "Demo"
        return f"{amount:,.2f} {currency} ({account_type} - ID: {loginid})"
    except Exception as e:
        print("Balance fetch error:", str(e))
        return f"Failed to fetch: {str(e)}"

def run_bot(user_id, bot_name, params=None):
    token = get_user_token(user_id)
    if not token:
        return "Deriv token not found."

    bot_path = os.path.join('bots', bot_name)
    if not os.path.exists(bot_path):
        return f"Bot not found: {bot_name}"

    def bot_thread():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            from deriv_api import DerivAPI
            api = DerivAPI(app_id=117276)
            auth_resp = loop.run_until_complete(api.authorize({'authorize': token}))
            if 'error' in auth_resp:
                print("Auth failed:", auth_resp['error'])
                return
            print(f"Bot '{bot_name}' authorized for user {user_id}.")
            spec = importlib.util.spec_from_file_location("user_bot", bot_path)
            user_bot_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(user_bot_module)
            if hasattr(user_bot_module, 'run_strategy'):
                loop.run_until_complete(user_bot_module.run_strategy(api, params or {}))
            else:
                print(f"No run_strategy in '{bot_name}'.")
        except Exception as e:
            print(f"Bot error for user {user_id}: {str(e)}")
        finally:
            loop.close()

    thread = threading.Thread(target=bot_thread, daemon=True)
    thread.start()
    return f"Bot '{bot_name}' started in background."
