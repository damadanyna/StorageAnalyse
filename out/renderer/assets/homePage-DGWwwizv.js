import { i as defineStore, j as inject, o as onMounted, d as ref, c as createElementBlock, a as openBlock, b as createBaseVNode, k as unref, e as createVNode, l as VProgressCircular, F as Fragment, r as renderList, t as toDisplayString, w as withCtx, m as VProgressLinear, n as resolveComponent } from "./index-DdbfV3Ea.js";
const useGlobalStore = defineStore("global", {
  state: () => ({
    Folderlist: [],
    PartitionActual: null
  })
});
const _hoisted_1$1 = { class: "flex h-full" };
const _hoisted_2$1 = {
  key: 0,
  class: "flex justify-center flex-col items-center w-full"
};
const _hoisted_3 = {
  key: 1,
  class: "overflow-auto h-full overflow-x-hidden"
};
const _hoisted_4 = { class: "flex flex-col w-[30vw]" };
const _hoisted_5 = ["onClick"];
const _hoisted_6 = { class: "flex flex-row justify-between items-center mb-4" };
const _hoisted_7 = { class: "flex flex-col" };
const _hoisted_8 = { class: "text-sm text-gray-500" };
const _hoisted_9 = { class: "pr-14 flex flex-start w-[60%]" };
const _hoisted_10 = { class: "w-[150px]" };
const _hoisted_11 = ["textContent"];
const _hoisted_12 = { class: "text-xs ml-2" };
const _sfc_main$1 = {
  __name: "folder",
  setup(__props) {
    const api = inject("api");
    const fileList = ref([]);
    const URLFile = ref("");
    const global = useGlobalStore();
    async function get_value(item) {
      fileList.value = [];
      global.Folderlist = [];
      URLFile.value += "\\" + item.name;
      console.log(URLFile.value);
      const es = new EventSource(`${api}/api/analyseSubfile?folder_name=${encodeURIComponent(URLFile.value + "/")}`);
      es.onmessage = (event) => {
        const data = JSON.parse(event.data);
        fileList.value.push(data);
      };
      es.onerror = () => {
        global.Folderlist = fileList.value;
        console.log(global.Folderlist);
        console.log("Stream terminé");
        es.close();
      };
    }
    onMounted(() => {
      global.Folderlist = [];
      const es = new EventSource(`${api}/api/analyseSubfile?folder_name=${encodeURIComponent("C:\\")}`);
      URLFile.value = global.PartitionActual;
      console.log(URLFile.value);
      es.onmessage = (event) => {
        const data = JSON.parse(event.data);
        fileList.value.push(data);
      };
      es.onerror = () => {
        global.Folderlist = fileList.value;
        console.log("Stream terminé");
        es.close();
      };
    });
    return (_ctx, _cache) => {
      return openBlock(), createElementBlock("div", _hoisted_1$1, [
        unref(global).Folderlist.length == 0 ? (openBlock(), createElementBlock("div", _hoisted_2$1, [
          createVNode(VProgressCircular, {
            indeterminate: "",
            size: 70,
            width: 6
          }),
          _cache[0] || (_cache[0] = createBaseVNode("span", { class: "text-sm mt-4 text-gray-500" }, "Analyse en cours...", -1))
        ])) : (openBlock(), createElementBlock("div", _hoisted_3, [
          createBaseVNode("div", _hoisted_4, [
            (openBlock(true), createElementBlock(Fragment, null, renderList(unref(global).Folderlist, (item, i) => {
              return openBlock(), createElementBlock("div", {
                key: i,
                class: "flex flex-col mb-3 cursor.pointer",
                onClick: ($event) => get_value(item)
              }, [
                createBaseVNode("div", _hoisted_6, [
                  createBaseVNode("div", _hoisted_7, [
                    _cache[1] || (_cache[1] = createBaseVNode("span", { class: "mdi mdi-folder text-5xl text-yellow-500" }, null, -1)),
                    createBaseVNode("span", _hoisted_8, toDisplayString(item.name), 1)
                  ]),
                  createBaseVNode("div", _hoisted_9, [
                    createBaseVNode("div", _hoisted_10, [
                      createVNode(VProgressLinear, {
                        modelValue: item.percent,
                        "onUpdate:modelValue": ($event) => item.percent = $event,
                        color: "green",
                        height: "20"
                      }, {
                        default: withCtx(({ value }) => [
                          createBaseVNode("strong", {
                            textContent: toDisplayString(item.size_display),
                            class: "text-xs"
                          }, null, 8, _hoisted_11)
                        ]),
                        _: 2
                      }, 1032, ["modelValue", "onUpdate:modelValue"])
                    ]),
                    createBaseVNode("span", _hoisted_12, toDisplayString(item.percent) + "%", 1)
                  ])
                ])
              ], 8, _hoisted_5);
            }), 128))
          ])
        ])),
        _cache[2] || (_cache[2] = createBaseVNode("div", { class: "border-r border-gray-300 h-full" }, null, -1)),
        _cache[3] || (_cache[3] = createBaseVNode("div", { class: "flex w-[60vw]" }, null, -1))
      ]);
    };
  }
};
const _hoisted_1 = { class: "flex h-screen" };
const _hoisted_2 = { class: "flex-1 p-4" };
const _sfc_main = {
  __name: "homePage",
  setup(__props) {
    return (_ctx, _cache) => {
      const _component_nav_bar = resolveComponent("nav-bar");
      return openBlock(), createElementBlock("div", _hoisted_1, [
        createVNode(_component_nav_bar),
        createBaseVNode("div", _hoisted_2, [
          createVNode(_sfc_main$1)
        ])
      ]);
    };
  }
};
export {
  _sfc_main as default
};
