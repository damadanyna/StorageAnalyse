<template>
<div id="bg_img" class="    w-full flex flex-row justify-end items-center h-full">

    <div class="flex justify-end flex-row sm:px-24 sm:w-[80vw] ">
        <div class="  sm:w-[50%] pa-12 " >
            <div class=" mb-10">
                <span class=" text-cyan-400 text-3xl font-bold">Login</span>
            </div>
            <v-text-field v-for="item,i in user_form" :key="i" :label="item.title" v-model="item.field" variant="outlined" :prepend-inner-icon="item.icon"></v-text-field>

            <div class="flex flex-col">
                <v-btn :loading="loading" class="flex-grow-1" height="48" variant="tonal" @click="load">
                    Se Connecter
                </v-btn>
                <div class=" flex justify-end items-center mt-4  ">
                Vous n'avez pas de compte
                <button @click="inscription_rout()" variant=" outlined" class=" ml-3 underline text-cyan-500" >
                  S'inscrire
                </button>
                </div>

            </div>

        </div>
    </div>
</div>
</template>

<script setup>
import {
    ref,
} from 'vue'

import { useRouter } from 'vue-router'

const router = useRouter()
const user_form = ref(
    [{
            field: "",
            title: "Email adress",
            type: "email",
            icon: "mdi-email"

        },
        {
            field: "",
            title: "Password",
            type: "password",
            icon: "mdi-lock"

        }
    ]
)

const loading = ref(false)
const load = () => {
    loading.value = true
    setTimeout(() => (loading.value = false), 3000)
}
const inscription_rout = () => {
  router.push('signup')

}
</script>

<style scoped>
#bg_img {
    background-image: url("../../../public/img/bg.jpg");
    background-size: cover;
}
</style>
