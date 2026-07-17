import {
  createContext,
  ReactNode,
  useCallback,
  useContext,
  useEffect,
  useState,
} from "react";
import useSWR from "swr";
import {
  Site,
  createSite as apiCreateSite,
  deleteSite as apiDeleteSite,
  renameSite as apiRenameSite,
  listSites,
  sitesKey,
} from "../api/sites";
import { useToast } from "./Toast";

const SELECTED_SITE_KEY = "selectedSiteId";

interface SiteContextValue {
  sites: Site[] | undefined;
  selectedSiteId: number | null;
  current: Site | undefined;
  isLoading: boolean;
  /** The caller owns the currently selected site (vs. team-member access). */
  isOwner: boolean;
  /** The caller owns at least one site (or could create their first one). */
  ownsAnySite: boolean;
  selectSite: (id: number) => void;
  createSite: (name: string, widgetOrigin?: string) => Promise<Site>;
  renameSite: (id: number, name: string) => Promise<void>;
  deleteSite: (id: number) => Promise<void>;
}

const SiteContext = createContext<SiteContextValue>({
  sites: undefined,
  selectedSiteId: null,
  current: undefined,
  isLoading: true,
  isOwner: true,
  ownsAnySite: true,
  selectSite: () => {},
  createSite: async () => {
    throw new Error("SiteProvider missing");
  },
  renameSite: async () => {},
  deleteSite: async () => {},
});

/** Which website the whole admin app is currently scoped to. */
export function useSite() {
  return useContext(SiteContext);
}

function loadSelectedSiteId(): number | null {
  const raw = localStorage.getItem(SELECTED_SITE_KEY);
  if (!raw) return null;
  const id = Number(raw);
  return Number.isFinite(id) ? id : null;
}

export function SiteProvider({ children }: { children: ReactNode }) {
  const { data: sites, mutate } = useSWR(sitesKey, listSites);
  const { showToast } = useToast();
  const [selectedSiteId, setSelectedSiteId] = useState<number | null>(
    loadSelectedSiteId
  );

  // Persist the selection across reloads.
  useEffect(() => {
    if (selectedSiteId === null) localStorage.removeItem(SELECTED_SITE_KEY);
    else localStorage.setItem(SELECTED_SITE_KEY, String(selectedSiteId));
  }, [selectedSiteId]);

  // Default to the first site, and fall back to it if the persisted id no
  // longer exists (deleted, or belongs to a different account). With no sites
  // at all, clear any stale selection so the app shows the first-run panel.
  useEffect(() => {
    if (!sites) return;
    if (sites.length === 0) {
      if (selectedSiteId !== null) setSelectedSiteId(null);
      return;
    }
    if (selectedSiteId === null || !sites.some((s) => s.id === selectedSiteId)) {
      setSelectedSiteId(sites[0].id);
    }
  }, [sites, selectedSiteId]);

  const selectSite = useCallback((id: number) => setSelectedSiteId(id), []);

  const createSite = useCallback(
    async (name: string, widgetOrigin?: string) => {
      const trimmedOrigin = widgetOrigin?.trim();
      const site = await apiCreateSite({
        name,
        ...(trimmedOrigin ? { widget_origin: trimmedOrigin } : {}),
      });
      await mutate();
      setSelectedSiteId(site.id);
      return site;
    },
    [mutate]
  );

  const renameSite = useCallback(
    async (id: number, name: string) => {
      // Optimistically rename in the list; rethrow on failure so the rename
      // dialog can surface the error inline (and the optimistic name rolls back).
      await mutate(
        async (list) => {
          await apiRenameSite(id, name);
          return list?.map((s) => (s.id === id ? { ...s, name } : s)) ?? [];
        },
        {
          optimisticData: (list) =>
            list?.map((s) => (s.id === id ? { ...s, name } : s)) ?? [],
          rollbackOnError: true,
          revalidate: true,
        }
      );
    },
    [mutate]
  );

  const deleteSite = useCallback(
    async (id: number) => {
      try {
        // Optimistically drop the site from the list. Server-side this cascades
        // to the site's conversations/knowledge/settings, so revalidate after.
        await mutate(
          async (list) => {
            await apiDeleteSite(id);
            return list?.filter((s) => s.id !== id) ?? [];
          },
          {
            optimisticData: (list) => list?.filter((s) => s.id !== id) ?? [],
            rollbackOnError: true,
            revalidate: true,
          }
        );
        setSelectedSiteId((prev) => {
          if (prev !== id) return prev;
          const remaining = sites?.filter((s) => s.id !== id) ?? [];
          return remaining.length ? remaining[0].id : null;
        });
      } catch {
        showToast("Couldn't delete the website. Restored.");
      }
    },
    [mutate, sites, showToast]
  );

  // Resolve against the loaded list, falling back to the first site - the same
  // site the default-selection effect above lands on one commit later. Without
  // the fallback there is a rendered frame (sites loaded, selectedSiteId still
  // null) where role-gated UI flashes owner-only items at team members.
  const current = sites?.find((s) => s.id === selectedSiteId) ?? sites?.[0];
  // An absent role (older API) means owner. While sites are still loading,
  // stay permissive so owner UI doesn't flicker away on every reload.
  const isOwner = current ? current.role !== "member" : true;
  const ownsAnySite =
    !sites || sites.length === 0 || sites.some((s) => s.role !== "member");

  return (
    <SiteContext.Provider
      value={{
        sites,
        selectedSiteId,
        current,
        isLoading: sites === undefined,
        isOwner,
        ownsAnySite,
        selectSite,
        createSite,
        renameSite,
        deleteSite,
      }}
    >
      {children}
    </SiteContext.Provider>
  );
}
