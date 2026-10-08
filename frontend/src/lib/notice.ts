/** Browser helpers for the parent notice: Hindi font, notice-only printing, clipboard. */

const DEVANAGARI_FONT_URL =
  "https://fonts.googleapis.com/css2?family=Noto+Sans+Devanagari:wght@400;600&display=swap";

/** Load the full Noto Sans Devanagari once, only when Hindi is used (index.html loads a wordmark subset). */
export function ensureDevanagariFont(doc: Document = document): void {
  if (doc.querySelector('link[data-font="noto-sans-devanagari"]')) return;
  const link = doc.createElement("link");
  link.rel = "stylesheet";
  link.href = DEVANAGARI_FONT_URL;
  link.dataset.font = "noto-sans-devanagari";
  doc.head.appendChild(link);
}

export const PRINT_CLASS = "print-notice";

/** Print only the [data-print-notice] copy of the notice (see index.css). */
export function printNotice(win: Window = window): void {
  const body = win.document.body;
  const done = () => {
    body.classList.remove(PRINT_CLASS);
    win.removeEventListener("afterprint", done);
  };
  body.classList.add(PRINT_CLASS);
  win.addEventListener("afterprint", done);
  win.print();
}

/** Copy text; false when the Clipboard API is missing or refused (caller offers a fallback). */
export async function copyText(text: string, nav: Navigator = navigator): Promise<boolean> {
  try {
    if (!nav.clipboard?.writeText) return false;
    await nav.clipboard.writeText(text);
    return true;
  } catch {
    return false;
  }
}

/** Select an element's text so the user can copy it by hand. */
export function selectContents(element: HTMLElement | null): void {
  const selection = element ? window.getSelection() : null;
  if (element && selection) selection.selectAllChildren(element);
}

export function canWebShare(nav: Navigator = navigator): boolean {
  return typeof nav.share === "function";
}
