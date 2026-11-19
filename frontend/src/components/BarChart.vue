<script setup>
// Столбчатая диаграмма на SVG: ответы по дням, верные выделены цветом
import { computed } from 'vue'
import { num, shortDay } from '../lib/format'

const props = defineProps({ data: { type: Array, required: true } }) // [{day, answers, correct}]
const W = 640, H = 180, PAD = { l: 34, r: 8, t: 10, b: 24 }

const max = computed(() => Math.max(5, ...props.data.map((d) => d.answers)))
const bw = computed(() => (W - PAD.l - PAD.r) / props.data.length)
const y = (v) => PAD.t + (H - PAD.t - PAD.b) * (1 - v / max.value)
const ticks = computed(() => [0, Math.round(max.value / 2), max.value])
</script>

<template>
  <svg :viewBox="`0 0 ${W} ${H}`" width="100%" role="img" aria-label="Ответы учеников по дням">
    <g v-for="t in ticks" :key="t">
      <line :x1="PAD.l" :x2="W - PAD.r" :y1="y(t)" :y2="y(t)" stroke="var(--border)" />
      <text :x="PAD.l - 6" :y="y(t) + 4" text-anchor="end" font-size="10" fill="var(--muted)">{{ t }}</text>
    </g>
    <g v-for="(d, i) in data" :key="d.day">
      <title>{{ shortDay(d.day) }}: ответов {{ num(d.answers) }}, верных {{ num(d.correct) }}</title>
      <rect :x="PAD.l + i * bw + bw * 0.18" :y="y(d.answers)" :width="bw * 0.64"
            :height="Math.max(0, H - PAD.b - y(d.answers))" rx="3" fill="var(--accent-soft)" stroke="var(--accent)" stroke-opacity=".35" />
      <rect :x="PAD.l + i * bw + bw * 0.18" :y="y(d.correct)" :width="bw * 0.64"
            :height="Math.max(0, H - PAD.b - y(d.correct))" rx="3" fill="var(--accent)" />
      <text v-if="i % 2 === 0 || data.length < 8" :x="PAD.l + i * bw + bw / 2" :y="H - 6"
            text-anchor="middle" font-size="10" fill="var(--muted)">{{ shortDay(d.day) }}</text>
    </g>
  </svg>
</template>
