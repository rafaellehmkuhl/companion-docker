<template>
  <span />
</template>

<script lang="ts">
import Vue from 'vue'
import { getModule } from 'vuex-module-decorators'
import WifiStore from '@/store/wifi'

const wifi = getModule(WifiStore)

export default Vue.extend({
  name: 'WifiUpdater',
  async mounted () {
    await this.updateStatus()
    await this.scanForNetworks()
  },
  methods: {
    async updateStatus (): Promise<void> {
      await wifi.updateWifiNetworkStatus()
      await this.sleep(1000)
      this.updateStatus()
    },
    async scanForNetworks (): Promise<void> {
      await wifi.scanAvailableWifiNetworks()
      await this.sleep(1000)
      this.scanForNetworks()
    },
    sleep (ms: number): Promise<void> {
      return new Promise((resolve) => setTimeout(resolve, ms))
    },
  },
})
</script>
