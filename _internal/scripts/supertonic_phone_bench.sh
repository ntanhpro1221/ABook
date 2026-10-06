#!/usr/bin/env bash
# Speed of the Supertonic voice on one phone or emulator (androidTest SupertonicBench.kt; results in docs/research/SUPERTONIC_PHONE.md).
#
#   MODEL=<folder with onnx/ + voice_styles/> scripts/supertonic_phone_bench.sh <adb serial> all [threads 1,2,4 passes 2]
#   or one step:  build | install | push | parity | speed | results | clean   (app [threads=1,2,4 ...] + wait-app: the speed run without installing)
#   parity: the model inputs (voice styles, character ids) and one chunk of audio against the desktop (tests/fixtures/readaloud/supertonic/supertonic.json)
#
# The bench is built and installed under its OWN package (BENCH_ID, default com.ngdtuanh.abook.stbench, + ".test"), never com.ngdtuanh.abook, so
# the listener's app and its books are never replaced or wiped; `clean` uninstalls only the bench packages and removes /data/local/tmp/stonic.
# Needs: JAVA_HOME (Android Studio jbr), ANDROID_HOME, adb on PATH or in %LOCALAPPDATA%/Android/Sdk/platform-tools, MODEL (e.g. the desktop module's
# <app data>/supertonic/model, or a download of Supertone/supertonic-3 at the commit of supertonic_module.SOURCE_REVISION), ORT_JNI (folder with
# <abi>/libonnxruntime*.so of onnxruntime-android 1.30.0, default D:/Novels/LLM_Train/ort_build/maven/aar/jni). node_modules of _internal/mobile
# must be installed (npm ci) for gradle to find Capacitor.
# Extra arguments become `-e name value` pairs of the instrumented run.
set -euo pipefail
SERIAL=${1:?usage: $0 <adb serial> all|build|install|push|speed|results|clean|app|wait-app [name value ...]}
STEP=${2:-all}
shift 2 || true
HERE=$(cd "$(dirname "$0")" && pwd)
ANDROID_DIR=$(cd "$HERE/../mobile/android" && (pwd -W 2>/dev/null || pwd))   # a Windows path: adb.exe does not map /d/...
FIXTURE=$(cd "$HERE/../tests/fixtures/readaloud/supertonic" && (pwd -W 2>/dev/null || pwd))/supertonic_bench.json
ADB=${ADB:-$(command -v adb || echo "$LOCALAPPDATA/Android/Sdk/platform-tools/adb.exe")}
ORT_JNI=${ORT_JNI:-D:/Novels/LLM_Train/ort_build/maven/aar/jni}
BENCH_ID=${BENCH_ID:-com.ngdtuanh.abook.stbench}
[ "$BENCH_ID" = com.ngdtuanh.abook ] && { echo "BENCH_ID must not be the real app" >&2; exit 2; }
REMOTE=/data/local/tmp/stonic
adb() { MSYS_NO_PATHCONV=1 "$ADB" -s "$SERIAL" "$@"; }

extras() { local out=(); while [ $# -ge 2 ]; do out+=(-e "$1" "$2"); shift 2; done; printf "%s " "${out[@]}"; }

build()   { (cd "$ANDROID_DIR" && ./gradlew :app:assembleDebug :app:assembleDebugAndroidTest -PbenchAppId="$BENCH_ID" -q); }
install() {
  local id; id=$(aapt_id "$ANDROID_DIR/app/build/outputs/apk/debug/app-debug.apk")
  [ "$id" = "$BENCH_ID" ] || { echo "app-debug.apk is $id, not $BENCH_ID - run the build step first" >&2; exit 2; }
  adb install -r -t "$ANDROID_DIR/app/build/outputs/apk/debug/app-debug.apk"
  adb install -r -t "$ANDROID_DIR/app/build/outputs/apk/androidTest/debug/app-debug-androidTest.apk"
}
# package name inside an APK (aapt2 of the newest build-tools)
aapt_id() { "$(ls -d "${ANDROID_HOME:-$LOCALAPPDATA/Android/Sdk}"/build-tools/* | sort -V | tail -1)/aapt2" dump packagename "$1" | tr -d '\r'; }
push() {
  local model=${MODEL:?set MODEL to the Supertonic model folder} abi; abi=$(adb shell getprop ro.product.cpu.abi | tr -d '\r')
  adb shell mkdir -p "$REMOTE/ort" "$REMOTE/model/onnx" "$REMOTE/model/voice_styles"
  adb push "$model"/onnx/duration_predictor.onnx "$model"/onnx/text_encoder.onnx "$model"/onnx/vector_estimator.onnx "$model"/onnx/vocoder.onnx \
    "$model"/onnx/tts.json "$model"/onnx/unicode_indexer.json "$REMOTE/model/onnx/"
  adb push "$model"/voice_styles/. "$REMOTE/model/voice_styles/"
  adb push "$ORT_JNI/$abi/libonnxruntime.so" "$ORT_JNI/$abi/libonnxruntime4j_jni.so" "$REMOTE/ort/"
  adb push "$FIXTURE" "$REMOTE/"
}
run()     { local method=$1; shift; adb shell am instrument -w -r $(extras "$@") -e class "vn.abook.player.SupertonicBenchTest#$method" "$BENCH_ID.test/androidx.test.runner.AndroidJUnitRunner"; }
results() { adb shell run-as "$BENCH_ID" cat files/stonic-results.jsonl; }
# No install: both APKs on the class path of app_process, run as the shell user; output to a log on the phone, `wait-app` follows it.
app() {
  adb shell mkdir -p "$REMOTE/apk"
  adb push "$ANDROID_DIR/app/build/outputs/apk/debug/app-debug.apk" "$REMOTE/apk/app.apk"
  adb push "$ANDROID_DIR/app/build/outputs/apk/androidTest/debug/app-debug-androidTest.apk" "$REMOTE/apk/test.apk"
  adb shell "rm -f $REMOTE/run.log; cd $REMOTE && CLASSPATH=$REMOTE/apk/app.apk:$REMOTE/apk/test.apk nohup app_process /system/bin vn.abook.player.SupertonicBenchMain $* > $REMOTE/run.log 2>&1 &"
}
wait_app() { until adb shell "grep -q STONIC_FINISHED $REMOTE/run.log || ! pidof app_process >/dev/null" 2>/dev/null; do sleep 15; done; adb shell tail -n 20 "$REMOTE/run.log"; }
clean()   { adb shell rm -rf "$REMOTE" || true; adb uninstall "$BENCH_ID.test" || true; adb uninstall "$BENCH_ID" || true; }

case "$STEP" in
  build) build ;; install) install ;; push) push ;; parity) run parity "$@" ;; speed) run speed "$@" ;; results) results ;; clean) clean ;;
  app) app "$@" ;; wait-app) wait_app ;; app-results) adb shell cat "$REMOTE/results.jsonl" ;;
  all) build; install; push; run parity; run speed "$@"; results; clean ;;
  *) echo "unknown step $STEP" >&2; exit 2 ;;
esac
