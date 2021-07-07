<template>
  <v-card
    elevation="1"
    width="500"
  >
    <v-container>
      <v-container v-if="showLoading">
        <spinning-logo />
      </v-container>
      <v-container v-else>
        <network-card
          v-if="currentNetwork"
          class="connected-network"
          @click="openDisconnectionDialog()"
          :network="currentNetwork"
        />
        <network-card
          @click="openConnectionDialog(network)"
          class="available-network"
          v-for="(network, key) in networksToShow"
          :key="key"
          :network="network"
        />
        <v-row v-if="!areNetworksAvailable">
          <v-col
            :cols="12"
            class="d-flex flex-justify-center flex-align-center"
          >
            No wifi networks available.
          </v-col>
        </v-row>
      </v-container>
    </v-container>
    <connection-dialog
      v-if="selected_network"
      v-model="show_connection_dialog"
      :network="selected_network" 
    />
    <disconnection-dialog
      v-if="currentNetwork"
      v-model="show_disconnection_dialog"
      :network="currentNetwork"
    />
    <error-dialog />
  </v-card>
</template>

<script lang="ts">
import Vue from 'vue'
import { getModule } from 'vuex-module-decorators'
import WifiStore from '@/store/wifi'
import ConnectionDialog from './ConnectionDialog.vue'
import DisconnectionDialog from './DisconnectionDialog.vue'
import NetworkCard from './NetworkCard.vue'
import SpinningLogo from '../general/SpinningLogo.vue'
import ErrorDialog from '../general/ErrorDialog.vue'
import { Network } from '@/types/wifi'

const wifi = getModule(WifiStore)

export default Vue.extend({
  name: 'WifiManager',
  components: {
    NetworkCard,
    SpinningLogo,
    ConnectionDialog,
    DisconnectionDialog,
    ErrorDialog,
  },
  data () {
    return {
      selected_network: null as Network | null,
      show_connection_dialog: false,
      show_disconnection_dialog: false,
    }
  },
  computed: {
    areNetworksAvailable (): boolean {
      return wifi.available_wifi_networks.length === 0 ? false : true
    },
    showLoading (): boolean {
      if (wifi.wifi_network_status === 'SCANNING' && !this.areNetworksAvailable) {
        return true
      }
      return ['COMPLETED', 'DISCONNECTED'].includes(wifi.wifi_network_status) ? false : true
    },
    currentNetwork (): Network | null {
      return wifi.current_wifi_network
    },
    networkStatus (): string {
      return wifi.wifi_network_status
    },
    networksToShow (): Network[] {
      let showable_networks = wifi.available_wifi_networks
      const current_network = wifi.current_wifi_network
      if (current_network) {
        showable_networks = showable_networks.filter((network: Network) => network.ssid != current_network.ssid)
      }
      return showable_networks.sort((a: Network, b: Network) => b.signal - a.signal)
    },
  },
  methods: {
    openConnectionDialog (network: Network): void {
      this.selected_network = network
      this.show_connection_dialog = true
    },
    openDisconnectionDialog (): void {
      this.show_disconnection_dialog = true
    },
  },
})
</script>

<style>
  .connected-network {
      background-color: #2799D2
  }

  .connected-network:hover {
      cursor: pointer;
  }

  .available-network {
      background-color: #f8f8f8;
  }

  .available-network:hover {
      cursor: pointer;
      background-color: #c5c5c5;
  }

  .disabled {
      cursor: not-allowed;
  }
</style>
