import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import * as cartApi from "../features/cart/api";
import type { Cart } from "../types/cart";
import { useAuth } from "./AuthContext";

interface CartContextValue {
  cart: Cart | null;
  itemCount: number;
  loading: boolean;
  refresh: () => Promise<void>;
  addItem: (bookId: string, quantity: number) => Promise<void>;
  updateItem: (bookId: string, quantity: number) => Promise<void>;
  removeItem: (bookId: string) => Promise<void>;
  clear: () => Promise<void>;
}

const CartContext = createContext<CartContextValue | undefined>(undefined);

export function CartProvider({ children }: { children: ReactNode }) {
  const { token } = useAuth();
  const [cart, setCart] = useState<Cart | null>(null);
  const [loading, setLoading] = useState(false);

  const refresh = useCallback(async () => {
    if (!token) {
      setCart(null);
      return;
    }
    setLoading(true);
    try {
      setCart(await cartApi.getCart(token));
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const addItem = useCallback(
    async (bookId: string, quantity: number) => {
      if (!token) return;
      setCart(await cartApi.addItem(token, bookId, quantity));
    },
    [token],
  );

  const updateItem = useCallback(
    async (bookId: string, quantity: number) => {
      if (!token) return;
      setCart(await cartApi.updateItem(token, bookId, quantity));
    },
    [token],
  );

  const removeItem = useCallback(
    async (bookId: string) => {
      if (!token) return;
      setCart(await cartApi.removeItem(token, bookId));
    },
    [token],
  );

  const clear = useCallback(async () => {
    if (!token) return;
    await cartApi.clearCart(token);
    setCart({ items: [], total: "0" });
  }, [token]);

  const itemCount = cart?.items.reduce((sum, item) => sum + item.quantity, 0) ?? 0;

  const value = useMemo(
    () => ({ cart, itemCount, loading, refresh, addItem, updateItem, removeItem, clear }),
    [cart, itemCount, loading, refresh, addItem, updateItem, removeItem, clear],
  );

  return <CartContext.Provider value={value}>{children}</CartContext.Provider>;
}

export function useCart(): CartContextValue {
  const context = useContext(CartContext);
  if (!context) {
    throw new Error("useCart must be used within a CartProvider");
  }
  return context;
}
