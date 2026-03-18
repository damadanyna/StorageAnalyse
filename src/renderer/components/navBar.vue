<template>
   <v-navigation-drawer permanent>
  <v-list-item title="Disk Analizer" subtitle="Banay"></v-list-item>
  <v-divider></v-divider>
    <div class="mt-4"></div>
  <v-list density="compact" nav>
        <v-list-item v-for="item in storageInfo" :key="item.to" :to="item.to" color="green-accent-3" class="mt-3 cursor-pointer" @click="get_value(item)">  >
            <template #title>
                <div class="flex ">
                  {{ item.partition }}
                  <span class="text-sm text-gray-500 ml-2">{{ item.free_GB }} Go sur </span>
                  <span class="text-sm text-gray-500 ml-2">{{ item.total_GB }} Go</span>
                 </div>
                <div class=" flex ">
                    <v-progress-linear v-model="item.percentage" color="amber" height="12">
                        <template v-slot:default="{ value }">
                          <strong class=" text-xs">{{ Math.ceil(item.used_GB*100/item.total_GB) }}%</strong>
                        </template>
                    </v-progress-linear>
                </div>
            </template>
        </v-list-item>
    </v-list>

  <div></div>


</v-navigation-drawer>
</template>

<script setup>
import { ref,inject,onMounted } from "vue"
import { watch } from 'vue'
import { useGlobalStore } from '@/stores/app'
const global = useGlobalStore()
const api = inject('api')
const storageInfo = ref([])
const fileList = ref([])

async function  get_value(item){
    global.PartitionActual= item.partition
    // global.Folderlist=  []
    const folderName = "Windows"
    const es = new EventSource(`${api}/api/analyseSubfile?folder_name=${encodeURIComponent(item.partition)}`)

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
}


onMounted( async () => {
 global.Folderlist=  []
  const response = await fetch(`${api}/api/listpart`, {
        method: "get",
      });
      var temp_data = await response.json();
      for (let i = 0; i < temp_data.length; i++) {
          temp_data[i]['percentage'] = Math.ceil(temp_data[i].used_GB * 100 / temp_data[i].total_GB);
        }
      storageInfo.value = temp_data
})

watch(
  () => global.Folderlist,
  (newValue, oldValue) => {
    console.log('folderList a changé :', newValue)
  },
  { deep: true } // important si c'est un tableau ou objet
)


</script>

<style>

</style>
