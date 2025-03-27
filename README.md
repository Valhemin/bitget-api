# Bitget Multi-Account Trader

A Python tool for trading cryptocurrencies on Bitget exchange across multiple accounts simultaneously. This tool allows you to execute buy/sell orders with a simple command-line interface.

## Features

- Manage multiple Bitget accounts simultaneously
- Execute buy/sell orders across all accounts with a single command
- Support for both market and limit orders
- Interactive mode for missing configuration parameters
- Flexible trading options with real-time price information
- Cancel pending limit orders across all accounts

## Installation

1. Clone this repository:
```
git clone git@github.com:Valhemin/bitget-api.git
cd bitget-api
```

2. Install the required dependencies:
```
pip install -r requirements.txt
```

3. Configure your accounts in `config.json` (a default template will be created on first run)

## Configuration

The tool uses a `config.json` file to store API keys and trading preferences. On first run, a default template will be created that you need to edit:

```json
{
    "accounts": [
        {
            "name": "main_account",
            "api_key": "YOUR_API_KEY_HERE",
            "api_secret": "YOUR_API_SECRET_HERE",
            "passphrase": "YOUR_PASSPHRASE_HERE",
            "is_sub_account": false
        },
        {
            "name": "sub_account_1",
            "api_key": "SUB_API_KEY_HERE",
            "api_secret": "SUB_API_SECRET_HERE",
            "passphrase": "SUB_PASSPHRASE_HERE",
            "is_sub_account": true,
            "main_account_uid": "MAIN_ACCOUNT_UID_HERE"
        }
    ],
    "trading": {
        "symbol": "BTCUSDT_SPBL", // SPBL to trade with spot
        "coin": "SPELL",
        "quote": "USDT",
        "price": 0,
        "buy_amount": 10,
        "sell_percentage": 100
    }
}
```

### Configuration Options

#### Accounts
- `name`: A name for the account (used in logs)
- `api_key`, `api_secret`, `passphrase`: Your Bitget API credentials
- `is_sub_account`: Set to true if this is a sub-account
- `main_account_uid`: The UID of the main account (required for transfers from sub-accounts)

#### Trading
- `symbol`: Trading pair in format BASE_QUOTE (e.g., BTC_USDT)
- `coin`: The trading cryptocurrency (e.g., BTC, ETH, SOL)
- `quote`: The quote currency used for pricing (e.g., USDT, USDC)
- `price`: Price for limit orders
- `buy_amount`: Amount in quote currency (e.g., USDT) to spend on buys
- `sell_percentage`: Percentage of available balance to sell

## Usage

Run the script:
```
python main.py
```

Follow the command-line interface to:
1. Execute BUY for all accounts
2. Execute SELL for all accounts
3. Cancel pending limit orders for all accounts
4. Exit

## Logging

The application logs all actions to both the console and a file named `trading_log.log` in the application directory.

## Security

- Store your API keys securely and never share them
- Consider using the IP restriction feature in your Bitget API settings
- Use API keys with minimal permissions (trading only, no withdrawal rights)

## Disclaimer

This tool is provided for educational purposes only. Use at your own risk. The authors take no responsibility for any financial losses incurred through the use of this software.
