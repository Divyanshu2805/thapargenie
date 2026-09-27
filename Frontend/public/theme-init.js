// Applies the saved theme before first paint, so dark mode never flashes light.
// Kept as a file (not inline) so the CSP can stay script-src 'self'.
(function () {
  var dark;
  try {
    var stored = localStorage.getItem('thapargenie-theme');
    dark = stored === 'dark' || (stored !== 'light' && matchMedia('(prefers-color-scheme: dark)').matches);
  } catch {
    // Storage can be blocked; fall back to the system preference.
    dark = matchMedia('(prefers-color-scheme: dark)').matches;
  }
  document.documentElement.classList.toggle('dark', dark);
  document.documentElement.style.colorScheme = dark ? 'dark' : 'light';
})();
