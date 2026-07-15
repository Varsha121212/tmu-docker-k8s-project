import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ApiError } from "../lib/api";
import { useAuth } from "../context/AuthContext";
import { useCart } from "../context/CartContext";
import { checkout } from "../features/order/api";

export function CartPage() {
  const { cart, loading, updateItem, removeItem, clear, refresh } = useCart();
  const { token } = useAuth();
  const navigate = useNavigate();
  const [error, setError] = useState<string | null>(null);
  const [placingOrder, setPlacingOrder] = useState(false);
  // Persists across retries within this page visit: if checkout fails and the customer
  // clicks "Place order" again, the retry reuses the same key (US-ORD-04) instead of
  // risking a duplicate order from what looks like a fresh request.
  const [idempotencyKey] = useState(() => crypto.randomUUID());

  async function handleQuantityChange(bookId: string, nextQuantity: number) {
    setError(null);
    try {
      if (nextQuantity <= 0) {
        await removeItem(bookId);
      } else {
        await updateItem(bookId, nextQuantity);
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not update your cart.");
    }
  }

  async function handlePlaceOrder() {
    if (!token) return;
    setError(null);
    setPlacingOrder(true);
    try {
      const order = await checkout(token, idempotencyKey);
      await navigate(`/orders/${order.id}`, { state: { justPlaced: true } });
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        setError(
          "One or more items in your cart no longer have enough stock. Please review your cart and try again.",
        );
        await refresh();
      } else {
        setError(err instanceof ApiError ? err.message : "Could not place your order.");
      }
    } finally {
      setPlacingOrder(false);
    }
  }

  if (loading && !cart) {
    return <p className="text-ink-soft">Loading your cart...</p>;
  }

  const items = cart?.items ?? [];

  return (
    <div className="w-full max-w-2xl">
      <h1 className="mb-8 text-3xl text-ink">Your cart</h1>

      {error && (
        <p role="alert" className="mb-6 rounded-sm border border-danger/30 bg-danger/10 px-3 py-2 text-sm text-danger">
          {error}
        </p>
      )}

      {items.length === 0 ? (
        <div className="rounded-md border border-paper-line bg-paper-dim px-8 py-12 text-center">
          <p className="text-ink-soft">Your cart is empty.</p>
          <Link to="/" className="mt-4 inline-block font-medium text-primary underline underline-offset-2">
            Browse the shelves
          </Link>
        </div>
      ) : (
        <div className="overflow-hidden rounded-md border border-paper-line bg-paper-dim">
          <ul className="divide-y divide-paper-line">
            {items.map((item) => (
              <li key={item.book_id} className="flex items-center gap-4 px-6 py-4">
                <div className="flex-1">
                  <Link
                    to={`/books/${item.book_id}`}
                    className="font-display text-lg text-ink hover:text-primary"
                  >
                    {item.title}
                  </Link>
                  <p className="text-sm text-ink-soft">{item.author_name}</p>
                  <p className="mt-1 text-sm text-ink-soft">${item.unit_price} each</p>
                </div>

                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => handleQuantityChange(item.book_id, item.quantity - 1)}
                    className="flex h-7 w-7 items-center justify-center rounded-full border border-paper-line text-ink transition hover:border-primary hover:text-primary"
                    aria-label={`Decrease quantity of ${item.title}`}
                  >
                    &minus;
                  </button>
                  <span className="w-6 text-center text-ink">{item.quantity}</span>
                  <button
                    type="button"
                    onClick={() => handleQuantityChange(item.book_id, item.quantity + 1)}
                    className="flex h-7 w-7 items-center justify-center rounded-full border border-paper-line text-ink transition hover:border-primary hover:text-primary"
                    aria-label={`Increase quantity of ${item.title}`}
                  >
                    +
                  </button>
                </div>

                <span className="w-20 text-right font-display text-lg text-ink">
                  ${item.line_total}
                </span>
              </li>
            ))}
          </ul>

          <div className="flex items-center justify-between border-t border-paper-line px-6 py-5">
            <button
              type="button"
              onClick={() => clear()}
              className="text-sm font-medium text-ink-soft underline underline-offset-2 hover:text-danger"
            >
              Clear cart
            </button>
            <div className="text-right">
              <p className="text-xs uppercase tracking-[0.2em] text-ink-soft">Total</p>
              <p className="font-display text-2xl text-ink">${cart?.total}</p>
            </div>
          </div>

          <div className="border-t border-paper-line px-6 py-5">
            <button
              type="button"
              onClick={handlePlaceOrder}
              disabled={placingOrder}
              className="w-full rounded-sm bg-primary px-4 py-3 font-medium text-paper transition hover:bg-primary-dark disabled:cursor-not-allowed disabled:opacity-60"
            >
              {placingOrder ? "Placing order..." : "Place order"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
