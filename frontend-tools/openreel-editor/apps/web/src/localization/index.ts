import { messages, translateText } from "./zh-CN";

type MessageKey = keyof typeof messages;

type Params = Record<string, string | number>;

export function t(key: MessageKey, params?: Params): string {
  let value: string = messages[key] ?? key;
  if (!params) return value;

  for (const [paramKey, paramValue] of Object.entries(params)) {
    value = value.replaceAll(`{${paramKey}}`, String(paramValue));
  }

  return value;
}

function translateNode(node: Node): void {
  if (node.nodeType === Node.TEXT_NODE) {
    const text = node.textContent ?? "";
    const translated = translateText(text);
    if (translated !== text) {
      node.textContent = translated;
    }
    return;
  }

  if (node.nodeType !== Node.ELEMENT_NODE) return;

  const element = node as HTMLElement;
  const textTagsToSkip = new Set(["SCRIPT", "STYLE", "CODE", "PRE"]);
  const attrsToTranslate = ["title", "placeholder", "aria-label"];

  for (const attr of attrsToTranslate) {
    const current = element.getAttribute(attr);
    if (!current) continue;
    const translated = translateText(current);
    if (translated !== current) {
      element.setAttribute(attr, translated);
    }
  }

  if (textTagsToSkip.has(element.tagName)) {
    return;
  }

  element.childNodes.forEach(translateNode);
}

export function localizeDocument(root: ParentNode = document): void {
  root.childNodes.forEach(translateNode);
}

export function observeAndLocalize(root: ParentNode = document.body): MutationObserver | null {
  if (typeof MutationObserver === "undefined" || !(root instanceof Node)) {
    return null;
  }

  localizeDocument(root);

  const observer = new MutationObserver((mutations) => {
    mutations.forEach((mutation) => {
      if (mutation.type === "characterData") {
        if (mutation.target.parentNode) {
          translateNode(mutation.target);
        }
        return;
      }

      if (mutation.type === "attributes") {
        if (mutation.target instanceof Node) {
          translateNode(mutation.target);
        }
        return;
      }

      mutation.addedNodes.forEach((addedNode) => {
        translateNode(addedNode);
      });
    });
  });

  observer.observe(root, {
    subtree: true,
    childList: true,
    characterData: true,
    attributes: true,
    attributeFilter: ["title", "placeholder", "aria-label"],
  });

  return observer;
}
