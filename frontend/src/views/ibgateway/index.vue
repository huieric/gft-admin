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
    this.iframeSrc = 'http://3.137.88.155:6080/data/';
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
