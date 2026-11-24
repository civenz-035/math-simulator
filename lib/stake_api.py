# -*- coding: utf-8 -*-
"""
lib/stake_api.py — Standalone Stake GraphQL API Connector
Architecture: Pure Python Client with Cloudflare TLS & Cookie support
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import random
import time
import urllib.parse
from typing import Any, Optional

# Try curl_cffi for Chrome TLS impersonation (bypasses Cloudflare JA3/TLS fingerprint)
try:
    from curl_cffi import requests as cffi_requests
    HAS_CURL_CFFI = True
except ImportError:
    HAS_CURL_CFFI = False
    import requests as std_requests

# GraphQL Queries & Mutations (exact Gambler.Bot / Stake upstream schema)
LOGIN_QUERY = (
    "query DiceBotLogin{user {activeServerSeed { seedHash seed nonce} "
    "activeClientSeed{seed} id balances{available{currency amount}} "
    "statistic {game bets wins losses betAmount profit currency}}}"
)

BALANCE_QUERY = (
    "query DiceBotGetBalance{user { activeServerSeed { seedHash seed nonce } "
    "activeClientSeed { seed } id balances { available { currency amount } } } }"
)

DICE_MUTATION = (
    "mutation DiceRoll($amount: Float! \r\n"
    "  $target: Float!\r\n"
    "  $condition: CasinoGameDiceConditionEnum!\r\n"
    "  $currency: CurrencyEnum!\r\n"
    "  $identifier: String!){ diceRoll(amount: $amount, target: $target, "
    "condition: $condition, currency: $currency, identifier: $identifier) { "
    "id payoutMultiplier amountMultiplier nonce currency amount payout state { "
    "... on CasinoGameDice { result target condition } } createdAt "
    "serverSeed{seedHash seed nonce} clientSeed{seed} "
    "user{balances{available{currency amount}} statistic{game bets wins losses "
    "betAmount profit currency}}}}"
)

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0"
)

class StakeAPIError(Exception):
    """General Stake API error."""

class StakeAuthError(StakeAPIError):
    """Authentication or Cloudflare 403 error."""

class StakeBetError(StakeAPIError):
    """Bet placement error (insufficient funds, invalid bet, etc.)."""
    def __init__(self, message: str = "", error_type: str = "Unknown"):
        super().__init__(message)
        self.error_type = error_type


def find_cached_cookies() -> dict[str, Any] | None:
    """Finds Cloudflare cookies from known cache locations."""
    candidates = [
        Path.cwd() / ".bypass_cache.json",
        Path(__file__).resolve().parent.parent / ".bypass_cache.json",
        Path(r"C:\Users\User\Desktop\stakebot\.bypass_cache.json"),
    ]
    for p in candidates:
        if p.is_file():
            try:
                with open(p, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict) and "cookies" in data:
                        return data
            except Exception:
                pass
    return None


class StakeClient:
    """
    Direct Stake.com GraphQL API Client.
    Connects, reads real balance, and places dice bets natively.
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://stake.bz",
        cookies: Optional[dict[str, Any]] = None,
        user_agent: Optional[str] = None,
    ):
        self.api_key = api_key.strip()
        self.base_url = base_url.rstrip("/")

        if HAS_CURL_CFFI:
            self.session = cffi_requests.Session(impersonate="chrome")
        else:
            self.session = std_requests.Session()

        # Load cookies
        if not cookies:
            cookies = find_cached_cookies()

        self.user_agent = user_agent or DEFAULT_USER_AGENT
        if isinstance(cookies, dict):
            if cookies.get("user_agent"):
                self.user_agent = cookies["user_agent"]
            host = urllib.parse.urlparse(self.base_url).hostname
            for name, val in (cookies.get("cookies") or {}).items():
                if host:
                    self.session.cookies.set(name, str(val), domain=host)
                else:
                    self.session.cookies.set(name, str(val))

    def _request_gql(self, query: str, variables: dict | None = None) -> dict[str, Any]:
        url = f"{self.base_url}/_api/graphql"
        headers = {
            "x-access-token": self.api_key,
            "content-type": "application/json",
            "user-agent": self.user_agent,
            "origin": self.base_url,
            "referer": f"{self.base_url}/casino/games/dice",
        }
        body: dict[str, Any] = {"query": query}
        if variables:
            body["variables"] = variables

        try:
            r = self.session.post(url, json=body, headers=headers, timeout=12)
        except Exception as e:
            raise StakeAPIError(f"Network error connecting to {url}: {e}") from e

        if r.status_code in (401, 403) or "<!DOCTYPE html>" in r.text[:200].lower():
            raise StakeAuthError(
                f"Cloudflare or Auth rejection ({r.status_code}). Check API Key or update Cloudflare cookies."
            )

        try:
            data = r.json()
        except Exception as e:
            raise StakeAPIError(f"Invalid JSON response from Stake API: {r.text[:200]}") from e

        if "errors" in data and data["errors"]:
            msg = data["errors"][0].get("message", "Unknown GraphQL error")
            raise StakeBetError(f"Stake API GraphQL error: {msg}")

        return data

    def get_balances(self) -> dict[str, float]:
        """Returns dict of {currency: available_amount}."""
        data = self._request_gql(BALANCE_QUERY)
        user = (data.get("data") or {}).get("user") or {}
        balances = (user.get("balances") or {}).get("available") or []
        res: dict[str, float] = {}
        for b in balances:
            c = b.get("currency", "").lower()
            amt = float(b.get("amount", 0.0) or 0.0)
            if c:
                res[c] = amt
        return res

    def get_currency_balance(self, currency: str) -> float:
        """Returns available balance for specific currency (e.g. 'trx', 'usdt')."""
        balances = self.get_balances()
        return balances.get(currency.lower(), 0.0)

    def place_dice_bet(
        self,
        amount: float,
        chance: float,
        high: bool,
        currency: str = "trx",
    ) -> dict[str, Any]:
        """
        Places a real dice bet on Stake.
        
        Args:
            amount: Bet amount in crypto
            chance: Win chance in percent (0.01 to 98.0)
            high: True = Roll Over, False = Roll Under
            currency: Crypto symbol ('trx', 'usdt', 'btc', 'ltc', etc.)
            
        Returns:
            dict containing:
                roll_val (float): Roll result 0.00-99.99
                won (bool): True if win, False if lose
                round_pnl (float): Net profit/loss of this round
                payout (float): Total payout returned
                balance (float): Updated account balance
                bet_id (str): Stake Bet ID
        """
        # In Stake Dice:
        # High=True  -> Roll Over  (Target = 100 - chance, condition = 'above')
        # High=False -> Roll Under (Target = chance, condition = 'below')
        target = 100.0 - float(chance) if high else float(chance)
        variables = {
            "amount": float(amount),
            "target": round(float(target), 4),
            "condition": "above" if high else "below",
            "currency": str(currency).lower(),
            "identifier": str(random.randint(1, 10**9)),
        }

        data = self._request_gql(DICE_MUTATION, variables)
        dice_roll = (data.get("data") or {}).get("diceRoll") or {}
        state = dice_roll.get("state") or {}

        roll_val = float(state.get("result", 0.0) or 0.0)
        payout_amt = float(dice_roll.get("payout", 0.0) or 0.0)
        pnl = payout_amt - float(amount)
        won = pnl > 0.0

        # Updated balance from user profile in response
        user = dice_roll.get("user") or {}
        new_bal: float = 0.0
        for b in (user.get("balances") or {}).get("available") or []:
            if b.get("currency", "").lower() == currency.lower():
                new_bal = float(b.get("amount", 0.0) or 0.0)
                break

        return {
            "roll_val": roll_val,
            "won": won,
            "round_pnl": pnl,
            "payout": payout_amt,
            "balance": new_bal,
            "bet_id": dice_roll.get("id", ""),
            "nonce": dice_roll.get("nonce", 0),
        }
