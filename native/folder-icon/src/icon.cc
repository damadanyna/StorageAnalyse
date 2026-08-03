#include <napi.h>
#include <windows.h>
#include <shellapi.h>
#include <shlobj.h>
#include <commoncontrols.h>
#include <gdiplus.h>
#include <vector>
#include <string>

using namespace Gdiplus;

namespace {

bool GetEncoderClsid(const WCHAR* format, CLSID* clsid) {
  UINT num = 0;
  UINT size = 0;
  GetImageEncodersSize(&num, &size);
  if (size == 0) return false;

  std::vector<BYTE> buffer(size);
  ImageCodecInfo* codecInfo = reinterpret_cast<ImageCodecInfo*>(buffer.data());
  GetImageEncoders(num, size, codecInfo);

  for (UINT i = 0; i < num; i++) {
    if (wcscmp(codecInfo[i].MimeType, format) == 0) {
      *clsid = codecInfo[i].Clsid;
      return true;
    }
  }
  return false;
}

std::wstring Utf8ToWide(const std::string& utf8) {
  if (utf8.empty()) return std::wstring();
  int wlen = MultiByteToWideChar(CP_UTF8, 0, utf8.c_str(), -1, nullptr, 0);
  std::wstring wide(wlen > 0 ? wlen - 1 : 0, 0);
  if (wlen > 0) {
    MultiByteToWideChar(CP_UTF8, 0, utf8.c_str(), -1, &wide[0], wlen);
  }
  return wide;
}

// Runs the Shell/GDI+ icon extraction off the JS thread. Each worker thread
// needs its own COM apartment, since IImageList is a COM interface.
class JumboIconWorker : public Napi::AsyncWorker {
 public:
  JumboIconWorker(Napi::Env env, std::wstring path, int size)
      : Napi::AsyncWorker(env),
        path_(std::move(path)),
        size_(size),
        deferred_(Napi::Promise::Deferred::New(env)) {}

  Napi::Promise GetPromise() { return deferred_.Promise(); }

 protected:
  void Execute() override {
    HRESULT coHr = CoInitializeEx(nullptr, COINIT_APARTMENTTHREADED);
    bool comOwned = SUCCEEDED(coHr);

    if (!RunExtraction()) {
      if (comOwned) CoUninitialize();
      return;
    }

    if (comOwned) CoUninitialize();
  }

  void OnOK() override {
    Napi::Env env = Env();
    Napi::HandleScope scope(env);
    Napi::Buffer<uint8_t> buf = Napi::Buffer<uint8_t>::Copy(
        env, buffer_.empty() ? reinterpret_cast<uint8_t*>("") : buffer_.data(), buffer_.size());
    deferred_.Resolve(buf);
  }

  void OnError(const Napi::Error& e) override {
    deferred_.Reject(e.Value());
  }

 private:
  bool Fail(const char* message) {
    SetError(message);
    return false;
  }

  bool RunExtraction() {
    SHFILEINFOW sfi = {};
    if (!SHGetFileInfoW(path_.c_str(), 0, &sfi, sizeof(sfi), SHGFI_SYSICONINDEX)) {
      return Fail("SHGetFileInfo failed");
    }

    int shil = size_ >= 128 ? SHIL_JUMBO : SHIL_EXTRALARGE;
    IImageList* imageList = nullptr;
    HRESULT hr = SHGetImageList(shil, IID_IImageList, reinterpret_cast<void**>(&imageList));
    if (FAILED(hr) || !imageList) {
      return Fail("SHGetImageList failed");
    }

    HICON hIcon = nullptr;
    hr = imageList->GetIcon(sfi.iIcon, ILD_TRANSPARENT, &hIcon);
    imageList->Release();
    if (FAILED(hr) || !hIcon) {
      return Fail("IImageList::GetIcon failed");
    }

    Bitmap bitmap(hIcon);
    DestroyIcon(hIcon);
    if (bitmap.GetLastStatus() != Ok) {
      return Fail("Bitmap::FromHICON failed");
    }

    CLSID pngClsid;
    if (!GetEncoderClsid(L"image/png", &pngClsid)) {
      return Fail("PNG encoder not available");
    }

    IStream* stream = nullptr;
    if (FAILED(CreateStreamOnHGlobal(nullptr, TRUE, &stream)) || !stream) {
      return Fail("CreateStreamOnHGlobal failed");
    }

    Status saveStatus = bitmap.Save(stream, &pngClsid, nullptr);
    if (saveStatus != Ok) {
      stream->Release();
      return Fail("Bitmap::Save failed");
    }

    HGLOBAL hMem = nullptr;
    if (FAILED(GetHGlobalFromStream(stream, &hMem)) || !hMem) {
      stream->Release();
      return Fail("GetHGlobalFromStream failed");
    }

    SIZE_T dataSize = GlobalSize(hMem);
    void* data = GlobalLock(hMem);
    if (data && dataSize > 0) {
      buffer_.assign(static_cast<uint8_t*>(data), static_cast<uint8_t*>(data) + dataSize);
      GlobalUnlock(hMem);
    }
    stream->Release();
    return true;
  }

  std::wstring path_;
  int size_;
  std::vector<uint8_t> buffer_;
  Napi::Promise::Deferred deferred_;
};

Napi::Value GetJumboIcon(const Napi::CallbackInfo& info) {
  Napi::Env env = info.Env();
  if (info.Length() < 1 || !info[0].IsString()) {
    Napi::TypeError::New(env, "path (string) is required").ThrowAsJavaScriptException();
    return env.Undefined();
  }

  std::wstring wpath = Utf8ToWide(info[0].As<Napi::String>().Utf8Value());
  int size = 256;
  if (info.Length() > 1 && info[1].IsNumber()) {
    size = info[1].As<Napi::Number>().Int32Value();
  }

  auto* worker = new JumboIconWorker(env, std::move(wpath), size);
  Napi::Promise promise = worker->GetPromise();
  worker->Queue();
  return promise;
}

Napi::Object Init(Napi::Env env, Napi::Object exports) {
  static ULONG_PTR gdiplusToken = 0;
  static GdiplusStartupInput gdiplusInput;
  GdiplusStartup(&gdiplusToken, &gdiplusInput, nullptr);

  exports.Set("getJumboIcon", Napi::Function::New(env, GetJumboIcon));
  return exports;
}

}  // namespace

NODE_API_MODULE(folder_icon, Init)
