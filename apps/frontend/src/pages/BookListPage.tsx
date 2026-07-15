import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { BookCard } from "../components/BookCard";
import { listBooks, listCategories } from "../features/catalog/api";
import type { PaginatedBooks } from "../types/catalog";

const PAGE_SIZE = 12;

export function BookListPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const q = searchParams.get("q") ?? "";
  const category = searchParams.get("category") ?? "";
  const page = Number(searchParams.get("page") ?? "1");

  const [queryInput, setQueryInput] = useState(q);
  const [categories, setCategories] = useState<string[]>([]);
  const [result, setResult] = useState<PaginatedBooks | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listCategories()
      .then(setCategories)
      .catch(() => setCategories([]));
  }, []);

  useEffect(() => {
    setLoading(true);
    setError(null);
    listBooks({ q: q || undefined, category: category || undefined, page, pageSize: PAGE_SIZE })
      .then(setResult)
      .catch(() => setError("Could not load books. Please try again."))
      .finally(() => setLoading(false));
  }, [q, category, page]);

  function updateParams(next: { q?: string; category?: string; page?: number }) {
    const params = new URLSearchParams(searchParams);
    if (next.q !== undefined) {
      if (next.q) params.set("q", next.q);
      else params.delete("q");
    }
    if (next.category !== undefined) {
      if (next.category) params.set("category", next.category);
      else params.delete("category");
    }
    params.set("page", String(next.page ?? 1));
    setSearchParams(params);
  }

  const totalPages = result ? Math.max(1, Math.ceil(result.total / result.page_size)) : 1;

  return (
    <div className="w-full max-w-5xl">
      <div className="mb-10 text-center">
        <p className="text-xs font-semibold uppercase tracking-[0.3em] text-accent">The shelves</p>
        <h1 className="mt-2 text-4xl text-ink">Browse the collection</h1>
      </div>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          updateParams({ q: queryInput, page: 1 });
        }}
        className="mb-6 flex flex-col gap-3 sm:flex-row"
      >
        <input
          value={queryInput}
          onChange={(e) => setQueryInput(e.target.value)}
          placeholder="Search by title..."
          className="flex-1 rounded-sm border border-paper-line bg-paper px-3.5 py-2.5 text-ink placeholder:text-ink-soft/50 outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/20"
        />
        <button
          type="submit"
          className="rounded-sm bg-primary px-5 py-2.5 font-medium text-paper transition hover:bg-primary-dark"
        >
          Search
        </button>
      </form>

      <div className="mb-10 flex flex-wrap gap-2">
        <button
          type="button"
          onClick={() => updateParams({ category: "", page: 1 })}
          className={`rounded-full border px-4 py-1.5 text-sm font-medium transition ${
            category === ""
              ? "border-primary bg-primary text-paper"
              : "border-paper-line bg-paper-dim text-ink-soft hover:border-primary hover:text-primary"
          }`}
        >
          All categories
        </button>
        {categories.map((c) => (
          <button
            key={c}
            type="button"
            onClick={() => updateParams({ category: c, page: 1 })}
            className={`rounded-full border px-4 py-1.5 text-sm font-medium transition ${
              category === c
                ? "border-primary bg-primary text-paper"
                : "border-paper-line bg-paper-dim text-ink-soft hover:border-primary hover:text-primary"
            }`}
          >
            {c}
          </button>
        ))}
      </div>

      {error && (
        <p role="alert" className="mb-6 rounded-sm border border-danger/30 bg-danger/10 px-3 py-2 text-sm text-danger">
          {error}
        </p>
      )}

      {loading && <p className="text-center text-ink-soft">Loading books...</p>}

      {!loading && result && result.items.length === 0 && (
        <p className="text-center text-ink-soft">No books match your search.</p>
      )}

      {!loading && result && result.items.length > 0 && (
        <>
          <div className="grid grid-cols-2 gap-5 sm:grid-cols-3 lg:grid-cols-4">
            {result.items.map((book) => (
              <BookCard key={book.id} book={book} />
            ))}
          </div>

          {totalPages > 1 && (
            <div className="mt-10 flex items-center justify-center gap-4">
              <button
                type="button"
                disabled={page <= 1}
                onClick={() => updateParams({ page: page - 1 })}
                className="rounded-sm border border-paper-line px-4 py-2 text-sm font-medium text-ink transition hover:border-primary hover:text-primary disabled:cursor-not-allowed disabled:opacity-40"
              >
                Previous
              </button>
              <span className="text-sm text-ink-soft">
                Page {page} of {totalPages}
              </span>
              <button
                type="button"
                disabled={page >= totalPages}
                onClick={() => updateParams({ page: page + 1 })}
                className="rounded-sm border border-paper-line px-4 py-2 text-sm font-medium text-ink transition hover:border-primary hover:text-primary disabled:cursor-not-allowed disabled:opacity-40"
              >
                Next
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
