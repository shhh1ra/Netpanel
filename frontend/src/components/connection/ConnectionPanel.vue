<script setup lang="ts">
import { ref, type ComponentPublicInstance } from "vue";
import type { ConnectionForm, HostProfile } from "../../types/netpanel";

defineProps<{
  profiles: HostProfile[];
  isBusy: boolean;
  isConnected: boolean;
  backendRestarting: boolean;
}>();

const emit = defineEmits<{
  connect: [];
  disconnect: [];
  selectProfile: [];
  saveProfile: [];
  deleteProfile: [];
  restartBackend: [];
  passwordElement: [element: HTMLInputElement | null];
}>();

const apiBase = defineModel<string>("apiBase", { required: true });
const connection = defineModel<ConnectionForm>("connection", { required: true });
const selectedHostId = defineModel<string>("selectedHostId", { required: true });
const profileName = defineModel<string>("profileName", { required: true });
const rememberPassword = defineModel<boolean>("rememberPassword", { required: true });
const passwordField = ref<HTMLInputElement | null>(null);

function exposePasswordField(element: Element | ComponentPublicInstance | null) {
  const input = element instanceof HTMLInputElement ? element : null;
  passwordField.value = input;
  emit("passwordElement", input);
}

function setAuthType(authType: "password" | "key") {
  connection.value.authType = authType;
}
</script>

<template>
  <form class="panel" @submit.prevent="emit('connect')">
    <div class="panel-head">
      <h2>Подключение</h2>
      <span class="status" :class="{ online: isConnected }">{{ isConnected ? "online" : "offline" }}</span>
    </div>

    <div class="host-manager">
      <label>
        Профиль
        <select v-model="selectedHostId" :disabled="isBusy" @change="emit('selectProfile')">
          <option value="">Новый хост</option>
          <option v-for="profile in profiles" :key="profile.id" :value="profile.id">
            {{ profile.name }} — {{ profile.host }}
          </option>
        </select>
      </label>
      <label>
        Название
        <input v-model="profileName" placeholder="Например, SW1" autocomplete="off" />
      </label>
      <div class="host-actions">
        <button type="button" :disabled="!connection.host" @click="emit('saveProfile')">Сохранить</button>
        <button type="button" :disabled="!selectedHostId" @click="emit('deleteProfile')">Удалить</button>
      </div>
    </div>

    <label>
      API backend
      <input v-model="apiBase" autocomplete="off" />
    </label>
    <button class="backend-restart" type="button" :disabled="backendRestarting" @click="emit('restartBackend')">
      {{ backendRestarting ? "Рестарт backend..." : "Рестарт backend" }}
    </button>
    <div class="auth-mode">
      <span>Авторизация</span>
      <div class="segmented">
        <button
          type="button"
          :class="{ active: connection.authType === 'password' }"
          :disabled="isBusy"
          @click="setAuthType('password')"
        >
          Пароль
        </button>
        <button
          type="button"
          :class="{ active: connection.authType === 'key' }"
          :disabled="isBusy"
          @click="setAuthType('key')"
        >
          SSH-ключ
        </button>
      </div>
    </div>
    <label>
      Хост
      <input v-model="connection.host" placeholder="192.168.1.10" autocomplete="off" required />
    </label>
    <div class="grid two">
      <label>
        Порт
        <input v-model.number="connection.port" type="number" min="1" max="65535" required />
      </label>
      <label>
        Логин
        <input v-model="connection.username" autocomplete="username" required />
      </label>
    </div>
    <label v-if="connection.authType === 'key'">
      Путь к приватному ключу
      <input
        v-model="connection.keyPath"
        placeholder="C:\Users\name\.ssh\id_rsa"
        autocomplete="off"
        required
      />
    </label>
    <label>
      {{ connection.authType === "key" ? "Passphrase ключа" : "Пароль" }}
      <input
        :ref="exposePasswordField"
        v-model="connection.password"
        type="password"
        autocomplete="current-password"
        :required="connection.authType === 'password'"
      />
    </label>
    <label class="check">
      <input v-model="rememberPassword" type="checkbox" />
      {{ connection.authType === "key" ? "Сохранять passphrase в защищённом виде" : "Сохранять пароль в защищённом виде" }}
    </label>

    <div class="actions">
      <button class="primary" type="submit" :disabled="isBusy || isConnected">Подключиться</button>
      <button type="button" :disabled="isBusy || !isConnected" @click="emit('disconnect')">Отключиться</button>
    </div>
  </form>
</template>
