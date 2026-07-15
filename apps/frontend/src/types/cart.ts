export interface CartItem {
  book_id: string;
  title: string;
  author_name: string;
  unit_price: string;
  quantity: number;
  line_total: string;
}

export interface Cart {
  items: CartItem[];
  total: string;
}
