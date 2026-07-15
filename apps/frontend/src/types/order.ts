export interface OrderItem {
  book_id: string;
  title_snapshot: string;
  unit_price: string;
  quantity: number;
  line_total: string;
}

export interface Order {
  id: string;
  status: string;
  total_amount: string;
  created_at: string;
  items: OrderItem[];
}
