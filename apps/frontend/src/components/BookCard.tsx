import { Link } from "react-router-dom";
import { getCoverGradient } from "../lib/coverPlaceholder";
import type { Book } from "../types/catalog";

export function BookCard({ book }: { book: Book }) {
  return (
    <Link
      to={`/books/${book.id}`}
      className="group flex flex-col overflow-hidden rounded-lg border border-paper-line bg-paper-dim shadow-[0_1px_2px_rgb(42_36_64_/_0.06)] transition hover:-translate-y-1 hover:shadow-[0_16px_28px_-18px_rgb(42_36_64_/_0.35)]"
    >
      <div className="relative aspect-[2/3] w-full overflow-hidden">
        {book.cover_image_url ? (
          <img
            src={book.cover_image_url}
            alt={`Cover of ${book.title}`}
            loading="lazy"
            className="h-full w-full object-cover transition duration-300 group-hover:scale-105"
          />
        ) : (
          <div
            className="flex h-full w-full flex-col items-center justify-center gap-2 p-4 text-center transition duration-300 group-hover:scale-105"
            style={{ background: getCoverGradient(book.category) }}
          >
            <span className="text-[0.6rem] font-semibold uppercase tracking-[0.2em] text-white/70">
              {book.category}
            </span>
            <span className="font-display text-lg leading-snug text-white">{book.title}</span>
          </div>
        )}
        <span className="absolute left-2.5 top-2.5 rounded-full bg-paper-dim/90 px-2.5 py-1 text-[0.6rem] font-semibold uppercase tracking-[0.15em] text-primary shadow-sm">
          {book.category}
        </span>
      </div>
      <div className="flex flex-1 flex-col gap-1 px-4 py-3.5">
        <h3 className="font-display text-base leading-snug text-ink group-hover:text-primary">
          {book.title}
        </h3>
        <p className="text-sm text-ink-soft">{book.author_name}</p>
        <p className="mt-auto pt-2 font-display text-lg text-primary">${book.price}</p>
      </div>
    </Link>
  );
}
