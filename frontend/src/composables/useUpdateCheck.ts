import { open } from "@tauri-apps/api/shell";
import { computed, ref } from "vue";
import packageInfo from "../../package.json";

type GitHubRelease = {
  html_url?: string;
  name?: string;
  tag_name?: string;
  prerelease?: boolean;
  draft?: boolean;
};

const RELEASE_API_URL = "https://api.github.com/repos/shhh1ra/Netpanel/releases/latest";
const RELEASES_URL = "https://github.com/shhh1ra/Netpanel/releases";
const CHECK_INTERVAL_MS = 30 * 60 * 1000;

export function useUpdateCheck() {
  const latestVersion = ref("");
  const releaseUrl = ref(RELEASES_URL);
  const isChecking = ref(false);
  const error = ref("");
  const dismissedUntil = ref(0);
  const currentVersion = packageInfo.version;
  let intervalId: ReturnType<typeof window.setInterval> | null = null;

  const hasUpdate = computed(() => {
    if (!latestVersion.value || Date.now() < dismissedUntil.value) return false;
    return compareVersions(latestVersion.value, currentVersion) > 0;
  });

  async function check() {
    isChecking.value = true;
    error.value = "";
    try {
      const response = await fetch(RELEASE_API_URL, {
        headers: { Accept: "application/vnd.github+json" },
      });
      if (!response.ok) throw new Error(response.statusText);
      const release = await response.json() as GitHubRelease;
      if (release.draft || release.prerelease) return;
      latestVersion.value = normalizeVersion(release.tag_name || release.name || "");
      releaseUrl.value = release.html_url || RELEASES_URL;
    } catch (cause) {
      error.value = cause instanceof Error ? cause.message : String(cause);
    } finally {
      isChecking.value = false;
    }
  }

  async function openRelease() {
    await open(releaseUrl.value);
  }

  function dismiss() {
    dismissedUntil.value = Date.now() + CHECK_INTERVAL_MS;
  }

  function startAutoCheck() {
    void check();
    if (intervalId) return;
    intervalId = window.setInterval(() => {
      void check();
      dismissedUntil.value = 0;
    }, CHECK_INTERVAL_MS);
  }

  function stopAutoCheck() {
    if (!intervalId) return;
    window.clearInterval(intervalId);
    intervalId = null;
  }

  return {
    currentVersion,
    latestVersion,
    hasUpdate,
    isChecking,
    error,
    check,
    startAutoCheck,
    stopAutoCheck,
    openRelease,
    dismiss,
  };
}

function normalizeVersion(value: string) {
  return value.trim().replace(/^v/i, "");
}

function compareVersions(left: string, right: string) {
  const leftParts = normalizeVersion(left).split(".").map(toVersionPart);
  const rightParts = normalizeVersion(right).split(".").map(toVersionPart);
  const length = Math.max(leftParts.length, rightParts.length);
  for (let index = 0; index < length; index += 1) {
    const diff = (leftParts[index] || 0) - (rightParts[index] || 0);
    if (diff !== 0) return diff;
  }
  return 0;
}

function toVersionPart(value: string) {
  const numeric = Number(value.replace(/\D.*/, ""));
  return Number.isFinite(numeric) ? numeric : 0;
}
