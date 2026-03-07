account attrs:
    - date opened
    - last update

Need a concept of a "Recurring Period":
    Examples:
    - Monthly on the 1st
    - Monthly on the last day of the month
    - Twice monthly on the 1st and 15th
    - Yearly on January 1st
    - Daily on MTWRF
    - Weekly on Monday

Need to be able to CRUD accounts:
- Different account types with different attributes each
    - All accounts have:
        - database UUID
        - account number
        - user defined `name`
        - type
        - organization (IE: Wells Fargo, Robinhood)
        - a web URL
        - a notes field
    Types:
    - Checking
        - Balance
        - Fee amount (USD)
        - Fee period (IE: 1st of every month)
        - routing number
    - Savings
        - APY
        - Compound period (enum: Daily, Monthly)
        - Balance
        - Fee amount (USD)
        - Fee period
        - routing number
    - Cash
        - Bills -> Quantity
    - Line of credit
        - Balance
        - Fee amount (USD)
        - Fee period
        - APR
        - Compound period
        - Billing day (of the month - when the bill is given)
        - Payment day (of the month - when the bill is due)
    - Credit card
        - Balance
        - Fee amount (USD)
        - Fee period
        - APR
        - Billing day (of the month - when the bill is given)
        - Payment day (of the month - when the bill is due)
        - Compound period
        - expiration
        - CVC
    - Stocks account
        - Stock UUID -> Quantity
        - on UI this needs to be easy to select existing / create new
    - Crypto Exchange
        - USD balance
        - crypto ticker -> Quantity
    - Crypto Wallet (self hosted)
        - crypto ticker -> Quantity
    - Retirement
        - balance
        - Retirement acct type: Roth, SIMPLE, 401k
    - Loan
        - balance
        - APR
        - Compound period
        - Payment amount
        - Payment day
    - Rewards card
        - balance
        - expiration date
Stocks:
- uuid
- name
- ticker
- exchange (IE: NYSE)
- 

TODO:
- Contracts
- Recurring deposits
- Expenses/Budget
- Assets
- Receivables
- Credit score
- Money visual / forecast

- Bonds/CD
