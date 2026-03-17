<template>

  <div class=" flex items-center justify-center h-full">
    chargement ....
  </div>

</template>

<script setup>

import { useRouter } from 'vue-router'
import {
    ref,
} from 'vue'


const router = useRouter()
  //
  onMounted(() => {
    router.replace('/diskAnalize/homePage')
  })
</script>



