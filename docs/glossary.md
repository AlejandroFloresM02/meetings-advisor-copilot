# Financial Glossary — Grounded Brief (V2)

Plain-English reference for the institutional asset-management vocabulary used across the V2 grounded-brief project. Each term gives the meaning and, where it maps to code, the model field/module in parentheses (e.g. *`CGMandate.fee_bps`*).

> Scope: the **client** is a real public **asset owner** (pension/endowment); the **user** is a Capital Group **relationship manager** selling/servicing investment **mandates**. Terms here drive the data model (spec §5), the analytics layer (spec §6) and the brief content (spec §9).

---

## 1. The relationship & the players

- **Relationship Manager (RM)** — *our user.* The Capital Group salesperson/account owner the brief is generated *for*. *(`RelationshipMeta.rm`)*
- **Asset owner / institutional client** — the institution that *owns* the money (e.g. CalPERS). The meeting is *with* them.
- **Mandate** — a specific pot of the client's money that Capital Group runs in one strategy (e.g. "a $600mm Core Plus mandate"). Winning, keeping, and growing mandates is the core business. *(`CGMandate`)*
- **Strategy** — the investment product/approach a mandate is run in (e.g. "Core Plus Income"). *(`CGMandate.strategy`)*
- **Vehicle** — the legal wrapper a mandate lives in:
  - **SMA (Separate Account)** — the client owns the underlying securities directly; most customizable; common for large institutions.
  - **Commingled fund** — many clients pooled into one fund.
  - **CIT (Collective Investment Trust)** — a pooled vehicle for retirement plans (often cheaper than a mutual fund).
  - **Mutual fund** — registered, retail-accessible pooled fund.
  *(`CGMandate.vehicle`)*
- **AUM (Assets Under Management)** — the size of money managed. **AUM with CG** = how much of the client's money Capital Group runs.
- **Tier** — how strategic a relationship is (Strategic / Core / Developing). *(`RelationshipMeta.tier`)*
- **Consultant** — the gatekeeper advisor (Mercer, Aon, NEPC, RVK, Callan…) the client hires to vet and monitor managers. Capital Group frequently has to win the *consultant*, not just the client. *(`RelationshipMeta.consultant`)*
- **Pipeline / Opportunity** — a potential new or expanded mandate. *(`Opportunity`)*
  - **Stage** — where it sits in the procurement funnel: Prospecting → Qualification → **RFP** (Request for Proposal) → **Finals** (the finalist presentation) → **Due Diligence** → Won/Lost.
  - **Probability** — likelihood of winning (0–1). **Probability-weighted value** = mandate size × probability.
  - **Search / Notice of Search** — the client formally shopping for a manager in an asset class (a buying signal). *(`InvestmentAction.kind = "search"`)*

## 2. The client institution (the asset owner)

- **Public pension** — a retirement plan for public employees; *owes* defined benefits to retirees. **Endowment** — a permanent fund (e.g. a university's) meant to support spending forever.
- **Funded ratio** — plan assets ÷ the present value of what it owes (liabilities). Below 100% = **underfunded**. *Our CalPERS sample = 0.75 → 75¢ of assets per $1 of pension promises = funding pressure.* *(`Institution.funded_ratio`)*
- **Assumed return / discount rate** — the long-term annual return the plan *assumes*, used to value its liabilities (e.g. 6.8%). A consequential, politically-charged number: a *lower* assumed rate is more conservative and makes liabilities look *bigger*. *(`Institution.assumed_return`)*
- **Actuarial value vs market value** — actuaries often use a *smoothed* asset value (to dampen market swings) alongside the current *market* value.
- **Surplus / deficit** — assets minus liabilities (positive = surplus, negative = deficit).
- **Strategic Asset Allocation (SAA)** — the long-term **target mix** across asset classes (e.g. 42% equity / 30% fixed income / 13% private equity / …). The single most important decision an asset owner makes; everything else serves it. *(`Institution.allocation`: target vs actual per class)*
- **Rebalancing / rebalancing bands** — keeping actual allocation near target; bands are the tolerance ranges before they trade back.
- **Policy benchmark** — a blended index built from the SAA weights; the bar the **total fund** is measured against. *(`Institution.policy_benchmark`)*
- **Asset classes** — the buckets: public equity, **fixed income** (bonds), **private equity**, **private credit**, real assets/real estate, etc. *(`AllocationSlice.asset_class`)*
- **Liability-Driven Investing (LDI)** — managing assets specifically to track the liabilities (common for corporate pensions and insurers).
- **Liquidity** — how quickly assets can be turned into cash without loss; pensions must keep enough liquid to pay benefits.
- **In-house vs external management** — money the institution runs itself vs money given to outside managers (like CG). The "external" slice is CG's addressable market.

## 3. Performance & skill — how a manager is judged (kept or fired)

- **Benchmark** — the index a strategy is measured against (e.g. **Bloomberg US Aggregate** for core bonds; **MSCI ACWI** for global equity). *(`CGMandate.benchmark`)*
- **Gross vs net return** — before vs after fees. Institutions judge on **net**.
- **Excess return / alpha** — return *above* the benchmark. **Net-of-fee excess** = excess after fees — the number that actually matters. *Our mandate: +62 bps.* *(`CGMandate.net_excess_bps`)*
- **Tracking error** — the volatility of the excess return — how far the strategy strays from its benchmark. Low = index-hugging; high = bold active bets.
- **Information Ratio (IR)** — excess return ÷ tracking error. "Skill per unit of active risk." Higher is better; ~0.5 is good, **0.71** (our mandate) is strong. *(`CGMandate.information_ratio`)*
- **Up-capture / down-capture** — in *rising* markets, the % of the market's gain you capture; in *falling* markets, the % of the loss you take. *Down-capture **0.83** = you fall only 83% as much as the market in a selloff — prized downside protection for risk-averse pensions.* *(`CGMandate.down_capture`)*
- **Active share** — the % of a portfolio that differs from its benchmark. High = genuinely active management (Capital Group's pitch); low = "**closet indexing**" (charging active fees for index-like holdings).
- **Sharpe ratio** — return per unit of *total* risk (above the risk-free rate). **Sortino ratio** — like Sharpe but only penalizes *downside* volatility.
- **Batting average** — the % of periods a manager beats its benchmark (consistency).
- **Beta** — sensitivity to the market (1.0 = moves one-for-one; 0.8 = 80% as much).
- **Drawdown / max drawdown** — a peak-to-trough loss; the worst is the *maximum* drawdown.
- **Performance attribution** — decomposing returns into *where they came from*: **allocation effect** (asset-class bets) vs **selection effect** (security picks), plus sector/duration contributions. The "story" behind the numbers.
- **Peer universe / percentile ranking** — ranking a manager against comparable managers (e.g. via the **eVestment** database); "top-quartile" = top 25%.

## 4. Fixed income (Capital Group's core strength)

- **Duration** — price sensitivity to interest rates, expressed in ~years. *Effective duration 5.9 → a 1% rise in rates ≈ a 5.9% price drop.* The master risk knob for bonds.
- **Key-rate duration** — sensitivity to specific maturities on the **yield curve** (so you can see *where* the rate risk sits).
- **Yield to Maturity (YTM) / Yield to Worst (YTW)** — the income return if held to maturity; YTW assumes the worst-case (e.g. early call).
- **OAS (Option-Adjusted Spread)** — the extra yield a bond pays over Treasuries, adjusted for embedded options — compensation for credit and other risk. Wider OAS = riskier/cheaper.
- **Spread duration** — sensitivity to changes in credit spreads (vs interest-rate duration).
- **Convexity** — how a bond's duration itself changes as rates move (the curvature of the price/yield relationship).
- **Carry** — the income you earn simply by holding the bond over time.
- **Credit quality** — the ratings mix, from **AAA** (safest) down through **investment grade** (BBB- and up) to **high yield / below-investment-grade** ("junk").
- **Sector mix** — Treasuries / investment-grade corporates / high yield / **securitized** (MBS/ABS) / **EMD** (emerging-market debt).
- **Core vs Core Plus** — *Core* sticks near the Aggregate index; *Core Plus* adds out-of-benchmark sectors (high yield, EMD) for extra return — our sample mandate's strategy.

## 5. Private markets / alternatives

- **IRR (Internal Rate of Return)** — the annualized return that accounts for the *timing* of cash flows (money in vs money out).
- **DPI (Distributions to Paid-In)** — cash returned ÷ cash invested = *realized* return so far.
- **TVPI (Total Value to Paid-In)** — (distributions + remaining value) ÷ invested = *total* value, realized + unrealized.
- **J-curve** — private funds typically post early *losses* (fees + slow deployment) before later gains, so cumulative returns trace a "J."
- **Vintage (year)** — the year a fund began investing; LPs diversify across vintages to avoid timing one market.
- **Commitment pacing** — planning how much to *commit* each year to reach a target private allocation, given that capital is **called** (drawn) slowly over time.
- **NAV (Net Asset Value)** — the current marked value of the holdings.
- **Illiquidity budget** — how much illiquid (private) exposure a plan can tolerate given its liquidity needs.

## 6. Cost & fees (a constant pressure point)

- **bps (basis points)** — 1 bp = 0.01%. Fees and excess returns are quoted in bps. *Our fee = 38 bps = 0.38% per year.* *(`CGMandate.fee_bps`)*
- **Fee schedule / breakpoints** — the fee rate, usually *declining* as the mandate grows; **breakpoints** are the size thresholds where the rate steps down. A classic lever to defend a mandate under fee pressure.
- **Expense ratio (MER)** — the all-in annual cost of a fund as a % of assets.
- **Performance fee** — a fee tied to outperformance (common in alternatives, rare in long-only).
- **CEM Benchmarking** — an industry service that compares a fund's **cost *and* value-add** against genuinely comparable peers ("Cost Effectiveness Analysis").
- **Net value added** — value the manager/fund added: *net return − policy-benchmark return*. **Excess cost** — how much *more* (or less) you pay than the peer-median cost. Together they answer "are we paying for value?" *(`derived/cost.py` → `CostEffectiveness`)*

## 7. Due diligence & monitoring

- **Investment Due Diligence (IDD)** — evaluating the *strategy*: performance, process, people, fit. ("Is this a good investment?")
- **Operational Due Diligence (ODD)** — evaluating the *firm's operational risk*: valuation policy, internal controls & segregation of duties, compliance, IT/cyber, trade lifecycle, third-party service providers. ("Can this firm safely run the money?")
- **On watch** — a manager formally flagged for review — often the step before **termination**. *(`InvestmentAction.kind = "watch"` / `"terminate"`)*
- **Capacity** — how much money a strategy can run before its size erodes performance ("asset bloat").
- **Style drift** — a manager straying from its stated approach.
- **Key-person risk** — over-dependence on one star portfolio manager.

## 8. Market context & recommendations

- **Capital Market Assumptions (CMAs)** — a firm's long-term forecasts of **expected return, volatility, and correlation** by asset class — the raw inputs to allocation decisions. Capital Group publishes these; we ground *recommendations* in them. *(provenance `cg_house_view`)*
- **House view** — the firm's current market outlook and positioning themes.
- **Strategy fit / recommendation** — matching a CG strategy to a *gap* in the client's allocation or a stated need (e.g. their under-funded private-credit target). *(`derived` Recommendation)*

---

## How to read our sample (CalPERS, `data/snapshots/CALPERS.json`)

Every number below is a real field in the sample snapshot:

| Field | Value | Plain English |
|---|---|---|
| `funded_ratio` | 0.75 | Underfunded — 75¢ of assets per $1 owed → pressure to perform |
| `assumed_return` | 0.068 | Assumes 6.8%/yr long-term to value its promises |
| allocation: Private Credit | target 4% / actual 1.5% | **Under-allocated** — an opening to pitch CG private credit |
| `CGMandate.strategy` | Core Plus Income | A bond mandate that adds out-of-index sectors for extra yield |
| `size_mm` | 600.5 | The mandate is ~$600mm |
| `fee_bps` | 38 | We charge 0.38%/yr |
| `net_excess_bps` | 62 | We beat the benchmark by 0.62%/yr **after** fees |
| `information_ratio` | 0.71 | Strong skill-per-unit-of-risk |
| `down_capture` | 0.83 | We fall only 83% as much as the market in selloffs |
| `benchmark` | Bloomberg US Aggregate | The core-bond index we're measured against |

**Read as one sentence:** *"A ~$600mm core-plus bond mandate that beats its index by 0.62%/yr after a 0.38% fee, with good downside protection, for an underfunded pension that's under-allocated to private credit."* — which is exactly the kind of grounded story the brief turns into talking points.
