<script setup lang="ts">
import { ref } from "vue";

defineProps<{ copied: boolean }>();
const emit = defineEmits<{ copy: [] }>();
const host = ref<HTMLElement | null>(null);
defineExpose({ host });
</script>

<template>
  <div class="terminal-wrap interactive-terminal">
    <button
      class="copy-output"
      type="button"
      :title="copied ? 'Скопировано' : 'Копировать терминал'"
      :aria-label="copied ? 'Скопировано' : 'Копировать терминал'"
      @click="emit('copy')"
    >{{ copied ? "✓" : "⧉" }}</button>
    <div ref="host" class="xterm-host"></div>
  </div>
</template>
