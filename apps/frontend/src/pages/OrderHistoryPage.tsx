import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { listOrders } from "../features/order/api";
import { useAuth } from "../context/AuthContext";
import type { Order } from "../types/order";

export function OrderHistoryPage() {
  const { token } = useAuth();
  const [orders, setOrders] = useState<Order[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!token) return;
    listOrders(token)
      .then(setOrders)
      .catch(() => setError("Could not load your order history."));
  }, [token]);

  return (
    <div className="w-full max-w-2xl">
      <h1 className="mb-8 text-3xl text-ink">Order history</h1>

      {error && (
        <p role="alert" className="mb-6 rounded-sm border border-danger/30 bg-danger/10 px-3 py-2 text-sm text-danger">
          {error}
        </p>
      )}

      {orders === null && !error && <p className="text-ink-soft">Loading...</p>}

      {orders?.length === 0 && (
        <div className="rounded-md border border-paper-line bg-paper-dim px-8 py-12 text-center">
          <p className="text-ink-soft">You haven&apos;t placed any orders yet.</p>
          <Link to="/" className="mt-4 inline-block font-medium text-primary underline underline-offset-2">
            Browse the shelves
          </Link>
        </div>
      )}

      {orders && orders.length > 0 && (
        <ul className="overflow-hidden rounded-md border border-paper-line bg-paper-dim">
          {orders.map((order) => (
            <li key={order.id} className="border-b border-paper-line last:border-0">
              <Link
                to={`/orders/${order.id}`}
                className="flex items-center justify-between px-6 py-4 transition hover:bg-paper"
              >
                <div>
                  <p className="text-ink">Order #{order.id.slice(0, 8)}</p>
                  <p className="text-sm text-ink-soft">
                    {new Date(order.created_at).toLocaleDateString()} &middot; {order.status}
                  </p>
                </div>
                <span className="font-display text-lg text-ink">${order.total_amount}</span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
