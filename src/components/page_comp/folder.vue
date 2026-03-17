<template>
<div class=" flex h-full">
    <div v-if="global.Folderlist.length==0" class=" flex justify-center flex-col items-center w-full">
      <v-progress-circular indeterminate :size="70" :width="6"></v-progress-circular>
      <span class=" text-sm mt-4 text-gray-500">Analyse en cours...</span>
    </div>
    <div v-else class=" overflow-auto h-full overflow-x-hidden">
        <div class="flex flex-col w-[30vw]" >
            <div v-for=" item,i in global.Folderlist" :key="i" class=" flex flex-col mb-3 cursor.pointer" @click="get_value(item)">
                <div class="flex flex-row justify-between items-center mb-4">
                    <div class=" flex flex-col">
                        <span class="mdi mdi-folder text-5xl  text-yellow-500"></span>
                        <span class="text-sm text-gray-500">{{ item.name }}</span>
                    </div>
                    <div class="  pr-14 flex flex-start w-[60%]">
                        <div class="w-[150px] ">
                            <v-progress-linear v-model="item.percent" color="green" height="20">
                                <template v-slot:default="{ value }" class=" ">
                                    <strong v-text="item.size_display " class=" text-xs"> </strong>
                                </template>
                            </v-progress-linear>
                        </div>
                        <span class=" text-xs ml-2">{{ item.percent }}%</span>
                    </div>
                </div>
            </div>
        </div>
    </div>
    <div class=" border-r border-gray-300 h-full "></div>
    <div class="flex w-[60vw]"></div>
</div>
</template>

<script setup>
import {
    ref,
    inject,
    onMounted
} from "vue"
const api = inject('api')
const fileList = ref([])
const URLFile = ref('')

import { useGlobalStore } from '@/stores/app'
const global = useGlobalStore()

async function  get_value(item){
    fileList.value= []
    global.Folderlist=  []
    // console.log(global.PartitionActual);
    URLFile.value += '\\' + item.name
    console.log(URLFile.value);


    const folderName = "Windows"
    const es = new EventSource(`${api}/api/analyseSubfile?folder_name=${encodeURIComponent(URLFile.value+'/')}`)

    es.onmessage = (event) => {
        const data = JSON.parse(event.data)
        // results.value.push(data)       // ← chaque dossier arrive au fur et à mesure
        // console.log(data)
        fileList.value.push(data)
    }

    es.onerror = () => {
        global.Folderlist = fileList.value
        console.log(global.Folderlist);

        console.log("Stream terminé")
        es.close()
    }
}



onMounted(() => {

    global.Folderlist=  []

    const es = new EventSource(`${api}/api/analyseSubfile?folder_name=${encodeURIComponent('C:\\')}`)
    URLFile.value = global.PartitionActual
    console.log(URLFile.value);

    es.onmessage = (event) => {
        const data = JSON.parse(event.data)
        // results.value.push(data)       // ← chaque dossier arrive au fur et à mesure
        // console.log(data)
        fileList.value.push(data)
    }

    es.onerror = () => {
        global.Folderlist = fileList.value
        console.log("Stream terminé")
        es.close()
    }
})
</script>

<style>

</style>
