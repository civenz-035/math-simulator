# -*- coding: utf-8 -*-
"""
lib/stake_api.py — Standalone Stake GraphQL API Connector
Architecture: Pure Python stdlib (urllib.request + http.cookiejar)
Optional accelerator: curl_cffi for Chrome TLS Impersonation
"""

from __future__ import annotations

import http.cookiejar
import json
import os
from pathlib import Path
import random
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Optional

# Optional curl_cffi for Chrome TLS impersonation
try:
    from curl_cffi import requests as cffi_requests
    HAS_CURL_CFFI = True
except ImportError:
    HAS_CURL_CFFI = False

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
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

# Stake Minimum Bet per currency (enforced by Stake Casino Engine)
STAKE_MIN_BETS: dict[str, float] = {
    "pol": 0.01,
    "matic": 0.01,
    "doge": 0.001,
    "trx": 0.0001,
    "usdt": 0.0001,
    "usdc": 0.0001,
    "btc": 0.00000001,
    "eth": 0.0000001,
    "ltc": 0.00001,
    "bch": 0.00001,
    "bnb": 0.0001,
    "xrp": 0.001,
    "sol": 0.00001,
    "eos": 0.001,
}

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
    """Finds Cloudflare cookies from known local cache locations if fresh."""
    candidates = [
        Path.cwd() / ".bypass_cache.json",
        Path(__file__).resolve().parent.parent / ".bypass_cache.json",
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
        self.user_agent = user_agent or DEFAULT_USER_AGENT

        self.cookie_jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.cookie_jar)
        )

        # Pre-seed cookies if provided explicitly
        if isinstance(cookies, dict) and "cookies" in cookies:
            host = urllib.parse.urlparse(self.base_url).hostname or "stake.bz"
            for name, val in (cookies.get("cookies") or {}).items():
                ck = http.cookiejar.Cookie(
                    version=0, name=name, value=str(val), port=None, port_specified=False,
                    domain=host, domain_specified=True, domain_initial_dot=False,
                    path="/", path_specified=True, secure=True, expires=None,
                    discard=True, comment=None, comment_url=None, rest={}, rfc2109=False,
                )
                self.cookie_jar.set_cookie(ck)

    def _request_gql(self, query: str, variables: dict | None = None) -> dict[str, Any]:
        url = f"{self.base_url}/_api/graphql"
        headers = {
            "User-Agent": self.user_agent,
            "Content-Type": "application/json",
            "x-access-token": self.api_key,
        }
        body: dict[str, Any] = {"query": query}
        if variables:
            body["variables"] = variables

        data_bytes = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(url, data=data_bytes, headers=headers)

        try:
            with self.opener.open(req, timeout=12) as resp:
                status_code = resp.status
                raw_text = resp.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="replace") if e.fp else ""
            if e.code in (401, 403):
                raise StakeAuthError(
                    f"Stake rejection ({e.code}). Please verify your STAKE_API_KEY or connection."
                ) from e
            raise StakeAPIError(f"HTTP Error {e.code} from Stake API: {err_body[:200]}") from e
        except Exception as e:
            raise StakeAPIError(f"Network error connecting to {url}: {e}") from e

        if "<!doctype html>" in raw_text[:200].lower():
            raise StakeAuthError("Cloudflare challenge page received. WAF clearance required.")

        try:
            data = json.loads(raw_text)
        except Exception as e:
            raise StakeAPIError(f"Invalid JSON response from Stake API: {raw_text[:200]}") from e

        if "errors" in data and data["errors"]:
            msg = data["errors"][0].get("message", "Unknown GraphQL error")
            raise StakeBetError(f"Stake API GraphQL error: {msg}")

        return data

    def test_connection(self) -> tuple[bool, str, float]:
        """Tests API connectivity and measures response latency (seconds)."""
        t0 = time.time()
        try:
            data = self._request_gql(BALANCE_QUERY)
            lat = time.time() - t0
            user = (data.get("data") or {}).get("user") or {}
            user_id = user.get("id") or "OK"
            return True, f"Connected (User ID: {user_id})", lat
        except Exception as e:
            lat = time.time() - t0
            return False, str(e), lat

    def get_account_info(self) -> dict[str, Any]:
        """Returns comprehensive account info including all non-zero balances."""
        data = self._request_gql(BALANCE_QUERY)
        user = (data.get("data") or {}).get("user") or {}
        raw_bals = user.get("balances") or []
        bal_dict: dict[str, float] = {}
        for item in raw_bals:
            if isinstance(item, dict):
                avail = item.get("available") or item
                c = avail.get("currency", "").lower()
                amt = float(avail.get("amount", 0.0) or 0.0)
                if c:
                    bal_dict[c] = amt
        return {
            "id": user.get("id", ""),
            "name": user.get("name") or "Stake User",
            "balances": bal_dict,
        }

    def get_balances(self) -> dict[str, float]:
        """Returns dict of {currency: available_amount}."""
        return self.get_account_info()["balances"]

    @staticmethod
    def get_currency_min_bet(currency: str) -> float:
        """Returns Stake Casino minimum allowed bet for currency."""
        return STAKE_MIN_BETS.get(currency.lower(), 0.0001)

    def get_currency_balance(self, currency: str) -> float:
        """Returns available balance for specific currency (e.g. 'trx', 'usdt', 'pol')."""
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
            currency: Crypto symbol ('trx', 'pol', 'usdt', 'btc', 'ltc', etc.)
            
        Returns:
            dict containing:
                roll_val (float): Roll result 0.00-99.99
                won (bool): True if win, False if lose
                round_pnl (float): Net profit/loss of this round
                payout (float): Total payout returned
                balance (float): Updated account balance
                bet_id (str): Stake Bet ID
        """
        # Auto-clamp to Stake minimum bet per currency to prevent 'Amount too small'
        min_allowed = self.get_currency_min_bet(currency)
        actual_amount = max(float(amount), min_allowed)

        target = 100.0 - float(chance) if high else float(chance)
        variables = {
            "amount": actual_amount,
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
        pnl = payout_amt - actual_amount
        won = pnl > 0.0

        # Updated balance from user profile in response
        user = dice_roll.get("user") or {}
        raw_bals = user.get("balances") or []
        new_bal: float = 0.0
        for item in raw_bals:
            if isinstance(item, dict):
                avail = item.get("available") or item
                if avail.get("currency", "").lower() == currency.lower():
                    new_bal = float(avail.get("amount", 0.0) or 0.0)
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
