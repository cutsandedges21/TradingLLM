# Learn to Trade — From Zero to Your First Trade

This guide assumes you know **nothing** about trading. Read it top to bottom and
you'll understand what trading is, how markets work, the words people use, how to
read a chart, how to manage risk, and how to place your first (pretend-money)
trade inside this app. Take your time — there's no rush, and the practice account
uses fake money on purpose.

> **Important, read this first:** Trading involves real risk of losing money.
> Nothing in this app or guide is financial advice. The assistant can be wrong,
> data can be delayed, and markets can do anything. Start with **paper trading**
> (simulated money), learn the ropes, and never risk money you can't afford to
> lose.

---

## 1. What is trading, really?

A **market** is just a place where buyers and sellers meet to agree on a price.
A **stock** (also called a **share** or **equity**) is a tiny slice of ownership
in a company. If a company has 1 billion shares and you own 1, you own one-billionth
of that company. When you "trade," you're buying and selling these slices (or other
assets like crypto) hoping to buy lower and sell higher.

- **Investing** = buying and holding for months or years, betting a company or asset
  grows over time.
- **Trading** = buying and selling more actively (minutes to weeks), trying to profit
  from shorter price moves.

Both are on the same spectrum. This app supports both styles — you decide.

**Why do prices move?** Supply and demand. If more people want to buy than sell, the
price rises; if more want to sell, it falls. What makes people want to buy or sell?
Company earnings, news, the economy, interest rates, emotions (fear and greed), and
sometimes nothing logical at all. Nobody can predict prices reliably — anyone who
promises they can is lying.

---

## 2. The things you can trade

- **Stocks / shares** — ownership in one company (e.g., AAPL = Apple, NVDA = Nvidia).
- **ETFs (Exchange-Traded Funds)** — a single ticker that holds a basket of many
  stocks. Buying **SPY** gives you a slice of the 500 biggest U.S. companies at once.
  ETFs are popular with beginners because they spread risk automatically.
- **Crypto** — digital assets like Bitcoin (**BTC/USD**) or Ethereum (**ETH/USD**).
  Trades 24/7, very volatile.
- **Options** — advanced contracts that bet on price moving by a date. Powerful but
  risky and confusing. **Skip these until you're experienced.** (This app focuses on
  stocks, ETFs, and crypto.)

A **ticker** (or **symbol**) is the short code for an asset: Apple = `AAPL`,
Tesla = `TSLA`, the S&P 500 ETF = `SPY`, Bitcoin = `BTC/USD`.

---

## 3. The words you'll hear (plain-English glossary)

- **Bid** — the highest price a buyer will currently pay.
- **Ask (or offer)** — the lowest price a seller will currently accept.
- **Spread** — the gap between bid and ask. Tight spread = easy to trade; wide spread = costlier.
- **Volume** — how many shares traded. High volume = lots of interest/liquidity.
- **Liquidity** — how easily you can buy/sell without moving the price. Big stocks = very liquid.
- **Market cap** — total value of a company (share price × number of shares).
- **Position** — an asset you currently own (or owe). "I have a position in NVDA."
- **Long** — you bought, betting the price goes **up** (the normal way).
- **Short** — you borrowed and sold, betting the price goes **down**. Advanced; risky.
- **Portfolio** — everything you hold together.
- **Equity** — the total value of your account.
- **Buying power** — how much you can currently spend.
- **P/L (Profit/Loss)** — how much you're up or down. **Unrealized** = on paper
  (still holding). **Realized** = locked in after you sell.
- **Volatility** — how wildly a price swings. High volatility = bigger risk and reward.
- **Bull / bullish** — expecting prices to rise. **Bear / bearish** — expecting a fall.
- **Dividend** — a cash payment some companies pay shareholders periodically.

---

## 4. How orders work (this is the actual "how to trade" part)

To buy or sell, you send an **order** to the market. The main types:

- **Market order** — "Buy/sell right now at the best available price." Fast, but you
  don't control the exact price. Best for liquid assets when you just want in or out.
- **Limit order** — "Only buy at $100 or lower" / "only sell at $120 or higher." You
  control the price, but it might never fill if the market doesn't reach it.
- **Stop order (stop-loss)** — "If price drops to $95, sell me out." This is your
  safety net to cap losses. **Use these.**
- **Stop-limit** — a stop that turns into a limit order. More control, more ways to miss.

**Time in force** tells the order how long to stay active:
- **DAY** — cancels at end of the trading day if unfilled.
- **GTC (Good 'Til Canceled)** — stays active until it fills or you cancel.

**Position sizing** = how much you buy. You can specify:
- **Quantity** — a number of shares/coins ("buy 5 shares of AAPL"), or
- **Notional** — a dollar amount ("put $500 into AAPL"), which buys fractional shares.

When the U.S. stock market is open (roughly 9:30am–4:00pm Eastern, Mon–Fri), orders
fill quickly. Crypto trades 24/7.

---

## 5. Reading a price chart

A chart shows price over time. The most common style is **candlesticks**. Each candle
covers one time slice (a day, an hour, etc.) and shows four prices:

- **Open** — price at the start of the slice.
- **Close** — price at the end.
- **High** / **Low** — the extremes during the slice.

A **green/up candle** means it closed higher than it opened; **red/down** means lower.
The thin lines (**wicks**) show the highs and lows; the thick part (**body**) shows
open-to-close.

Key things to look for:
- **Trend** — is price generally rising (uptrend), falling (downtrend), or flat
  (sideways/ranging)? "The trend is your friend" — trading with the trend is easier.
- **Support** — a price floor where buyers repeatedly step in.
- **Resistance** — a price ceiling where sellers repeatedly appear.
- **Timeframe** — the same asset looks different on a 5-minute vs daily chart. Zoom out
  to see the big picture; zoom in to time an entry.

---

## 6. Indicators (the math hints this app computes for you)

Indicators are formulas applied to price. They **hint**, they don't predict. This app
shows a few of the most common ones:

- **Moving Average (SMA/EMA)** — the average price over the last N periods, drawn as a
  smooth line. Price above a rising average = uptrend; below a falling one = downtrend.
  This app shows **SMA20** (20-day) and **SMA50** (50-day).
- **RSI (Relative Strength Index, 0–100)** — momentum gauge. Above ~70 = "overbought"
  (ran up fast, may cool off); below ~30 = "oversold" (fell fast, may bounce). It's a
  hint, not a command — strong trends can stay overbought for a long time.
- **MACD** — compares two moving averages to show whether momentum is building up
  (bullish) or fading (bearish).

The app turns these into a plain summary like:
`NVDA $120.50  +1.2%  RSI 58 (neutral)  trend up  MACD bullish`.

---

## 7. Two ways people decide what to trade

- **Fundamental analysis** — studying the *business*: earnings, revenue growth, debt,
  industry, management. "Is this a good company at a fair price?" Better for long-term
  investing.
- **Technical analysis** — studying the *chart and indicators* to time entries and
  exits. Better for shorter-term trading.

Most good traders blend both. Ask the assistant to do either: "What are NVDA's
fundamentals?" or "Is AAPL technically overbought right now?"

---

## 8. Trading styles — pick one that fits your life

- **Long-term investing** — buy quality, hold for years. Lowest stress, lowest effort.
  Great default for beginners (especially broad ETFs like SPY).
- **Swing trading** — hold days to weeks to catch a "swing" in price. A few decisions
  per week.
- **Day trading** — open and close within the same day. Intense, full-time, and most
  beginners lose money at it. Don't start here.

There's no prize for trading more often. Less is often more.

---

## 9. Risk management — the part that actually keeps you in the game

Professionals obsess over risk, not profit. The goal is to **survive long enough to
learn**. Rules that matter:

- **Only risk money you can afford to lose.** Never rent money, never debt.
- **Position sizing / the 1–2% rule** — don't risk more than 1–2% of your account on a
  single trade. On a $1,000 account, that's $10–$20 of *potential loss* per trade.
- **Always know your exit before you enter.** Decide your **stop-loss** (where you'll
  admit you're wrong) *before* buying.
- **Risk/reward ratio** — aim for trades where the potential gain is at least ~2× the
  potential loss. If you risk $50 to make $100, you can be right less than half the
  time and still come out ahead.
- **Diversify** — don't put everything in one stock. ETFs do this for you.
- **Cut losses, let winners run** — the opposite of what emotions tell you to do.

A simple example: you buy 10 shares of a $100 stock ($1,000). You set a stop-loss at
$95. Your risk is $5 × 10 = $50. You target $110, a $100 gain. That's a 2:1
reward-to-risk trade with a defined, survivable loss.

---

## 10. Trading psychology

Most losses come from emotions, not bad analysis:

- **FOMO (Fear Of Missing Out)** — chasing something that already shot up. Usually
  you're buying right before it cools off.
- **Revenge trading** — trying to instantly win back a loss. It compounds losses.
- **Holding losers, selling winners** — hoping a loss "comes back" while cutting gains
  short. Flip this habit.
- **Have a plan and follow it.** Decide entry, stop, and target *before* you click.
  Boring discipline beats exciting gambling.

---

## 11. Paper trading first (what this app does by default)

**Paper trading** means placing trades with **simulated money** — same prices and
mechanics, zero financial risk. It's how you learn without paying tuition to the
market. This app has a built-in **$100,000 mock account** by default — no brokerage
signup needed. Do this for weeks or months. Track your results. Only consider real
money once you're consistently *not* blowing up the fake account.

---

## 12. Your first trade, step by step (in this app)

1. **Open the 💬 Chat tab.** On the right you'll see your paper account, positions,
   and watchlist with live-ish prices.
2. **Ask a question.** Type something like: *"How does SPY look today, and is it a
   reasonable swing-trade entry?"* The assistant pulls live data and explains.
3. **Learn the reasoning.** It will mention trend, RSI, and risk. Ask follow-ups:
   *"Where would a sensible stop-loss go?"* or *"Explain why RSI matters here."*
4. **Ask for an action.** Say: *"Set up a small paper buy of SPY, about $200."* The
   assistant proposes a trade as a structured block.
5. **Confirm.** A pop-up shows the exact order (buy/sell, symbol, size, est. cost,
   reason). **Nothing happens unless you click Yes.** This is your safety gate.
6. **Review.** The order appears in your positions, and it's saved to the assistant's
   journal so it remembers what you did and why.
7. **Follow up over time.** Days later, ask *"How is my SPY position doing and should I
   take profit?"* It remembers the trade and reasons about your actual position.

---

## 13. Common beginner mistakes (learn these cheaply, here)

- Going all-in on one "sure thing." (Nothing is sure.)
- No stop-loss, then "hoping" a falling trade recovers.
- Over-trading and racking up tiny losses.
- Trading on social-media hype.
- Confusing a bull market for personal skill.
- Risking real money before mastering the paper account.

---

## 14. Fees, taxes, and the boring fine print

- **Commissions** — many brokers (including Alpaca) charge $0 commission on U.S. stocks,
  but spreads and small fees still exist.
- **Taxes** — in most countries, **realized** profits are taxable. Short-term gains
  (held < 1 year, in the U.S.) are usually taxed higher than long-term. Keep records;
  this app's journal helps. Talk to a tax professional for your situation.
- **Pattern Day Trader (PDT) rule** — in the U.S., accounts under $25,000 are limited
  to a few day trades per week. Another reason swing/long-term is friendlier to start.

---

## 15. A 30-second cheat sheet

- Buy = bet it goes up. Sell = exit (or bet it goes down, if shorting).
- Market order = now. Limit order = my price. Stop = my safety exit.
- Trend up + price above moving averages = healthier long setups.
- RSI > 70 overbought, < 30 oversold — *hints*, not commands.
- Risk 1–2% per trade. Always set a stop. Aim for 2:1 reward/risk.
- Paper trade first. Have a plan. Cut losses, let winners run.
- The assistant can be wrong. Data can lag. You make the final call.

---

## 16. Where to learn more

- **Investopedia** (investopedia.com) — free, beginner-friendly definitions for every
  term in this guide.
- **Finnhub** (finnhub.io) & **Yahoo Finance** — the free live-data sources this app uses.
- **Your own journal** — the most valuable resource. Review your paper trades and ask
  the assistant *"what patterns do you see in my past trades?"*

Welcome to trading. Go slow, stay curious, protect your money, and let the paper
account teach you before the real one ever can.
