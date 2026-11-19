<script setup>
// Небольшой набор линейных иконок (24x24, stroke), чтобы не тянуть библиотеку
defineProps({ name: { type: String, required: true }, size: { type: Number, default: 18 } })

const paths = {
  home: 'M3 11l9-8 9 8M5 10v10h5v-6h4v6h5V10',
  book: 'M4 5a2 2 0 012-2h13v16H6a2 2 0 00-2 2V5zM4 19a2 2 0 012-2h13',
  gift: 'M20 12v9H4v-9M2 7h20v5H2zM12 21V7M12 7H8a2.5 2.5 0 110-5c2 0 4 5 4 5zm0 0h4a2.5 2.5 0 100-5c-2 0-4 5-4 5z',
  users: 'M16 21v-2a4 4 0 00-4-4H6a4 4 0 00-4 4v2M9 11a4 4 0 100-8 4 4 0 000 8zM22 21v-2a4 4 0 00-3-3.9M16 3.1a4 4 0 010 7.8',
  sliders: 'M4 21v-7M4 10V3M12 21v-9M12 8V3M20 21v-5M20 12V3M1 14h6M9 8h6M17 16h6',
  send: 'M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z',
  plus: 'M12 5v14M5 12h14',
  upload: 'M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4M17 8l-5-5-5 5M12 3v12',
  edit: 'M12 20h9M16.5 3.5a2.1 2.1 0 013 3L7 19l-4 1 1-4 12.5-12.5z',
  eye: 'M1 12s4-8 11-8 11 8 11 8-4 8-11 8S1 12 1 12zM12 15a3 3 0 100-6 3 3 0 000 6z',
  eyeoff: 'M17.9 17.9A10.1 10.1 0 0112 20C5 20 1 12 1 12a18.5 18.5 0 015.1-5.9M9.9 4.2A9.1 9.1 0 0112 4c7 0 11 8 11 8a18.5 18.5 0 01-2.2 3.2M1 1l22 22',
  play: 'M5 3l14 9-14 9V3z',
  mic: 'M12 1a3 3 0 00-3 3v8a3 3 0 006 0V4a3 3 0 00-3-3zM19 10v2a7 7 0 01-14 0v-2M12 19v4',
  logout: 'M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4M16 17l5-5-5-5M21 12H9',
  check: 'M20 6L9 17l-5-5',
  x: 'M18 6L6 18M6 6l12 12',
  copy: 'M9 9h11v11H9zM5 15H4a1 1 0 01-1-1V4a1 1 0 011-1h10a1 1 0 011 1v1',
  ban: 'M12 21a9 9 0 100-18 9 9 0 000 18zM5.6 5.6l12.8 12.8',
}
</script>

<template>
  <svg :width="size" :height="size" viewBox="0 0 24 24" fill="none" stroke="currentColor"
       stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
    <path :d="paths[name]" />
  </svg>
</template>
