<template>
  <v-dialog
    width="500"
    :value="show"
    @input="emitChange"
  >
    <v-card>
      <v-card-title class="text-h5">
        {{ network.ssid }}
      </v-card-title>
      <v-card-text>
        <div
          v-for="(value, name) in connectionInfo"
          :key="name"
        >
          <span>{{ name }}: {{ value }}</span><br>
        </div>
      </v-card-text>
      <v-card-actions class="d-flex flex-column">
        <v-btn
          elevation="1"
          color="red darken-1"
          text
          @click="disconnectFromWifiNetwork"
        >
          Disconnect
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script lang="ts">
import Vue, { PropType } from 'vue'
import { getModule } from 'vuex-module-decorators'
import WifiStore from '@/store/wifi'
import { Network, WifiStatus } from '@/types/wifi'

const wifi = getModule(WifiStore)

export default Vue.extend({
  name: 'DisconnectionDialog',
  model: {
    prop: 'show',
    event: 'change',
  },
  props: {
    network: {
      type: Object as PropType<Network>,
      required: true,
    },
    status: {
      type: Object as PropType<WifiStatus>,
      required: true,
    },
    show: {
      type: Boolean,
      default: false,
    },
  },
  computed: {
    connectionInfo (): Network & WifiStatus {
      return {...this.network, ...this.status}
    },
  },
  methods: {
    disconnectFromWifiNetwork (): Promise<void> {
      this.emitChange(false)
      return wifi.disconnectFromWifiNetwork()
    },
    emitChange (state: boolean) {
      this.$emit('change', state)
    },
  },
})
</script>

<style>
</style>
