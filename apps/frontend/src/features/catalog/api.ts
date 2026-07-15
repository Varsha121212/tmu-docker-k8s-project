import { api } from "../../lib/api";
import type { Book, PaginatedBooks } from "../../types/catalog";

export interface ListBooksParams {
  q?: string;
  category?: string;
  author?: string;
  page?: number;
  pageSize?: number;
}

export function listBooks(params: ListBooksParams = {}) {
  const query = new URLSearchParams();
  if (params.q) query.set("q", params.q);
  if (params.category) query.set("category", params.category);
  if (params.author) query.set("author", params.author);
  if (params.page) query.set("page", String(params.page));
  if (params.pageSize) query.set("page_size", String(params.pageSize));

  const suffix = query.toString() ? `?${query.toString()}` : "";
  return api.get<PaginatedBooks>(`/books${suffix}`);
}

export function getBook(id: string) {
  return api.get<Book>(`/books/${id}`);
}

export function listCategories() {
  return api.get<string[]>("/books/categories");
}
