import { useState } from "react";
import { useSite } from "./SiteProvider";
import { AddWebsiteDialog } from "./AddWebsiteDialog";
import { Skeleton } from "./Skeleton";
import { Check, ChevronDown, Globe2, Plus } from "lucide-react";

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
    <div className="relative border-b border-slate-200 px-3 py-2.5">
      <button
        type="button"
        aria-label="Select website"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between gap-2 rounded-xl px-3 py-2 text-left text-sm font-medium text-slate-700 transition hover:bg-slate-100"
      >
        <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-md bg-sky-100 text-sky-600"><Globe2 className="h-3 w-3" /></span>
        {sites === undefined ? (
          <Skeleton className="h-4 w-32" />
        ) : (
          <span className="min-w-0 flex-1 truncate">{label}</span>
        )}
        <ChevronDown className={`h-4 w-4 shrink-0 text-slate-400 transition-transform ${open ? "rotate-180" : ""}`} />
      </button>

      {open && (
        <>
          {/* Click-away scrim. */}
          <div className="fixed inset-0 z-30" onClick={() => setOpen(false)} role="presentation" />
          <div className="absolute left-3 right-3 z-40 mt-1 overflow-hidden rounded-xl border border-slate-200 bg-white py-1 shadow-lg">
            <ul className="max-h-64 overflow-y-auto">
              {sites?.map((s) => (
                <li key={s.id}>
                  <button
                    type="button"
                    onClick={() => {
                      selectSite(s.id);
                      setOpen(false);
                    }}
                    className={`flex w-full items-center gap-2 truncate px-3 py-2 text-left text-sm transition ${
                      s.id === selectedSiteId
                        ? "font-semibold text-sky-700"
                        : "text-slate-700 hover:bg-slate-100"
                    }`}
                  >
                    <Globe2 className="h-3.5 w-3.5 shrink-0 text-slate-300" />
                    <span className="min-w-0 flex-1 truncate">{s.name}</span>
                    {s.id === selectedSiteId && <Check className="h-3.5 w-3.5 shrink-0 text-sky-600" />}
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
                  <Plus className="h-4 w-4" /> Add website
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
