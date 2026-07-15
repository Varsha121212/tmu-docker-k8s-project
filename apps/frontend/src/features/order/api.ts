import { api } from "../../lib/api";
import type { Order } from "../../types/order";

export function checkout(token: string, idempotencyKey: string) {
  return api.post<Order>("/orders", { idempotency_key: idempotencyKey }, token);
}

export function listOrders(token: string) {
  return api.get<Order[]>("/orders", token);
}

export function getOrder(token: string, orderId: string) {
  return api.get<Order>(`/orders/${orderId}`, token);
}
