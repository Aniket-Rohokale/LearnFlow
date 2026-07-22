// Sync the Supabase access token to extension storage whenever this page has one.
// supabase-js v2 stores the session under "sb-<project-ref>-auth-token".
(function syncToken() {
  for (let i = 0; i < localStorage.length; i++) {
    const key = localStorage.key(i);
    if (key?.startsWith('sb-') && key.endsWith('-auth-token')) {
      try {
        const token = JSON.parse(localStorage.getItem(key))?.access_token;
        if (token) chrome.storage.local.set({ token });
      } catch { /* ignore parse errors */ }
      break;
    }
  }
})();
