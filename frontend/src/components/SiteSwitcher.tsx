import { useState } from "react";
import { useSite } from "./SiteProvider";
import { AddWebsiteDialog } from "./AddWebsiteDialog";
import { Skeleton } from "./Skeleton";

/**
 * Cloudflare-style website picker pinned at the top of the sidebar. The current
 * site is always visible; the dropdown switches between sites or adds a new one.
 * Renaming and deleting a website live on the Settings page.
 */
export function SiteSwitcher() {
  const { sites, current, selectedSiteId, selectSite, createSite, ownsAnySite } =
    useSite();
  const [open, setOpen] = useState(false);
  const [addOpen, setAddOpen] = useState(false);

  const label = current?.name ?? (sites && sites.length === 0 ? "No websites" : "Loading…");

  return (
    <div className="relative border-b border-slate-200 px-3 py-2">
      <button
        type="button"
        aria-label="Select website"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between gap-2 rounded-lg border border-slate-300 bg-white px-3 py-2 text-left text-sm font-medium text-slate-700 transition hover:bg-slate-100"
      >
        {sites === undefined ? (
          <Skeleton className="h-4 w-32" />
        ) : (
          <span className="min-w-0 flex-1 truncate">{label}</span>
        )}
        <svg width="16" height="16" viewBox="0 0 20 20" fill="none" aria-hidden="true">
          <path
            d="M6 8l4 4 4-4"
            stroke="currentColor"
            strokeWidth="1.6"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </button>

      {open && (
        <>
          {/* Click-away scrim. */}
          <div className="fixed inset-0 z-30" onClick={() => setOpen(false)} role="presentation" />
          <div className="absolute left-3 right-3 z-40 mt-1 rounded-lg border border-slate-200 bg-white py-1 shadow-lg">
            <ul className="max-h-64 overflow-y-auto">
              {sites?.map((s) => (
                <li key={s.id}>
                  <button
                    type="button"
                    onClick={() => {
                      selectSite(s.id);
                      setOpen(false);
                    }}
                    className={`block w-full truncate px-3 py-2 text-left text-sm transition ${
                      s.id === selectedSiteId
                        ? "font-semibold text-sky-700"
                        : "text-slate-700 hover:bg-slate-100"
                    }`}
                  >
                    {s.name}
                  </button>
                </li>
              ))}
            </ul>

            {/* Members work on someone else's sites; don't offer site creation. */}
            {ownsAnySite && (
              <div className="border-t border-slate-100 p-1">
                <button
                  type="button"
                  onClick={() => {
                    setOpen(false);
                    setAddOpen(true);
                  }}
                  className="flex w-full items-center gap-2 rounded-md px-3 py-2 text-left text-sm font-medium text-sky-700 transition hover:bg-sky-50"
                >
                  <span className="text-lg leading-none">+</span> Add website
                </button>
              </div>
            )}
          </div>
        </>
      )}

      <AddWebsiteDialog
        open={addOpen}
        onClose={() => setAddOpen(false)}
        onSubmit={async (name, url) => {
          await createSite(name, url);
        }}
      />
    </div>
  );
}
