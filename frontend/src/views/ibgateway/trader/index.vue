<template>
  <div class="ibgateway">
    <iframe
      v-if="iframeSrc"
      :src="iframeSrc"
      width="100%"
      height="100%"
    ></iframe>
  </div>
</template>

<script>
export default {
  data() {
    return {
      iframeSrc: null
    };
  },
  mounted() {
    this.iframeSrc = 'http://trader-ibkr:6080/';
  }
}
</script>

<style>
.ibgateway {
  padding: 20px;
  height: 95vh;
  text-align: center;
}
</style>
