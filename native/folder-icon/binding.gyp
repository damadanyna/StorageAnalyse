{
  "targets": [
    {
      "target_name": "folder_icon",
      "sources": [ "src/icon.cc" ],
      "include_dirs": [
        "<!@(node -p \"require('node-addon-api').include\")"
      ],
      "dependencies": [
        "<!(node -p \"require('node-addon-api').gyp\")"
      ],
      "defines": [ "NAPI_VERSION=8" ],
      "libraries": [ "shell32.lib", "ole32.lib", "gdiplus.lib", "gdi32.lib", "uuid.lib" ],
      "msvs_settings": {
        "VCCLCompilerTool": { "ExceptionHandling": 1 }
      }
    }
  ]
}
