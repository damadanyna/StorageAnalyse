import { _ as _export_sfc, u as useRouter, c as createElementBlock, a as openBlock, b as createBaseVNode, F as Fragment, r as renderList, d as ref, e as createVNode, w as withCtx, f as createTextVNode, V as VBtn, g as createBlock, h as VTextField } from "./index-IoOG4OA_.js";
const _hoisted_1 = { class: "flex justify-end flex-row sm:px-24 sm:w-[80vw]" };
const _hoisted_2 = { class: "sm:w-[50%] pa-12" };
const _hoisted_3 = { class: "flex flex-col" };
const _hoisted_4 = { class: "flex justify-end items-center mt-4" };
const _sfc_main = {
  __name: "signin",
  setup(__props) {
    const router = useRouter();
    const backgroundImageUrl = new URL("" + new URL("bg-DqZvsW4T.jpg", import.meta.url).href, import.meta.url).href;
    const backgroundStyle = {
      backgroundImage: `url("${backgroundImageUrl}")`
    };
    const user_form = ref(
      [
        {
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
    );
    const loading = ref(false);
    const load = () => {
      loading.value = true;
      setTimeout(() => loading.value = false, 3e3);
    };
    const inscription_rout = () => {
      router.push("signup");
    };
    return (_ctx, _cache) => {
      return openBlock(), createElementBlock("div", {
        id: "bg_img",
        style: backgroundStyle,
        class: "w-full flex flex-row justify-end items-center h-full"
      }, [
        createBaseVNode("div", _hoisted_1, [
          createBaseVNode("div", _hoisted_2, [
            _cache[3] || (_cache[3] = createBaseVNode("div", { class: "mb-10" }, [
              createBaseVNode("span", { class: "text-cyan-400 text-3xl font-bold" }, "Login")
            ], -1)),
            (openBlock(true), createElementBlock(Fragment, null, renderList(user_form.value, (item, i) => {
              return openBlock(), createBlock(VTextField, {
                key: i,
                label: item.title,
                modelValue: item.field,
                "onUpdate:modelValue": ($event) => item.field = $event,
                variant: "outlined",
                "prepend-inner-icon": item.icon
              }, null, 8, ["label", "modelValue", "onUpdate:modelValue", "prepend-inner-icon"]);
            }), 128)),
            createBaseVNode("div", _hoisted_3, [
              createVNode(VBtn, {
                loading: loading.value,
                class: "flex-grow-1",
                height: "48",
                variant: "tonal",
                onClick: load
              }, {
                default: withCtx(() => [..._cache[1] || (_cache[1] = [
                  createTextVNode(" Se Connecter ", -1)
                ])]),
                _: 1
              }, 8, ["loading"]),
              createBaseVNode("div", _hoisted_4, [
                _cache[2] || (_cache[2] = createTextVNode(" Vous n'avez pas de compte ", -1)),
                createBaseVNode("button", {
                  onClick: _cache[0] || (_cache[0] = ($event) => inscription_rout()),
                  variant: " outlined",
                  class: "ml-3 underline text-cyan-500"
                }, " S'inscrire ")
              ])
            ])
          ])
        ])
      ]);
    };
  }
};
const signin = /* @__PURE__ */ _export_sfc(_sfc_main, [["__scopeId", "data-v-4cf4d52e"]]);
export {
  signin as default
};
