import { invoke } from "@tauri-apps/api/tauri";
import { ref, type ComputedRef, type Ref } from "vue";
import type { ConnectionForm, HostProfile } from "../types/netpanel";

const STORAGE_KEY = "netpanel-hosts";

export function useProfiles(options: {
  connection: ConnectionForm;
  isConnected: ComputedRef<boolean>;
  connect: () => Promise<void>;
  disconnect: () => Promise<void>;
  focusPassword: () => Promise<void>;
}) {
  const profiles = ref<HostProfile[]>([]);
  const selectedId = ref("");
  const profileName = ref("");
  const rememberPassword = ref(true);

  function normalize(profile: Partial<HostProfile>): HostProfile {
    return {
      id: profile.id || `${Date.now()}`, name: profile.name || profile.host || "Cisco",
      host: profile.host || "", port: profile.port || 22, username: profile.username || "",
      password: profile.password || "", authType: profile.authType || "password", keyPath: profile.keyPath,
    };
  }

  async function load() {
    let legacy: Partial<HostProfile>[] = [];
    try { legacy = JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]"); }
    catch { localStorage.removeItem(STORAGE_KEY); }
    try {
      const stored = await invoke<HostProfile[] | null>("load_host_profiles");
      profiles.value = (stored ?? legacy).map(normalize);
      if (stored === null && profiles.value.length) await persist();
      localStorage.removeItem(STORAGE_KEY);
    } catch {
      profiles.value = legacy.map(normalize);
    }
  }

  async function persist() {
    try { await invoke("save_host_profiles", { profiles: profiles.value }); }
    catch {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(profiles.value.map((profile) => ({ ...profile, password: "" }))));
    }
  }

  async function select() {
    const profile = profiles.value.find((item) => item.id === selectedId.value);
    if (!profile) { profileName.value = ""; return; }
    const reconnect = options.isConnected.value;
    if (reconnect) await options.disconnect();
    profileName.value = profile.name;
    Object.assign(options.connection, {
      host: profile.host, port: profile.port, username: profile.username, password: profile.password,
    });
    rememberPassword.value = Boolean(profile.password);
    if (reconnect && profile.password) await options.connect();
    else if (!profile.password) await options.focusPassword();
  }

  function save() {
    if (!options.connection.host.trim()) return;
    const existing = profiles.value.find((item) => item.id === selectedId.value);
    const profile: HostProfile = {
      id: existing?.id || `${Date.now()}`, name: profileName.value.trim() || options.connection.host.trim(),
      host: options.connection.host.trim(), port: options.connection.port,
      username: options.connection.username.trim(),
      password: rememberPassword.value ? options.connection.password : "",
      authType: existing?.authType || "password", keyPath: existing?.keyPath,
    };
    if (existing) Object.assign(existing, profile);
    else { profiles.value.push(profile); selectedId.value = profile.id; }
    profileName.value = profile.name;
    void persist();
  }

  function remove() {
    if (!selectedId.value) return;
    profiles.value = profiles.value.filter((item) => item.id !== selectedId.value);
    selectedId.value = "";
    profileName.value = "";
    void persist();
  }

  return { profiles, selectedId, profileName, rememberPassword, load, select, save, remove };
}
