# Integrate Portfolio Screen with Backend

This plan outlines the steps to build a real backend for the "Investment Portfolio" screen and integrate it with the Next.js frontend.

## User Review Required

> [!IMPORTANT]
> Since we don't have an existing Portfolio table in the database, I need to create a new database schema for `PortfolioPosition` to store our simulated institutional holdings. I will also generate some mock portfolio data (like AAPL, TCS, INFY) to populate the initial table so you can see it working. Let me know if you are okay with this approach.

## Proposed Changes

### Database Schema
#### [MODIFY] [models.py](file:///d:/Laraval-Projects/Sterlin_BPO_Company/Ein_Sof_Lite%20-%20Copy/src/domain/models.py)
Add a new SQLAlchemy model `PortfolioPosition`:
- `id`: Integer Primary Key
- `symbol_id`: Foreign Key to `SymbolMaster`
- `quantity`: Float (number of shares held)
- `average_buy_price`: Float (average entry price)
- `sector`: String (e.g., Technology, Finance, Energy)
- `last_updated`: DateTime

### Backend API
#### [MODIFY] [main.py](file:///d:/Laraval-Projects/Sterlin_BPO_Company/Ein_Sof_Lite%20-%20Copy/src/main.py)
Create a new endpoint `@app.get("/api/portfolio/summary")` that:
- Queries all `PortfolioPosition` records from the database.
- Joins with `SymbolMaster` to get the ticker and company name.
- Retrieves the latest `ProcessedMarketData` to calculate the current real-time price and 24h change %.
- Calculates the Total NAV (Net Asset Value) by summing up `quantity * current_price`.
- Calculates the Sector Distribution percentages (e.g., Technology 60%, Finance 25%) based on the current market value of holdings.
- Returns a structured JSON payload for the frontend.

#### [NEW] [scripts/seed_portfolio.py](file:///d:/Laraval-Projects/Sterlin_BPO_Company/Ein_Sof_Lite%20-%20Copy/src/scripts/seed_portfolio.py)
Create a quick initialization script to insert some dummy institutional positions (e.g., RELIANCE, TCS, INFY) into the `PortfolioPosition` table so the UI has something to display immediately.

### Frontend Integration
#### [MODIFY] [api.ts](file:///d:/Laraval-Projects/Sterlin_BPO_Company/Ein_Sof_Lite%20-%20Copy/frontend/lib/api.ts)
Add a `fetchPortfolio()` function to call the new `/api/portfolio/summary` endpoint.

#### [MODIFY] [portfolio/page.tsx](file:///d:/Laraval-Projects/Sterlin_BPO_Company/Ein_Sof_Lite%20-%20Copy/frontend/app/portfolio/page.tsx)
- Add `useState` and `useEffect` hooks to fetch the portfolio data on mount.
- Replace the hardcoded `portfolioData` array with the dynamic data from the backend.
- Dynamically render the Sector Distribution Donut Chart using the calculated percentages.
- Update the Total NAV number dynamically.

## Verification Plan
### Automated Tests
- N/A

### Manual Verification
- Ensure the database migration script runs without errors.
- Ensure the `/api/portfolio/summary` endpoint returns valid JSON.
- Verify that the frontend Portfolio UI correctly renders the dynamic rows, sector distribution ring, and total NAV based on the backend data.
