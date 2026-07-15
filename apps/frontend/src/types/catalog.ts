export interface Book {
  id: string;
  isbn: string | null;
  title: string;
  author_name: string;
  category: string;
  price: string;
  active: boolean;
  cover_image_url: string | null;
}

export interface PaginatedBooks {
  items: Book[];
  total: number;
  page: number;
  page_size: number;
}
