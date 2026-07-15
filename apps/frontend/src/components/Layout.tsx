import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { useCart } from "../context/CartContext";

function OpenBookMark() {
  return (
    <svg
      viewBox="0 0 40 28"
      className="h-7 w-10 text-primary"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M20 5.5C17 3 12 2 4 2v20c8 0 13 1 16 3.5" />
      <path d="M20 5.5C23 3 28 2 36 2v20c-8 0-13 1-16 3.5" />
      <path d="M20 5.5V25.5" />
    </svg>
  );
}

export function Layout({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  const { itemCount } = useCart();

  return (
    <div className="flex min-h-screen flex-col">
      <header className="border-b border-paper-line/80 bg-paper-dim">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-6 py-4">
          <Link to="/" className="flex items-center gap-3">
            <OpenBookMark />
            <span className="flex flex-col leading-none">
              <span className="font-display text-2xl tracking-tight text-ink">TMU BookVerse</span>
              <span className="mt-1 text-[0.65rem] font-medium uppercase tracking-[0.25em] text-ink-soft">
                Online Bookstore
              </span>
            </span>
          </Link>
          <nav className="flex items-center gap-6 text-sm font-medium text-ink-soft">
            <Link to="/" className="transition hover:text-primary">
              Home
            </Link>
            {user && (
              <Link to="/orders" className="transition hover:text-primary">
                Orders
              </Link>
            )}
            {user && (
              <Link to="/cart" className="relative transition hover:text-primary">
                Cart
                {itemCount > 0 && (
                  <span className="absolute -right-3 -top-2 flex h-4 min-w-4 items-center justify-center rounded-full bg-accent px-1 text-[0.65rem] font-semibold text-paper">
                    {itemCount}
                  </span>
                )}
              </Link>
            )}
            {user ? (
              <Link
                to="/profile"
                className="rounded-full bg-primary px-4 py-1.5 text-paper transition hover:bg-primary-dark"
              >
                {user.display_name}
              </Link>
            ) : (
              <>
                <Link to="/login" className="transition hover:text-primary">
                  Log in
                </Link>
                <Link
                  to="/register"
                  className="rounded-full bg-primary px-4 py-1.5 text-paper transition hover:bg-primary-dark"
                >
                  Register
                </Link>
              </>
            )}
          </nav>
        </div>
      </header>

      <main className="flex flex-1 items-center justify-center px-6 py-16">{children}</main>

      <footer className="border-t border-paper-line/80 py-6 text-center text-xs text-ink-soft">
        &copy; {new Date().getFullYear()} TMU BookVerse. A small shop for well-loved books.
      </footer>
    </div>
  );
}
