# Pythonbot
Python trading bot
# Automated Trading Strategy in MetaTrader 5

This repository contains a Python script designed to automate trading in MetaTrader 5 (MT5) using strategies based on technical signals, market analysis, and risk management. It includes functionalities to open and close trades and manage the connection with MetaTrader 5.

---

## Key Features

- **Order execution** based on buy/sell signals using market book data and customizable slippage.
- **Trade management** with dynamic stop loss (SL) and take profit (TP).
- **Automatic trade closing** when certain technical conditions (e.g., RSI levels) are met.
- **Daily loss management**: the script halts trading if a configurable daily loss threshold is reached.
- **Automated scheduling** of trades using `apscheduler`, aligned with market session times.

---

## Requirements

- **Python 3.8 or higher**
- **MetaTrader 5 installed** and access to an active trading account.
- Required Python libraries (install using `pip`):
  ```bash
  pip install -r requirements.txt

Contents of requirements.txt:

MetaTrader5
apscheduler
numpy
pandas
pytz
logging
traceback

Initial Setup
1. Connect to MetaTrader 5

    Before running the script, ensure that your MetaTrader 5 account is properly configured.
    Set up the symbols to trade in the configuration file symbol_config.

2. Configuration File (symbol_config)

The configuration file defines specific parameters for each trading symbol. Customize the following parameters:

symbol_config = {
    "EURUSD": {
        "max_spread": 0.00015,
        "TPSLRatio_coef": 1.5,
        "rsi_overbought": 70,
        "rsi_oversold": 30
    },
    "AUDNZD": {
        "max_spread": 0.00020,
        "TPSLRatio_coef": 2.0,
        "rsi_overbought": 75,
        "rsi_oversold": 25
    },
    # Add other symbols as needed
}

3. Scheduler Configuration

The script uses apscheduler to schedule trades based on market hours. Trades are executed:

    Sunday to Friday, at minute intervals defined in the code.
    Friday 21:30: All open positions are closed.

Running the Script
Step 1: Clone the Repository

Clone this repository to your local machine:

git clone [https://github.com/yourusername/repository-name.git](https://github.com/Zero1140/Pythonbot/)

Step 2: Run the Main Script

Once the environment and dependencies are set up, run the main script:

python main.py

Repository Structure

📂 repository-name
├── main.py                # Main script
├── requirements.txt       # Python dependencies
├── symbol_config.py       # Symbol-specific configuration
├── utils.py               # Utility functions (calculations, logs, etc.)
├── logs/                  # Folder for operation logs
│   ├── trading_log.txt
│   ├── error_log.txt
├── README.md              # Repository documentation

Script Workflow Explanation

    Initialization:
        Connects to MetaTrader 5.
        Checks account status.

    Trading Cycle:
        Fetches OHLC data and technical signals.
        Calculates key parameters like position size, stop loss, and take profit.
        Executes trades if conditions are met.
        Closes positions based on RSI or predefined thresholds.

    Risk Management:
        Monitors daily losses and halts trading if the threshold is reached.

    Position Closing:
        Automatically closes all open positions at the end of Friday's trading session.

Log Files

The system records important information for analysis in the following files:

    trading_log.txt: General information about executed trades.
    error_log.txt: Errors captured during the trading process.

How to Contribute

If you'd like to contribute to this project:

    Fork the repository.
    Create a branch for your changes:

    git checkout -b feature/new-feature

    Submit a pull request once your changes are ready.

Disclaimers

    Use at your own risk: This script is intended for educational purposes only and does not guarantee profitability.
    Test on a demo account: Always test the system on a demo account before using it on a live account.





<!-- 
This "configmt5.json" file is part of a larger trading bot project and contains essential settings. 
Below is a quick guide to help you adapt it to your own account and setup:

1. **symbol_config**: 
   - Holds the parameters for each currency pair (e.g., EURUSD, AUDNZD, USDCAD).
   - Common fields:
     - **strategy**: the trading strategy (e.g., "rsi_bollinger", "vwap_bollinger").
     - **slatrcoef**: a factor used to calculate the Stop Loss based on the ATR.
     - **TPSLRatio_coef**: the ratio between Take Profit and Stop Loss.
     - **risk_perc**: the percentage of your account balance to risk on each trade.
     - **max_spread**: the maximum allowed spread before entering a trade.
     - **rsi_length**, **rsi_overbought**, **rsi_oversold**: RSI-specific parameters.
     - **bb_length**, **bb_std**: Bollinger Bands parameters.
     - Other fields may appear depending on the strategy.

2. **timeframe**:
   - Specifies the chart timeframe to be used (e.g., mt5.TIMEFRAME_M5 for 5-minute candles).

3. **creds**:
   - Contains your MetaTrader 5 login details. You should replace these with your own:
     - **path**: path to your local MetaTrader 5 installation 
       (e.g., "C:/Program Files/MetaTrader 5/terminal64.exe").
     - **server**: the broker server name (e.g., "Darwinex-Demo").
     - **pass**: your MetaTrader 5 account password.
     - **login**: your MetaTrader 5 account login number.
     - **timeout**: the time (in milliseconds) the script waits for responses.
     - **portable**: set to `false` if MT5 was installed traditionally, or `true` if running in portable mode.

By editing these sections, you ensure:
- The bot connects to your correct account using your credentials.
- Each currency pair uses the right strategy settings.
- Risk and spread thresholds are enforced as per your preferences.

After customizing your details, save and commit your changes to the repository so the bot can run with your desired configuration!
-->

