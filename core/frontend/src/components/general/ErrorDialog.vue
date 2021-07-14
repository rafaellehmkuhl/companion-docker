<template>
  <v-dialog 
    v-model="showDialog"
    v-slot="dialog"
    width="500"
    transition="dialog-bottom-transition"
  >
    <v-card>
      <v-card-title> Error </v-card-title>
      <v-card-text> {{ message }} </v-card-text>
      <v-card-actions>
        <v-spacer />
        <v-btn
          text
          @click="dialog.value = false"
        >
          Close
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script lang="ts">
import Vue from 'vue'
import { getModule } from 'vuex-module-decorators'
import GeneralStore from '@/store/general'

const general = getModule(GeneralStore)

export default Vue.extend({
  name: 'ErrorDialog',
  computed: {
    message (): string {
      return general.errorMessage
    },
    showDialog: {
      get (): boolean {
        return general.errorDialogState
      },
      set (value: boolean): void {
        general.setErrorDialog(value)
      },
    },
  },
})
</script>

<style>
</style>
