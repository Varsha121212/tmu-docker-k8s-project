import { useEffect, useState } from "react";
import { Link, useLocation, useNavigate, useParams } from "react-router-dom";
import { getBook } from "../features/catalog/api";
import { getCoverGradient } from "../lib/coverPlaceholder";
import { ApiError } from "../lib/api";
import { useAuth } from "../context/AuthContext";
import { useCart } from "../context/CartContext";
import type { Book } from "../types/catalog";

export function BookDetailPage() {
  const { bookId } = useParams<{ bookId: string }>();
  const [book, setBook] = useState<Book | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [quantity, setQuantity] = useState(1);
  const [adding, setAdding] = useState(false);
  const [added, setAdded] = useState(false);
  const { token } = useAuth();
  const { addItem } = useCart();
  const navigate = useNavigate();
  const location = useLocation();

  useEffect(() => {
    if (!bookId) return;
    setNotFound(false);
    setError(null);
    getBook(bookId)
      .then(setBook)
      .catch((err) => {
        if (err instanceof ApiError && err.status === 404) {
          setNotFound(true);
        } else {
          setError("Could not load this book. Please try again.");
        }
      });
  }, [bookId]);

  async function handleAddToCart() {
    if (!book) return;
    if (!token) {
      await navigate("/login", { state: { from: location.pathname } });
      return;
    }
    setError(null);
    setAdding(true);
    try {
      await addItem(book.id, quantity);
      setAdded(true);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not add this book to your cart.");
    } finally {
      setAdding(false);
    }
  }

  if (notFound) {
    return (
      <div className="text-center">
        <h1 className="text-3xl text-ink">Book not found</h1>
        <p className="mt-2 text-ink-soft">It may have been removed from the catalog.</p>
        <Link to="/" className="mt-6 inline-block font-medium text-primary underline underline-offset-2">
          Back to the shelves
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

  if (!book) {
    return <p className="text-ink-soft">Loading...</p>;
  }

  return (
    <div className="w-full max-w-2xl">
      <Link to="/" className="text-sm font-medium text-primary underline underline-offset-2">
        &larr; Back to the shelves
      </Link>

      <div className="mt-6 flex flex-col overflow-hidden rounded-md border border-paper-line bg-paper-dim shadow-[0_1px_2px_rgb(42_36_64_/_0.06),0_18px_36px_-24px_rgb(42_36_64_/_0.35)] sm:flex-row">
        <div className="aspect-[2/3] w-full shrink-0 sm:w-48">
          {book.cover_image_url ? (
            <img
              src={book.cover_image_url}
              alt={`Cover of ${book.title}`}
              className="h-full w-full object-cover"
            />
          ) : (
            <div
              className="flex h-full w-full flex-col items-center justify-center gap-2 p-4 text-center"
              style={{ background: getCoverGradient(book.category) }}
            >
              <span className="text-[0.6rem] font-semibold uppercase tracking-[0.2em] text-white/70">
                {book.category}
              </span>
              <span className="font-display text-lg leading-snug text-white">{book.title}</span>
            </div>
          )}
        </div>
        <div className="flex-1 px-8 py-9">
          <span className="text-xs font-semibold uppercase tracking-[0.25em] text-accent">
            {book.category}
          </span>
          <h1 className="mt-2 text-3xl text-ink">{book.title}</h1>
          <p className="mt-1 text-lg text-ink-soft">by {book.author_name}</p>

          <div className="mt-6 flex items-center gap-4 border-t border-paper-line pt-6">
            <span className="font-display text-3xl text-primary">${book.price}</span>
            {!book.active && (
              <span className="rounded-sm border border-danger/30 bg-danger/10 px-2 py-1 text-xs font-medium text-danger">
                Currently unavailable
              </span>
            )}
          </div>

          {error && (
            <p role="alert" className="mt-4 rounded-sm border border-danger/30 bg-danger/10 px-3 py-2 text-sm text-danger">
              {error}
            </p>
          )}

          {book.active && (
            <div className="mt-6 flex items-center gap-3">
              <select
                value={quantity}
                onChange={(e) => {
                  setQuantity(Number(e.target.value));
                  setAdded(false);
                }}
                className="rounded-sm border border-paper-line bg-paper px-3 py-2 text-ink outline-none focus:border-primary focus:ring-2 focus:ring-primary/20"
                aria-label="Quantity"
              >
                {[1, 2, 3, 4, 5].map((n) => (
                  <option key={n} value={n}>
                    {n}
                  </option>
                ))}
              </select>
              <button
                type="button"
                onClick={handleAddToCart}
                disabled={adding}
                className="rounded-sm bg-primary px-5 py-2 font-medium text-paper transition hover:bg-primary-dark disabled:cursor-not-allowed disabled:opacity-60"
              >
                {adding ? "Adding..." : added ? "Added to cart" : "Add to cart"}
              </button>
            </div>
          )}

          {book.isbn && <p className="mt-4 text-xs text-ink-soft">ISBN {book.isbn}</p>}
        </div>
      </div>
    </div>
  );
}
