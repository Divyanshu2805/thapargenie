// Applies the saved theme before first paint, so light mode never flashes dark.
// Kept as a file (not inline) so the CSP can stay script-src 'self'.
(function () {
  // Dark unless the visitor chose light (see components/theme-provider.jsx).
  var dark = true;
  try {
    dark = localStorage.getItem('thapargenie-theme') !== 'light';
  } catch {
    // Storage can be blocked; stay on the default.
  }
  document.documentElement.classList.toggle('dark', dark);
  document.documentElement.style.colorScheme = dark ? 'dark' : 'light';
})();
