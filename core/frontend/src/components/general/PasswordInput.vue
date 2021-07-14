<template>
  <v-text-field
    @input="emitInput"
    @keyup.enter="emitSubmit"
    :value="value"
    :append-icon="show_password ? 'mdi-eye' : 'mdi-eye-off'"
    :type="show_password ? 'text' : 'password'"
    @click:append="show_password = !show_password"
    label="Password"
    hide-details="auto"
    class="pa-2"
  />
</template>

<script lang="ts">
import Vue from 'vue'

export default Vue.extend({
  name: 'PasswordInput',
  props: {
    value: {
      type: String,
      default: '',
    },
  },
  data () {
    return {
      show_password: '',
    }
  },
  methods: {
    emitInput (value: string) {
      this.$emit('input', value)
    },
    emitSubmit () {
      this.$emit('submit')
    },
  },
})
</script>

<style>
</style>
