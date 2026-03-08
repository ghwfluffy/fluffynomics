ALTER TABLE contracts
ADD COLUMN IF NOT EXISTS expiration_date DATE NOT NULL DEFAULT DATE '2099-01-01';

UPDATE contracts
SET expiration_date = DATE '2099-01-01'
WHERE expiration_date IS NULL;
