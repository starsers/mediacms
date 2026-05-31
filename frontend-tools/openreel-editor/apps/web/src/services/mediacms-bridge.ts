import { useProjectStore } from "../stores/project-store";

interface MediaCmsBridgeConfig {
  parentSource: string;
  childSource: string;
  initialHash: string;
  allowedOrigin?: string;
}

interface MediaCmsMediaPayload {
  url: string;
  title?: string;
  mediaType?: string;
  mimeType?: string;
}

interface MediaCmsImportMessage {
  source?: string;
  type?: string;
  requestId?: string;
  media?: MediaCmsMediaPayload;
}

declare global {
  interface Window {
    OPENREEL_HOST_CONFIG?: Partial<MediaCmsBridgeConfig>;
  }
}

const DEFAULT_CONFIG: MediaCmsBridgeConfig = {
  parentSource: "mediacms-clip",
  childSource: "openreel-bridge",
  initialHash: "#/editor",
};

let initialized = false;

function getConfig(): MediaCmsBridgeConfig {
  return {
    ...DEFAULT_CONFIG,
    ...(window.OPENREEL_HOST_CONFIG || {}),
  };
}

function postToParent(type: string, data: Record<string, unknown> = {}): void {
  const config = getConfig();

  if (!window.parent || window.parent === window) {
    return;
  }

  window.parent.postMessage(
    {
      source: config.childSource,
      type,
      ...data,
    },
    "*",
  );
}

function ensureEditorRoute(initialHash: string): void {
  const currentHash = window.location.hash || "";
  if (!currentHash || currentHash === "#/welcome" || currentHash === "#/") {
    window.location.hash = initialHash;
  }
}

function inferExtension(mediaType: string | undefined, mimeType: string): string {
  if (mediaType === "audio") return "mp3";
  if (mediaType === "image") return "png";
  if (mimeType.includes("webm")) return "webm";
  if (mimeType.includes("quicktime")) return "mov";
  if (mimeType.includes("mpeg")) return "mp3";
  if (mimeType.includes("wav")) return "wav";
  return "mp4";
}

function sanitizeFileName(media: MediaCmsMediaPayload, mimeType: string): string {
  const rawTitle = String(media.title || "mediacms-import").trim();
  const safeTitle = rawTitle
    .replace(/[\\/:*?"<>|]+/g, "-")
    .replace(/\s+/g, " ")
    .trim();

  if (/\.[a-z0-9]{2,6}$/i.test(safeTitle)) {
    return safeTitle;
  }

  const extension = inferExtension(media.mediaType, mimeType);
  return `${safeTitle || "mediacms-import"}.${extension}`;
}

async function importFromMediaCms(message: MediaCmsImportMessage): Promise<void> {
  const config = getConfig();
  const requestId = message.requestId || `mediacms-${Date.now()}`;
  const media = message.media;

  if (!media?.url) {
    postToParent("openreel:import-failed", {
      requestId,
      error: "Missing media URL",
    });
    return;
  }

  ensureEditorRoute(config.initialHash);

  postToParent("openreel:import-started", {
    requestId,
    title: media.title || "未命名素材",
    mediaType: media.mediaType || "video",
  });

  try {
    const response = await fetch(media.url, { credentials: "include" });
    if (!response.ok) {
      throw new Error(`Failed to fetch media (${response.status})`);
    }

    const blob = await response.blob();
    const mimeType = media.mimeType || blob.type || "application/octet-stream";
    const fileName = sanitizeFileName(media, mimeType);
    const file = new File([blob], fileName, { type: mimeType });

    const store = useProjectStore.getState();
    const importResult = await store.importMedia(file);

    if (!importResult.success || !importResult.actionId) {
      throw new Error(importResult.error?.message || "Failed to import media");
    }

    const clipResult = await store.addClipToNewTrack(importResult.actionId);
    if (!clipResult.success) {
      throw new Error(clipResult.error?.message || "Failed to add media to timeline");
    }

    postToParent("openreel:import-succeeded", {
      requestId,
      mediaId: importResult.actionId,
      title: fileName,
      mediaType: media.mediaType || "video",
    });
  } catch (error) {
    postToParent("openreel:import-failed", {
      requestId,
      title: media.title || "未命名素材",
      error: error instanceof Error ? error.message : "Unknown import error",
    });
  }
}

export function initializeMediaCmsBridge(): void {
  if (initialized || typeof window === "undefined") {
    return;
  }

  initialized = true;

  const config = getConfig();
  ensureEditorRoute(config.initialHash);

  window.addEventListener("message", (event: MessageEvent<MediaCmsImportMessage>) => {
    const config = getConfig();
    const payload = event.data;

    if (!payload || payload.source !== config.parentSource) {
      return;
    }

    if (config.allowedOrigin && event.origin !== config.allowedOrigin) {
      return;
    }

    if (payload.type === "mediacms:ping") {
      postToParent("openreel:ready", { hash: window.location.hash || "" });
      return;
    }

    if (payload.type === "mediacms:import-media") {
      void importFromMediaCms(payload);
    }
  });

  setTimeout(() => {
    postToParent("openreel:ready", { hash: window.location.hash || "" });
  }, 0);
}
