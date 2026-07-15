import { useAuth } from "../context/AuthContext";

export function ProfilePage() {
  const { user, logout } = useAuth();
  const initial = user?.display_name?.trim().charAt(0).toUpperCase() ?? "?";

  return (
    <div className="w-full max-w-md animate-[rise_0.5s_ease-out]">
      <div className="relative rounded-md border border-paper-line bg-paper-dim px-8 py-9 shadow-[0_1px_2px_rgb(36_31_28_/_0.06),0_18px_36px_-24px_rgb(36_31_28_/_0.45)]">
        <div className="absolute inset-x-0 top-0 h-1 rounded-t-md bg-gradient-to-r from-accent via-primary to-accent" />

        <div className="flex items-center gap-4">
          <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-full bg-primary font-display text-2xl text-paper">
            {initial}
          </div>
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.25em] text-accent">
              Reader account
            </p>
            <h1 className="text-2xl text-ink">{user?.display_name ?? "Welcome"}</h1>
          </div>
        </div>

        {user && (
          <dl className="mt-8 divide-y divide-paper-line border-y border-paper-line text-sm">
            <div className="flex items-center justify-between py-3">
              <dt className="text-ink-soft">Email</dt>
              <dd className="font-medium text-ink">{user.email}</dd>
            </div>
            <div className="flex items-center justify-between py-3">
              <dt className="text-ink-soft">Member since</dt>
              <dd className="font-medium text-ink">
                {new Date(user.created_at).toLocaleDateString(undefined, {
                  year: "numeric",
                  month: "long",
                  day: "numeric",
                })}
              </dd>
            </div>
            <div className="flex items-center justify-between py-3">
              <dt className="text-ink-soft">Status</dt>
              <dd className="font-medium text-success">{user.active ? "Active" : "Inactive"}</dd>
            </div>
          </dl>
        )}

        <button
          type="button"
          onClick={logout}
          className="mt-7 w-full rounded-sm border border-primary px-4 py-2.5 font-medium text-primary transition hover:bg-primary hover:text-paper"
        >
          Log out
        </button>
      </div>
    </div>
  );
}
