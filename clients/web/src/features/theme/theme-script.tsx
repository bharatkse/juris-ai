import { DEFAULT_THEME, THEME_STORAGE_KEY } from "@/config/theme";

export function themeBlockingScript(
  storageKey = THEME_STORAGE_KEY,
  fallback = DEFAULT_THEME,
): string {
  return `(function(){try{var k=${JSON.stringify(storageKey)};var f=${JSON.stringify(fallback)};var v=localStorage.getItem(k);var t=(v==="light"||v==="dark")?v:f;if(v&&v!==t){localStorage.setItem(k,t);}var d=document.documentElement;d.classList.remove("light","dark");d.classList.add(t);d.style.colorScheme=t;}catch(e){document.documentElement.classList.add(${JSON.stringify(fallback)});}})();`;
}

export function ThemeScript() {
  return (
    <script
      dangerouslySetInnerHTML={{ __html: themeBlockingScript() }}
    />
  );
}
