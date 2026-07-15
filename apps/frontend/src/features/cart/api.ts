import { api } from "../../lib/api";
import type { Cart } from "../../types/cart";

export function getCart(token: string) {
  return api.get<Cart>("/cart", token);
}

export function addItem(token: string, bookId: string, quantity: number) {
  return api.post<Cart>("/cart/items", { book_id: bookId, quantity }, token);
}

export function updateItem(token: string, bookId: string, quantity: number) {
  return api.patch<Cart>(`/cart/items/${bookId}`, { quantity }, token);
}

export function removeItem(token: string, bookId: string) {
  return api.del<Cart>(`/cart/items/${bookId}`, token);
}

export function clearCart(token: string) {
  return api.del<void>("/cart", token);
}
