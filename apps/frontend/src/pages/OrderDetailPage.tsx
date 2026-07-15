import { useEffect, useState } from "react";
import { Link, useLocation, useParams } from "react-router-dom";
import { getOrder } from "../features/order/api";
import { ApiError } from "../lib/api";
import { useAuth } from "../context/AuthContext";
import type { Order } from "../types/order";

export function OrderDetailPage() {
  const { orderId } = useParams<{ orderId: string }>();
  const { token } = useAuth();
  const location = useLocation();
  const justPlaced = Boolean((location.state as { justPlaced?: boolean } | null)?.justPlaced);

  const [order, setOrder] = useState<Order | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!orderId || !token) return;
    getOrder(token, orderId)
      .then(setOrder)
      .catch((err) => {
        if (err instanceof ApiError && err.status === 404) {
          setNotFound(true);
        } else {
          setError("Could not load this order.");
        }
      });
  }, [orderId, token]);

  if (notFound) {
    return (
      <div className="text-center">
        <h1 className="text-3xl text-ink">Order not found</h1>
        <Link to="/orders" className="mt-6 inline-block font-medium text-primary underline underline-offset-2">
          Back to order history
        </Link>
      </div>
    );
  }

  if (error) {
    return (
      <p role="alert" className="rounded-sm border border-danger/30 bg-danger/10 px-4 py-3 text-danger">
        {error}
      </p>
    );
  }

  if (!order) {
    return <p className="text-ink-soft">Loading...</p>;
  }

  return (
    <div className="w-full max-w-2xl">
      {justPlaced && (
        <p className="mb-6 rounded-sm border border-success/30 bg-success/10 px-4 py-3 text-success">
          Thank you &mdash; your order has been placed.
        </p>
      )}

      <div className="rounded-md border border-paper-line bg-paper-dim px-8 py-9">
        <p className="text-xs font-semibold uppercase tracking-[0.25em] text-accent">
          Order confirmation
        </p>
        <h1 className="mt-2 text-2xl text-ink">Order #{order.id.slice(0, 8)}</h1>
        <p className="mt-1 text-sm text-ink-soft">
          Placed {new Date(order.created_at).toLocaleString()} &middot; Status: {order.status}
        </p>

        <ul className="mt-6 divide-y divide-paper-line border-y border-paper-line">
          {order.items.map((item) => (
            <li key={item.book_id} className="flex items-center justify-between py-3">
              <div>
                <p className="text-ink">{item.title_snapshot}</p>
                <p className="text-sm text-ink-soft">
                  {item.quantity} &times; ${item.unit_price}
                </p>
              </div>
              <span className="font-display text-lg text-ink">${item.line_total}</span>
            </li>
          ))}
        </ul>

        <div className="mt-6 flex items-center justify-between">
          <Link to="/orders" className="text-sm font-medium text-primary underline underline-offset-2">
            Back to order history
          </Link>
          <p className="font-display text-2xl text-ink">${order.total_amount}</p>
        </div>
      </div>
    </div>
  );
}
