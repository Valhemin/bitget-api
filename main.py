import json
import time
import sys
import threading
import os

# Import python-bitget library
from pybitget import Client

# Import rich for colorful logging
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.panel import Panel
from rich import print as rprint

# Configure rich logging
console = Console()


class BitgetClient:
    def __init__(self, api_key, api_secret_key, passphrase, account_name=""):
        self.account_name = account_name
        try:
            self.client = Client(
                api_key=api_key, api_secret_key=api_secret_key, passphrase=passphrase
            )
        except Exception as e:
            rprint(
                f"[bold red]Failed to initialize client for {account_name}: {str(e)}[/bold red]"
            )
            raise

    def get_account_assets(self, coin=None):
        try:
            if coin:
                # Get specific coin info
                response = self.client.spot_get_account_assets(coin=coin)
            else:
                # Get all assets
                response = self.client.spot_get_account_assets(coin="SPELL")

            if not response or "data" not in response:
                rprint(
                    f"[bold red]Invalid response getting assets for {self.account_name}[/bold red]"
                )
                return {"code": -1, "msg": "Invalid API response"}

            return response
        except Exception as e:
            rprint(
                f"[bold red]Error getting account assets for {self.account_name}: {str(e)}[/bold red]"
            )
            return {"code": -1, "msg": str(e)}

    def place_order(self, symbol, side, orderType, quantity=None, price=None):
        try:
            # Prepare parameters based on order type and side
            params = {
                "symbol": symbol,
                "side": side,  # "buy" or "sell"
                "orderType": orderType,  # "limit" or "market"
                "force": "gtc",
                "clientOrderId": f"{int(time.time() * 1000)}",
            }

            if orderType == "limit":
                if not price or float(price) <= 0:
                    raise ValueError("Limit orders require a valid price")
                params["price"] = str(price)
                params["quantity"] = str(quantity)
            elif orderType == "market":
                params["quantity"] = str(quantity)  # Amount of base currency to sell

            # Call API to place order - removed console.status to avoid nested live displays
            rprint(
                f"[bold blue]Placing {side.upper()} order for {self.account_name}...[/bold blue]"
            )
            response = self.client.spot_place_order(**params)

            return response
        except Exception as e:
            return {"code": -1, "msg": str(e)}

    def get_order_details(self, symbol, orderId=None, clientOrderId=None):
        try:
            params = {"symbol": symbol}

            if orderId:
                params["orderId"] = orderId
            elif clientOrderId:
                params["clientOid"] = clientOrderId

            # Call API to get order details
            response = self.client.spot_get_order_details(**params)
            return response
        except Exception as e:
            rprint(
                f"[bold red]Error getting order details for {self.account_name}: {str(e)}[/bold red]"
            )
            return {"code": -1, "msg": str(e)}

    def transfer_funds(self, coin, amount, from_type="spot", to_type="funding"):
        """Transfer funds between accounts (spot, funding, mix)"""
        try:
            params = {
                "coin": coin,
                "amount": str(amount),
                "fromType": from_type,
                "toType": to_type,
            }
            # Call API to transfer funds - removed console.status
            rprint(
                f"[bold blue]Transferring {amount} {coin} between accounts...[/bold blue]"
            )
            response = self.client.spot_account_transfer(**params)
            return response
        except Exception as e:
            rprint(
                f"[bold red]Error transferring funds for {self.account_name}: {str(e)}[/bold red]"
            )
            return {"code": -1, "msg": str(e)}

    def inner_transfer(self, coin, amount, to_uid):
        """Transfer funds to another Bitget account (internal transfer)"""
        try:
            params = {"coin": coin, "amount": str(amount), "toUid": to_uid}
            # Call API for inner transfer - removed console.status
            rprint(
                f"[bold blue]Transferring {amount} {coin} to account {to_uid}...[/bold blue]"
            )
            response = self.client.spot_account_inner_transfer(**params)
            return response
        except Exception as e:
            rprint(
                f"[bold red]Error making inner transfer for {self.account_name}: {str(e)}[/bold red]"
            )
            return {"code": -1, "msg": str(e)}

    def get_current_price(self, symbol):
        """Get current market price for a trading pair"""
        try:
            # Using the ticker endpoint to get current price information
            response = self.client.spot_get_ticker(symbol=symbol)
            if "data" in response and response["data"] and "close" in response["data"]:
                return float(response["data"]["close"])
            else:
                rprint(
                    f"[bold yellow]Error getting price for {symbol}: Invalid response format[/bold yellow]"
                )
                return None
        except Exception as e:
            rprint(
                f"[bold red]Error getting current price for {symbol}: {str(e)}[/bold red]"
            )
            return None

    def get_open_orders(self, symbol):
        """Get all open orders for a specific symbol"""
        try:
            response = self.client.spot_get_open_orders(symbol=symbol)
            if not response or "data" not in response:
                rprint(f"[bold red]Invalid response getting open orders for {symbol}[/bold red]")
                return {"code": -1, "msg": "Invalid API response", "data": []}
            return response
        except Exception as e:
            rprint(f"[bold red]Error getting open orders: {str(e)}[/bold red]")
            return {"code": -1, "msg": str(e), "data": []}
    
    def cancel_order(self, symbol, order_id):
        """Cancel a specific order by ID"""
        try:
            response = self.client.spot_cance_order(symbol=symbol, orderId=order_id)
            return response
        except Exception as e:
            rprint(f"[bold red]Error canceling order {order_id}: {str(e)}[/bold red]")
            return {"code": -1, "msg": str(e)}


class MultiAccountTrader:
    def __init__(self, config_path="config.json"):
        self.load_config(config_path)
        self.thread_lock = threading.Lock()
        self.clients = {}
        self.initialize_clients()

    def load_config(self, config_path):
        try:
            if not os.path.exists(config_path):
                self.create_default_config(config_path)
                rprint(
                    f"[bold yellow]Created default config at {config_path}. Please edit with your account details.[/bold yellow]"
                )
                sys.exit(0)

            with open(config_path, "r", encoding="utf-8") as f:
                self.config = json.load(f)

            rprint(
                f"[bold green]Loaded config with {len(self.config['accounts'])} accounts[/bold green]"
            )

            # Validate config has required fields
            required_fields = ["accounts", "trading"]
            for field in required_fields:
                if field not in self.config:
                    raise ValueError(f"Missing required config section: {field}")

            if not self.config["accounts"]:
                rprint("[bold red]No accounts configured in config.json[/bold red]")
                sys.exit(1)

        except json.JSONDecodeError:
            rprint(f"[bold red]Invalid JSON in {config_path}[/bold red]")
            sys.exit(1)
        except Exception as e:
            rprint(f"[bold red]Failed to load config: {str(e)}[/bold red]")
            sys.exit(1)

    def create_default_config(self, config_path):
        default_config = {
            "accounts": [
                {
                    "name": "account_1",
                    "api_key": "YOUR_API_KEY_HERE",
                    "api_secret": "YOUR_API_SECRET_HERE",
                    "passphrase": "YOUR_PASSPHRASE_HERE"
                },
                {
                    "name": "account_2",
                    "api_key": "SECOND_API_KEY_HERE",
                    "api_secret": "SECOND_API_SECRET_HERE",
                    "passphrase": "SECOND_PASSPHRASE_HERE"
                },
            ],
            "trading": {
                "symbol": "BTCUSDT_SPBL",  
                "coin": "BTC",  
                "quote": "USDT"
            },
        }

        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(default_config, f, indent=4)

    def initialize_clients(self):
        with Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]Initializing accounts..."),
            console=console,
        ) as progress:
            task = progress.add_task("", total=len(self.config["accounts"]))

            for account in self.config["accounts"]:
                try:
                    account_name = account.get(
                        "name", f"account_{len(self.clients) + 1}"
                    )
                    progress.update(
                        task,
                        description=f"[bold blue]Initializing {account_name}...[/bold blue]",
                    )

                    if (
                        "api_key" not in account
                        or "api_secret" not in account
                        or "passphrase" not in account
                    ):
                        rprint(
                            f"\n[bold red]Account {account_name} missing API credentials[/bold red]"
                        )
                        progress.advance(task)
                        continue

                    client = BitgetClient(
                        api_key=account["api_key"],
                        api_secret_key=account["api_secret"],
                        passphrase=account["passphrase"],
                        account_name=account_name,
                    )

                    # Test API connection with a basic request
                    assets = client.get_account_assets()

                    if "data" in assets:
                        self.clients[account_name] = {
                            "client": client,
                            "active": True,
                        }
                        rprint(
                            f"\n[bold green]Successfully initialized account {account_name}[/bold green]"
                        )
                    else:
                        rprint(
                            f"\n[bold red]Failed to initialize account {account_name}: API test failed[/bold red]"
                        )

                except Exception as e:
                    rprint(
                        f"\n[bold red]Error initializing client for {account_name}: {str(e)}[/bold red]"
                    )

                progress.advance(task)

        if not self.clients:
            rprint("\n[bold red]No accounts could be initialized. Exiting.[/bold red]")
            sys.exit(1)

    def trade_all_accounts(self, action):
        """Execute trading action on all accounts sequentially to avoid display conflicts"""
        results = {}
        active_accounts = {
            name: info for name, info in self.clients.items() if info["active"]
        }

        if not active_accounts:
            rprint("[bold yellow]No active accounts found[/bold yellow]")
            return results
            
        # Get all user inputs before starting the Progress display
        user_inputs = {}
        if action == "buy_market" and "buy_amount" not in self.config["trading"]:
            quote = self.config["trading"]["quote"]
            amount = input(f"Enter amount of {quote} to spend for all accounts: ").strip() or "0"
            try:
                user_inputs["buy_amount"] = float(amount)
            except ValueError:
                rprint(f"[bold red]Invalid amount: {amount}[/bold red]")
                return results
                
        elif action == "buy_limit":
            quote = self.config["trading"]["quote"]
            coin = self.config["trading"]["coin"]
            symbol = self.config["trading"]["symbol"]
            
            # Get current market price for reference
            client = next(iter(active_accounts.values()))["client"]
            current_price = client.get_current_price(symbol)
            if current_price:
                rprint(f"\n[cyan]Current {coin} price: {current_price} {quote}[/cyan]")
            
            # Get quantity if not in config
            if "buy_amount" not in self.config["trading"]:
                amount = input(f"Enter amount of {quote} to spend for all accounts: ").strip() or "0"
                try:
                    user_inputs["buy_amount"] = float(amount)
                except ValueError:
                    rprint(f"[bold red]Invalid amount: {amount}[/bold red]")
                    return results
            
            # Get price if not in config or if price is zero
            if "price" not in self.config["trading"] or self.config["trading"]["price"] <= 0:
                price_input = input(f"Enter limit price in {quote} (current: {current_price}): ").strip() or str(current_price)
                try:
                    user_inputs["price"] = float(price_input)
                except ValueError:
                    rprint(f"[bold red]Invalid price: {price_input}[/bold red]")
                    return results
                    
        elif action == "sell_market" and "sell_percentage" not in self.config["trading"]:
            coin = self.config["trading"]["coin"]
            percentage = input(f"Enter percentage of {coin} to sell for all accounts (1-100): ").strip() or "100"
            try:
                user_inputs["sell_percentage"] = float(percentage)
                if user_inputs["sell_percentage"] <= 0 or user_inputs["sell_percentage"] > 100:
                    rprint(f"[bold red]Invalid percentage: {percentage}[/bold red]")
                    return results
            except ValueError:
                rprint(f"[bold red]Invalid percentage: {percentage}[/bold red]")
                return results
                
        elif action == "sell_limit":
            coin = self.config["trading"]["coin"]
            quote = self.config["trading"]["quote"]
            symbol = self.config["trading"]["symbol"]
            
            # Get current market price for reference
            client = next(iter(active_accounts.values()))["client"]
            current_price = client.get_current_price(symbol)
            if current_price:
                rprint(f"\n[cyan]Current {coin} price: {current_price} {quote}[/cyan]")
            
            # Get sell percentage if not in config
            if "sell_percentage" not in self.config["trading"]:
                percentage = input(f"Enter percentage of {coin} to sell for all accounts (1-100): ").strip() or "100"
                try:
                    user_inputs["sell_percentage"] = float(percentage)
                    if user_inputs["sell_percentage"] <= 0 or user_inputs["sell_percentage"] > 100:
                        rprint(f"[bold red]Invalid percentage: {percentage}[/bold red]")
                        return results
                except ValueError:
                    rprint(f"[bold red]Invalid percentage: {percentage}[/bold red]")
                    return results
            
            # Get price if not in config or if price is zero
            if "price" not in self.config["trading"] or self.config["trading"]["price"] <= 0:
                price_input = input(f"Enter limit price in {quote} (current: {current_price}): ").strip() or str(current_price)
                try:
                    user_inputs["price"] = float(price_input)
                except ValueError:
                    rprint(f"[bold red]Invalid price: {price_input}[/bold red]")
                    return results

        # Use a single progress display
        with Progress(SpinnerColumn(), TextColumn(f""), console=console) as progress:
            task = progress.add_task("", total=len(active_accounts))

            # This avoids conflicts with multiple live displays
            for account_name, account_info in active_accounts.items():
                progress.update(
                    task,
                    description=f"[bold blue]Processing {account_name}...[/bold blue]",
                )
                try:
                    # Pass any user inputs to the execute_action method
                    result = self.execute_action(account_name, account_info, action, user_inputs)
                    results[account_name] = result
                    time.sleep(0.3)
                except Exception as e:
                    rprint(
                        f"[bold red]Account {account_name}: Error: {str(e)}[/bold red]"
                    )
                    results[account_name] = None

                progress.advance(task)

        # Print summary
        success_count = len([r for r in results.values() if r])
        total_count = len(results)
        if success_count == total_count:
            rprint(
                Panel(
                    f"[bold green]✓ All {total_count} operations completed successfully[/bold green]"
                )
            )
        else:
            rprint(
                Panel(
                    f"[bold yellow]⚠ {success_count}/{total_count} operations completed successfully[/bold yellow]"
                )
            )

        return results

    def execute_action(self, account_name, account_info, action, user_inputs=None):
        """Execute a specific action for an account"""
        if user_inputs is None:
            user_inputs = {}
            
        if action == "buy_market":
            return self.execute_buy_market(account_name, account_info, user_inputs)
        elif action == "buy_limit":
            return self.execute_buy_limit(account_name, account_info, user_inputs)
        elif action == "sell_market":
            return self.execute_sell_market(account_name, account_info, user_inputs)
        elif action == "sell_limit":
            return self.execute_sell_limit(account_name, account_info, user_inputs)
        elif action == "cancel_buy_limits":
            return self.execute_cancel_buy_limits(account_name, account_info)
        elif action == "cancel_sell_limits":
            return self.execute_cancel_sell_limits(account_name, account_info)
        else:
            rprint(f"[bold yellow]Account {account_name}: Unknown action {action}[/bold yellow]")
            return None

    def execute_buy_market(self, account_name, account_info, user_inputs=None):
        """Execute market buy order for an account"""
        try:
            client = account_info["client"]
            symbol = self.config["trading"]["symbol"]
            quote = self.config["trading"]["quote"]
            user_inputs = user_inputs or {}
            
            # Get quantity from config or user inputs
            if "buy_amount" in user_inputs:
                quantity = user_inputs["buy_amount"]
            elif "buy_amount" in self.config["trading"]:
                quantity = self.config["trading"]["buy_amount"]
                rprint(f"[cyan]Using configured buy amount: {quantity} {quote}[/cyan]")
            else:
                # This should never happen now, but keep as fallback
                rprint(f"[bold red]Account {account_name}: No buy amount specified[/bold red]")
                return None
            
            if quantity <= 0:
                rprint(f"[bold red]Account {account_name}: Invalid buy amount: {quantity}[/bold red]")
                return None

            rprint(f"\n[bold blue]Account [bold yellow]{account_name}[/bold yellow]: Placing MARKET BUY order for {symbol}, amount: {quantity} {quote} [/bold blue]")

            result = client.place_order(
                symbol=symbol, side="buy", orderType="market", quantity=quantity
            )

            if result.get("code") == "00000":
                order_id = result.get("data", {}).get("orderId", "unknown")
                rprint(f"[bold green]Account {account_name}: BUY order placed successfully, order ID: {order_id}[/bold green]")
                return order_id
            else:
                rprint(f"[bold red]Account {account_name}: Failed to place BUY order: {result}[/bold red]")
                return None

        except Exception as e:
            rprint(f"[bold red]Account {account_name}: Error executing BUY: {str(e)}[/bold red]")
            return None

    # Modify the other execute methods similarly to accept and use user_inputs
    def execute_buy_limit(self, account_name, account_info, user_inputs=None):
        """Execute limit buy order for an account"""
        try:
            client = account_info["client"]
            symbol = self.config["trading"]["symbol"]
            quote = self.config["trading"]["quote"]
            coin = self.config["trading"]["coin"]
            user_inputs = user_inputs or {}
            
            # Get quantity from user_inputs, config, or ask user
            if "buy_amount" in user_inputs:
                quantity = user_inputs["buy_amount"]
            elif "buy_amount" in self.config["trading"]:
                quantity = self.config["trading"]["buy_amount"]
                rprint(f"[cyan]Using configured buy amount: {quantity} {quote}[/cyan]")
            else:
                # This should never happen now, but keep as fallback
                rprint(f"[bold red]Account {account_name}: No buy amount specified[/bold red]")
                return None
            
            # Get price from user_inputs, config, or ask user
            if "price" in user_inputs:
                price = user_inputs["price"]
            elif "price" in self.config["trading"] and self.config["trading"]["price"] > 0:
                price = self.config["trading"]["price"]
                rprint(f"[cyan]Using configured price: {price} {quote}[/cyan]")
            else:
                # This should never happen now, but keep as fallback
                current_price = client.get_current_price(symbol)
                price = current_price or 0
                rprint(f"[cyan]Using current market price: {price} {quote}[/cyan]")
            
            if quantity <= 0 or price <= 0:
                rprint(f"[bold red]Account {account_name}: Invalid parameters: quantity={quantity}, price={price}[/bold red]")
                return None
            
            formatted_sell_quantity = int(quantity) if quantity >= 1 else self.format_quantity_for_api(quantity)
            
            rprint(f"\n[bold blue]Account [bold yellow]{account_name}[/bold yellow]: Placing LIMIT BUY order[/bold blue]")
            rprint(f"[bold blue]├─ Amount: {quantity} {quote}[/bold blue]")
            rprint(f"[bold blue]├─ At Price: {self.format_quantity_for_api(price)} {coin}/{quote}[/bold blue]")
            rprint(f"[bold blue]└─ Estimated {coin}: {self.format_quantity_for_api(quantity / price)} {coin}[/bold blue]")

            result = client.place_order(
                symbol=symbol,
                side="buy",
                orderType="limit",
                quantity=quantity / price,
                price=price,
            )

            if result.get("code") == "00000":
                order_id = result.get("data", {}).get("orderId", "unknown")
                rprint(f"[bold green]Account {account_name}: LIMIT BUY order placed successfully, order ID: {order_id}[/bold green]")
                return order_id
            else:
                rprint(f"[bold red]Account {account_name}: Failed to place LIMIT BUY order: {result}[/bold red]")
                return None

        except Exception as e:
            rprint(f"[bold red]Account {account_name}: Error executing LIMIT BUY: {str(e)}[/bold red]")
            return None

    # Similarly update execute_sell_market and execute_sell_limit to receive and use user_inputs
    def execute_sell_market(self, account_name, account_info, user_inputs=None):
        """Execute market sell order for an account"""
        try:
            client = account_info["client"]
            symbol = self.config["trading"]["symbol"]
            coin = self.config["trading"]["coin"]
            quote = self.config["trading"]["quote"]
            user_inputs = user_inputs or {}

            # For sell, get current balance first
            assets = client.get_account_assets(coin=coin)

            if "data" not in assets or not assets["data"]:
                rprint(f"[bold red]Account {account_name}: Failed to get balance for {coin}[/bold red]")
                return None

            available_balance = 0
            for asset in assets["data"]:
                if asset["coinName"] == coin:
                    available_balance = float(asset["available"])
                    break
                    
            if available_balance <= 0:
                rprint(f"[bold red]Account {account_name}: No {coin} balance available[/bold red]")
                return None
                
            # Display available balance
            formatted_balance = self.format_quantity_for_api(available_balance)
            rprint(f"[cyan]Available {coin} balance for {account_name}: {formatted_balance}[/cyan]")

            # Get percentage from user_inputs, config, or ask user
            if "sell_percentage" in user_inputs:
                sell_percentage = user_inputs["sell_percentage"]
            elif "sell_percentage" in self.config["trading"]:
                sell_percentage = self.config["trading"]["sell_percentage"]
                rprint(f"[cyan]Using configured sell percentage: {sell_percentage}%[/cyan]")
            else:
                # This should never happen now, but keep as fallback
                rprint(f"[bold red]Account {account_name}: No sell percentage specified[/bold red]")
                return None
                
            if sell_percentage <= 0 or sell_percentage > 100:
                rprint(f"[bold red]Account {account_name}: Invalid sell percentage: {sell_percentage}[/bold red]")
                return None

            # Get current market price for display
            current_price = client.get_current_price(symbol)
            if current_price is None:
                rprint(f"[bold yellow]Account {account_name}: Unable to get current price, proceeding anyway[/bold yellow]")
                current_price = 0
            else:
                rprint(f"\n[cyan]Current {coin} price: {current_price} {quote}[/cyan]")

            # Calculate quantity to sell
            quantity = available_balance * (sell_percentage / 100)
            estimated_value = quantity * current_price

            # Format the quantity properly to avoid scientific notation issues
            formatted_sell_quantity = int(quantity) if quantity >= 1 else self.format_quantity_for_api(quantity)

            rprint(f"\n[bold blue]Account [bold yellow]{account_name}[/bold yellow]: Placing MARKET SELL order[/bold blue]")
            rprint(f"[bold blue]├─ Amount: {formatted_sell_quantity} {coin} ({sell_percentage}% of {formatted_balance})[/bold blue]")
            if current_price > 0:
                rprint(f"[bold blue]└─ Estimated value: ~{self.format_quantity_for_api(estimated_value)} {quote}[/bold blue]")

            result = client.place_order(
                symbol=symbol,
                side="sell",
                orderType="market",
                quantity=formatted_sell_quantity,
            )

            if result.get("code") == "00000":
                order_id = result.get("data", {}).get("orderId", "unknown")
                rprint(f"[bold green]Account {account_name}: SELL order placed successfully, order ID: {order_id}[/bold green]")
                return order_id
            else:
                rprint(f"[bold red]Account {account_name}: Failed to place SELL order: {result}[/bold red]")
                return None

        except Exception as e:
            rprint(f"[bold red]Account {account_name}: Error executing SELL: {str(e)}[/bold red]")
            return None

    def execute_sell_limit(self, account_name, account_info, user_inputs=None):
        """Execute limit sell order for an account"""
        try:
            client = account_info["client"]
            symbol = self.config["trading"]["symbol"]
            coin = self.config["trading"]["coin"]
            quote = self.config["trading"]["quote"]
            user_inputs = user_inputs or {}
            
            # For sell, get current balance first
            assets = client.get_account_assets(coin=coin)

            if "data" not in assets or not assets["data"]:
                rprint(f"[bold red]Account {account_name}: Failed to get balance for {coin}[/bold red]")
                return None

            available_balance = 0
            for asset in assets["data"]:
                if asset["coinName"] == coin:
                    available_balance = float(asset["available"])
                    break
                
            if available_balance <= 0:
                rprint(f"[bold red]Account {account_name}: No {coin} balance available[/bold red]")
                return None
            
            # Display available balance
            formatted_balance = self.format_quantity_for_api(available_balance)
            rprint(f"[cyan]Available {coin} balance for {account_name}: {formatted_balance}[/cyan]")
            
            # Get current price for reference
            current_price = client.get_current_price(symbol)
            if current_price:
                rprint(f"\n[cyan]Current {coin} price: {current_price} {quote}[/cyan]")
            else:
                rprint(f"[bold yellow]Account {account_name}: Unable to get current price[/bold yellow]")
                current_price = 0

            # Get percentage from user_inputs, config, or ask user
            if "sell_percentage" in user_inputs:
                sell_percentage = user_inputs["sell_percentage"]
            elif "sell_percentage" in self.config["trading"]:
                sell_percentage = self.config["trading"]["sell_percentage"]
                rprint(f"[cyan]Using configured sell percentage: {sell_percentage}%[/cyan]")
            else:
                # This should never happen now, but keep as fallback
                rprint(f"[bold red]Account {account_name}: No sell percentage specified[/bold red]")
                return None
            
            # Get price from user_inputs, config, or ask user
            if "price" in user_inputs:
                price = user_inputs["price"]
            elif "price" in self.config["trading"] and self.config["trading"]["price"] > 0:
                price = self.config["trading"]["price"]
                rprint(f"[cyan]Using configured price: {price} {quote}[/cyan]")
            else:
                # This should never happen now, but keep as fallback
                price = current_price or 0
                rprint(f"[cyan]Using current market price: {price} {quote}[/cyan]")
            
            if sell_percentage <= 0 or sell_percentage > 100 or price <= 0:
                rprint(f"[bold red]Account {account_name}: Invalid parameters: percentage={sell_percentage}, price={price}[/bold red]")
                return None

            # Calculate quantity to sell
            quantity = available_balance * (sell_percentage / 100)
            estimated_value = quantity * price

            # Format the quantity properly to avoid scientific notation issues
            formatted_sell_quantity = int(quantity) if quantity >= 1 else self.format_quantity_for_api(quantity)

            rprint(f"\n[bold blue]Account [bold yellow]{account_name}[/bold yellow]: Placing LIMIT SELL order[/bold blue]")
            rprint(f"[bold blue]├─ Amount: {formatted_sell_quantity} {coin} ({sell_percentage}% of {formatted_balance})[/bold blue]")
            rprint(f"[bold blue]├─ Price: {price} {quote}[/bold blue]")
            rprint(f"[bold blue]└─ Estimated value: ~{self.format_quantity_for_api(estimated_value)} {quote}[/bold blue]")

            result = client.place_order(
                symbol=symbol,
                side="sell",
                orderType="limit",
                quantity=formatted_sell_quantity,
                price=price,
            )

            if result.get("code") == "00000":
                order_id = result.get("data", {}).get("orderId", "unknown")
                rprint(f"[bold green]Account {account_name}: LIMIT SELL order placed successfully, order ID: {order_id}[/bold green]")
                return order_id
            else:
                rprint(f"[bold red]Account {account_name}: Failed to place LIMIT SELL order: {result}[/bold red]")
                return None

        except Exception as e:
            rprint(f"[bold red]Account {account_name}: Error executing LIMIT SELL: {str(e)}[/bold red]")
            return None

    def execute_cancel_buy_limits(self, account_name, account_info):
        """Cancel all open buy limit orders for an account"""
        try:
            client = account_info["client"]
            symbol = self.config["trading"]["symbol"]
            
            # Get all open orders
            response = client.get_open_orders(symbol)
            
            if response.get("code") != "00000" or "data" not in response:
                rprint(f"[bold red]Account {account_name}: Failed to get open orders[/bold red]")
                return None
                
            open_orders = response["data"]
            
            # Filter buy limit orders
            buy_limit_orders = [order for order in open_orders if 
                               order.get("side") == "buy" and 
                               order.get("orderType") == "limit"]
            
            if not buy_limit_orders:
                rprint(f"[bold yellow]Account {account_name}: No open buy limit orders found[/bold yellow]")
                return True
                
            rprint(f"\n[bold blue]Account {account_name}: Found {len(buy_limit_orders)} open buy limit orders to cancel[/bold blue]")
            
            cancelled_count = 0
            failed_count = 0
            
            # Cancel each order
            for order in buy_limit_orders:
                order_id = order.get("orderId")
                price = order.get("price", "unknown")
                quantity = order.get("quantity", "unknown")
                
                rprint(f"[cyan]Cancelling buy limit order: {order_id} - {quantity} @ {price}[/cyan]")
                
                result = client.cancel_order(symbol, order_id)
                
                if result.get("code") == "00000":
                    cancelled_count += 1
                    rprint(f"[green]Successfully cancelled order {order_id}[/green]")
                else:
                    failed_count += 1
                    rprint(f"[red]Failed to cancel order {order_id}: {result.get('msg', 'Unknown error')}[/red]")
            
            rprint(f"[bold blue]Account {account_name}: Cancelled {cancelled_count} buy limit orders, {failed_count} failed[/bold blue]")
            return cancelled_count > 0
            
        except Exception as e:
            rprint(f"[bold red]Account {account_name}: Error cancelling buy limit orders: {str(e)}[/bold red]")
            return None

    def execute_cancel_sell_limits(self, account_name, account_info):
        """Cancel all open sell limit orders for an account"""
        try:
            client = account_info["client"]
            symbol = self.config["trading"]["symbol"]
            
            # Get all open orders
            response = client.get_open_orders(symbol)
            
            if response.get("code") != "00000" or "data" not in response:
                rprint(f"[bold red]Account {account_name}: Failed to get open orders[/bold red]")
                return None
                
            open_orders = response["data"]
            
            # Filter sell limit orders
            sell_limit_orders = [order for order in open_orders if 
                               order.get("side") == "sell" and 
                               order.get("orderType") == "limit"]
            
            if not sell_limit_orders:
                rprint(f"[bold yellow]Account {account_name}: No open sell limit orders found[/bold yellow]")
                return True
                
            rprint(f"\n[bold blue]Account {account_name}: Found {len(sell_limit_orders)} open sell limit orders to cancel[/bold blue]")
            
            cancelled_count = 0
            failed_count = 0
            
            # Cancel each order
            for order in sell_limit_orders:
                order_id = order.get("orderId")
                price = order.get("price", "unknown")
                quantity = order.get("quantity", "unknown")
                
                rprint(f"[cyan]Cancelling sell limit order: {order_id} - {quantity} @ {price}[/cyan]")
                
                result = client.cancel_order(symbol, order_id)
                
                if result.get("code") == "00000":
                    cancelled_count += 1
                    rprint(f"[green]Successfully cancelled order {order_id}[/green]")
                else:
                    failed_count += 1
                    rprint(f"[red]Failed to cancel order {order_id}: {result.get('msg', 'Unknown error')}[/red]")
            
            rprint(f"[bold blue]Account {account_name}: Cancelled {cancelled_count} sell limit orders, {failed_count} failed[/bold blue]")
            return cancelled_count > 0
            
        except Exception as e:
            rprint(f"[bold red]Account {account_name}: Error cancelling sell limit orders: {str(e)}[/bold red]")
            return None

    def format_quantity_for_api(self, quantity):
        """
        Format the quantity to a string that can be accepted by the Bitget API.
        Converts scientific notation (like 1.17e-05) to a properly formatted decimal string.
        """
        # Check if the quantity is too small and would be represented in scientific notation
        if isinstance(quantity, str):
            try:
                quantity = float(quantity)
            except ValueError:
                return quantity

        # Format with enough decimal places to avoid scientific notation
        if quantity < 0.0001:
            # Using format with high precision to avoid scientific notation
            formatted = "{:.7f}".format(quantity).rstrip("0").rstrip(".")
            return formatted

        # For regular numbers, convert to string with appropriate precision
        formatted = "{:.7f}".format(quantity).rstrip("0").rstrip(".")
        return formatted


def main():
    try:
        # Display fancy header
        rprint("\n[bold cyan]=====================================[/bold cyan]")
        rprint("[bold cyan]     Bitget Multi-Account Trader     [/bold cyan]")
        rprint("[bold cyan]=====================================[/bold cyan]\n")

        # Initialize trader
        trader = MultiAccountTrader()

        # Command line interface
        rprint(f"[bold green]✓ Loaded {len(trader.clients)} accounts[/bold green]")
        symbol = trader.config['trading']['symbol']
        coin = trader.config['trading']['coin']
        quote = trader.config['trading']['quote']
        rprint(f"[bold green]✓ Trading pair: {symbol} ({coin}/{quote})[/bold green]")

        while True:
            rprint("\n[bold]Available commands:[/bold]")
            rprint("[bold magenta]1.[/bold magenta] Market BUY")
            rprint("[bold magenta]2.[/bold magenta] Limit BUY")
            rprint("[bold magenta]3.[/bold magenta] Market SELL")
            rprint("[bold magenta]4.[/bold magenta] Limit SELL")
            rprint("[bold magenta]5.[/bold magenta] Cancel All BUY Limit Orders")
            rprint("[bold magenta]6.[/bold magenta] Cancel All SELL Limit Orders")
            rprint("[bold magenta]7.[/bold magenta] Exit")

            choice = input("\nEnter command (1-7): ")
            rprint("")

            if choice == "1":
                rprint("[bold]Executing Market BUY orders...[/bold]")
                results = trader.trade_all_accounts("buy_market")

            elif choice == "2":
                rprint("[bold]Executing Limit BUY orders...[/bold]")
                results = trader.trade_all_accounts("buy_limit")

            elif choice == "3":
                rprint("[bold]Executing Market SELL orders...[/bold]")
                results = trader.trade_all_accounts("sell_market")
                
            elif choice == "4":
                rprint("[bold]Executing Limit SELL orders...[/bold]")
                results = trader.trade_all_accounts("sell_limit")
                
            elif choice == "5":
                rprint("[bold]Cancelling All BUY Limit Orders...[/bold]")
                results = trader.trade_all_accounts("cancel_buy_limits")
                
            elif choice == "6":
                rprint("[bold]Cancelling All SELL Limit Orders...[/bold]")
                results = trader.trade_all_accounts("cancel_sell_limits")

            elif choice == "7":
                rprint("[bold green]Exiting...[/bold green]")
                break

            else:
                rprint("[bold red]Invalid command. Please try again.[/bold red]")

    except KeyboardInterrupt:
        rprint("\n[bold yellow]Script stopped by user[/bold yellow]")
    except Exception as e:
        rprint(f"[bold red]Script error: {str(e)}[/bold red]")
        sys.exit(1)


if __name__ == "__main__":
    main()
