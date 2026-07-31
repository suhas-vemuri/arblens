"""Test the ArbLens connection to Tradier."""

from tradier_client import TradierClient, TradierError


def main() -> None:
    try:
        client = TradierClient()

        print("Testing Tradier authentication...")

        if not client.test_authentication():
            print("Authentication failed.")
            return

        print("Authentication successful.")

        print("\nDownloading AAPL quote...")
        quotes = client.get_quotes("AAPL")

        if not quotes:
            print("No quote was returned.")
            return

        quote = quotes[0]

        print("Quote successful.")
        print("Symbol:", quote.get("symbol"))
        print("Bid:", quote.get("bid"))
        print("Ask:", quote.get("ask"))
        print("Last:", quote.get("last"))

        print("\nDownloading AAPL option expirations...")
        expirations = client.get_option_expirations("AAPL")

        if not expirations:
            print("No option expirations were returned.")
            return

        print("Expiration request successful.")
        print("Expirations found:", len(expirations))
        print("First expiration:", expirations[0])

        print("\nDownloading the first AAPL option chain...")
        contracts = client.get_option_chain(
            symbol="AAPL",
            expiration=expirations[0],
            include_greeks=True,
        )

        print("Option-chain request successful.")
        print("Contracts returned:", len(contracts))

        if contracts:
            first_contract = contracts[0]

            print("Example contract:", first_contract.get("symbol"))
            print("Strike:", first_contract.get("strike"))
            print("Type:", first_contract.get("option_type"))
            print("Bid:", first_contract.get("bid"))
            print("Ask:", first_contract.get("ask"))
            print(
                "Greeks returned:",
                bool(first_contract.get("greeks")),
            )

        print("\nTradier is connected to ArbLens.")

    except TradierError as exc:
        print("\nTradier connection failed:")
        print(exc)

    except Exception as exc:
        print("\nUnexpected error:")
        print(f"{type(exc).__name__}: {exc}")


if __name__ == "__main__":
    main()