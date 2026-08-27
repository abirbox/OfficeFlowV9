import { create } from 'zustand';

// Which workspace the user is currently viewing: 'employee' | 'dispatch' | null.
// Persisted so a refresh keeps the chosen panel; cleared on logout so the
// selection popup shows again on the next login.
const KEY = 'officeflow_portal';

const usePortalStore = create((set) => ({
  portal: (typeof localStorage !== 'undefined' && localStorage.getItem(KEY)) || null,
  setPortal: (p) => {
    try { localStorage.setItem(KEY, p); } catch (e) { /* ignore */ }
    set({ portal: p });
  },
  clearPortal: () => {
    try { localStorage.removeItem(KEY); } catch (e) { /* ignore */ }
    set({ portal: null });
  },
}));

export default usePortalStore;
