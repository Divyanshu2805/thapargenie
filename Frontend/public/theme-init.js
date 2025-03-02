// Applies the saved theme before first paint, so dark mode never flashes light.
// Kept as a file (not inline) so the CSP can stay script-src 'self'.
(function () {
  var theme = 'system';
  try {
    theme = localStorage.getItem('thapargpt-theme') || 'system';
  } catch {
    // Storage can be blocked; fall back to the system preference.
  }
  var dark = theme === 'dark' || (theme === 'system' && matchMedia('(prefers-color-scheme: dark)').matches);
  document.documentElement.classList.toggle('dark', dark);
  document.documentElement.style.colorScheme = dark ? 'dark' : 'light';
})();
