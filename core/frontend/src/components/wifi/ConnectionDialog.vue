<template>
  <v-dialog
    width="400"
    :value="show"
    @input="emitChange"
  >
    <v-card>
      <v-card-title>{{ network.ssid }}</v-card-title>
      <v-card-text>
        <div
          v-for="(value, name) in network"
          :key="name"
        >
          <span>{{ name }}: {{ value }}</span><br>
        </div>
      </v-card-text>
      <v-card-actions class="d-flex flex-column">
        <v-row>
          <v-card
            v-if="!showPasswordInputBox"
            elevation="0"
            @click="forcePassword = !forcePassword"
          >
            <v-card-text>
              <div>
                Force new password
              </div>
            </v-card-text>
          </v-card>
          <password-input
            v-if="showPasswordInputBox"
            v-model="password"
            @submit="connectToWifiNetwork"
          />
        </v-row>
        <v-row>
          <v-col cols="6">
            <v-btn
              color="#2c99ce"
              depressed
              @click="connectToWifiNetwork"
            >
              Connect
            </v-btn>
          </v-col>
          <v-col cols="6">
            <v-btn
              v-if="network.saved"
              color="#EF5350"
              depressed
              @click="removeSavedWifiNetwork"
            >
              Forget
            </v-btn>
          </v-col>
        </v-row>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script lang="ts">
import Vue, { PropType } from 'vue'
import { getModule } from 'vuex-module-decorators'
import WifiStore from '@/store/wifi'
import PasswordInput from '../general/PasswordInput.vue'
import { Network } from '@/types/wifi'

const wifi = getModule(WifiStore)

export default Vue.extend({
  name: 'ConnectionDialog',
  model: {
    prop: 'show',
    event: 'change',
  },
  data () {
    return {
      password: '',
      forcePassword: false,
    }
  },
  props: {
    network:  {
      type: Object as PropType<Network>,
      required: true,
    },
    show: {
      type: Boolean,
      default: false,
    },
  },
  computed: {
    showPasswordInputBox (): boolean {
      if (this.forcePassword) {
        return true
      }
      if (this.network.saved) {
        return false
      }
      if (!this.network.locked) {
        return false
      }
      return true
    },
  },
  components: {
    PasswordInput,
  },
  methods: {
    connectToWifiNetwork (): Promise<void> {
      const password = this.password
      this.password = ''
      this.emitChange(false)
      return wifi.connectToWifiNetwork({
        ssid: this.network.ssid,
        password,
      })
    },
    removeSavedWifiNetwork (): Promise<void> {
      this.emitChange(false)
      return wifi.removeSavedWifiNetwork(this.network.ssid)
    },
    emitChange (state: boolean) {
      this.$emit('change', state)
    },
  },
})
</script>

<style>
html{
  overflow-y: auto;
}
</style>
