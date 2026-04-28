import { u as useRouter, o as onMounted, c as createElementBlock, a as openBlock } from "./index-BiNo5Db0.js";
const _hoisted_1 = { class: "flex items-center justify-center h-full" };
const _sfc_main = {
  __name: "index",
  setup(__props) {
    const router = useRouter();
    onMounted(() => {
      router.replace("/diskAnalize/homePage");
    });
    return (_ctx, _cache) => {
      return openBlock(), createElementBlock("div", _hoisted_1, " chargement .... ");
    };
  }
};
export {
  _sfc_main as default
};
