"""Stock Data Visualizer - queries Alpha Vantage and charts a date range in the browser.
"""
# Import the libraries
import os
import sys
from datetime import datetime
import time
import pygal
import requests

# Store the API address and read the API key
API_URL = "https://www.alphavantage.co/query"
API_KEY = os.environ.get("ALPHAVANTAGE_API_KEY", "YOUR_API_KEY_HERE")

# let user pick a bar chart or a line chart.
CHART_TYPES = {"1": ("Bar", pygal.Bar), "2": ("Line", pygal.Line)}

# connect each menu option to the matching Alpha Vantage request.
# entries include API function, response key, and any extra request settings
TIME_SERIES = {
    "1": ("Intraday (60 min)", "TIME_SERIES_INTRADAY", "Time Series (60min)", {"interval": "60min"}),
    "2": ("Daily", "TIME_SERIES_DAILY", "Time Series (Daily)", {}),
    "3": ("Weekly", "TIME_SERIES_WEEKLY", "Weekly Time Series", {}),
    "4": ("Monthly", "TIME_SERIES_MONTHLY", "Monthly Time Series", {}),
}


# Display a numbered menu until the user enters a valid input
def prompt_choice(title, options):
    """Show a numbered menu and return the chosen entry."""
    print(f"\n{title}")
    print("-" * len(title))
    for key, value in options.items():
        print(f"{key}. {value[0]}")
    while True:
        choice = input("Enter your choice: ").strip()
        if choice in options:
            return options[choice]
        print("Invalid choice, try again.")


# Ask for a stock symbol, then make it uppercase and check that it contains letters
def prompt_symbol():
    while True:
        symbol = input("Enter the stock symbol you are looking for (e.g. IBM): ").strip().upper()
        if symbol.isalpha() and 1 <= len(symbol) <= 10:
            return symbol
        print("Please enter a valid stock symbol (letters only).")


# Ask for a date in YYYY-MM-DD format and check any date limits.
def prompt_date(message, minimum=None, maximum=None):
    """Ask for a date and reject invalid dates or dates outside the limits."""
    while True:
        text = input(message).strip()
        try:
            date = datetime.strptime(text, "%Y-%m-%d").date()
        except ValueError:
            print("Invalid format. Use YYYY-MM-DD.")
            continue
        if minimum and date < minimum:
            print("The end date cannot be before the begin date.")
            continue
        if maximum and date > maximum:
            print("The date cannot be in the future.")
            continue
        return date


# Request stock data from Alpha Vantage
def fetch_data(symbol, function, params):
    """Try full history first; fall back to compact (last ~100 points) on free keys."""
    if not API_KEY or API_KEY == "YOUR_API_KEY_HERE":
        sys.exit("Please set your ALPHAVANTAGE_API_KEY before running the program.")

    for size in ("full", "compact"):
        query = {"function": function, "symbol": symbol, "apikey": API_KEY, "outputsize": size, **params}
        try:
            response = requests.get(API_URL, params=query, timeout=30)
            response.raise_for_status()
        except requests.RequestException as err:
            # Stop message if the web request fails
            sys.exit(f"Network error: {err}")
        raw = response.json()
        message = str(raw.get("Information", "")) + str(raw.get("Note", ""))
        if size == "full" and "premium" in message.lower() and "outputsize" in message.lower():
            # Pause before trying again so requests are not sent too quickly.
            print("Full history is a premium feature; using the most recent ~100 data points instead.")
            time.sleep(1.5)
            continue
        return raw
    return raw


# Keep only rows inside the dates and arrange from oldest to newest
def filter_series(raw, series_key, start, end):
    """Return (labels, opens, highs, lows, closes) sorted oldest -> newest within the range."""
    if series_key not in raw:
        message = raw.get("Error Message") or raw.get("Note") or raw.get("Information") or "Unexpected response."
        sys.exit(f"Alpha Vantage error: {message}")

    rows = []
    for stamp, values in raw[series_key].items():
        day = datetime.strptime(stamp[:10], "%Y-%m-%d").date()  # works for intraday timestamps too
        if start <= day <= end:
            rows.append((stamp, values))
    rows.sort(key=lambda r: r[0])

    # Separate dates and prices so they can be added
    labels = [r[0] for r in rows]
    cols = [[float(r[1][f"{i}. {name}"]) for r in rows] for i, name in enumerate(["open", "high", "low", "close"], 1)]
    return (labels, *cols)


# Create a chart and add the stock's prices
def build_chart(chart_cls, symbol, series_name, start, end, data):
    labels, opens, highs, lows, closes = data
    chart = chart_cls(x_label_rotation=45, show_minor_x_labels=False, width=1100, height=600)
    chart.title = f"Stock Data for {symbol}: {start} to {end} ({series_name})"
    chart.x_labels = labels
    chart.x_labels_major = labels[:: max(1, len(labels) // 12)]
    chart.add("Open", opens)
    chart.add("High", highs)
    chart.add("Low", lows)
    chart.add("Close", closes)
    return chart


# Run program by collecting choices, getting data, and opening the finished chart
def main():
    # Ask user what stock and chart settings to use
    symbol = prompt_symbol()
    chart_name, chart_cls = prompt_choice("Chart Types", CHART_TYPES)
    series_name, function, series_key, extra = prompt_choice("Select the Time Series of the chart you want to generate", TIME_SERIES)
    today = datetime.today().date()
    start = prompt_date("Enter the begin date (YYYY-MM-DD): ", maximum=today)
    end = prompt_date("Enter the end date (YYYY-MM-DD): ", minimum=start, maximum=today)

    # Download the data and remove dates that are outside the requested range
    raw = fetch_data(symbol, function, extra)
    data = filter_series(raw, series_key, start, end)
    if not data[0]:
        sys.exit("No data found. Try a more recent date range or choose Weekly or Monthly data.")

    # Build the chart and open it in the user's browser
    chart = build_chart(chart_cls, symbol, series_name, start, end, data)
    print(f"\nGenerating {chart_name.lower()} chart with {len(data[0])} points and opening your browser...")
    chart.render_in_browser()


main()