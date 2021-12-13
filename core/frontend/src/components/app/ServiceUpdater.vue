<template>
  <span />
</template>

<script lang="ts">
import Vue, { PropType } from 'vue'

import { Fetcher } from '@/types/common'
import { callPeriodically } from '@/utils/helper_functions'

export default Vue.extend({
  name: 'ServiceUpdater',
  props: {
    fetchers: {
      type: [] as PropType<Fetcher[]>,
      required: true,
    },
  },
  mounted() {
    this.fetchers.forEach((fetcher) => {
      callPeriodically(fetcher.func, fetcher.delay)
    })
  },
})
</script>
