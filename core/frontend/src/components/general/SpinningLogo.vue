<template>
  <v-img
    class="lds-dual-ring"
    src="../../assets/logo.svg"
  />
</template>

<script lang="ts">
import Vue from 'vue'

export default Vue.extend({
  name: 'SpinningLogo',
})
</script>

<style>
  .lds-dual-ring {
    display: block;
    width: 80px;
    height: 80px;
    margin: 20px auto;
    animation-name: rotation360;
    animation-duration: 2s;
    animation-iteration-count: infinite;
  }
  @keyframes rotation360 {
    0% {
        transform: rotate(0deg);
    }
    100% {
        transform: rotate(360deg);
    }
  }
</style>
