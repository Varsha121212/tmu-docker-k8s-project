-- Resets every book's available stock to a flat quantity, overwriting
-- whatever partial amount testing/load runs left behind. Identical across
-- all three stages - Stage 1/2/3 all run the same `inventory.stock` schema
-- (apps/services/inventory's Alembic migrations, reused unchanged from the
-- decomposed monolith per ADR-007).
--
-- Only available_qty (+ version/updated_at as a normal side effect of a
-- real stock change) is touched. reservations/stock_movements are audit
-- history only - the only column any reservation check actually reads is
-- available_qty (apps/services/inventory/app/modules/inventory/internal/
-- repository.py: `WHERE Stock.available_qty >= quantity`), so nothing else
-- needs to change to fix a false "out of stock" error.
--
-- Usage: psql -v qty=999 -f restock-inventory.sql
-- (falls back to 999 if -v qty=... isn't passed)

\if :{?qty}
\else
\set qty 999
\endif

\echo 'Stock levels BEFORE restock:'
SELECT b.title, s.book_id, s.available_qty
FROM inventory.stock s
LEFT JOIN catalog.books b ON b.id = s.book_id
ORDER BY s.available_qty ASC, b.title;

UPDATE inventory.stock
SET available_qty = :qty,
    version = version + 1,
    updated_at = now();

\echo 'Stock levels AFTER restock:'
SELECT b.title, s.book_id, s.available_qty
FROM inventory.stock s
LEFT JOIN catalog.books b ON b.id = s.book_id
ORDER BY b.title;

SELECT count(*) AS books_restocked, :qty AS new_available_qty FROM inventory.stock;
