#!/usr/bin/env bash
# Run the phone's VieNeu bench (app/src/androidTest/.../VieneuBenchTest.kt) on one device or emulator, step by step.
#
#   1. desktop, once:  runtime/.venv/Scripts/python.exe scripts/vieneu_phone_bench_export.py --out $BENCH   (models + bundle, ~470 MB)
#   2. scripts/vieneu_phone_bench.sh <adb serial> all [instrumentation args]      build + install + push + check + speed + results + clean
#      or one step:  build | install | push | check | speed | sustain | results | clean  (app check|speed|sustain + wait-app: the same without installing)
#
# Needs: JAVA_HOME (Android Studio jbr), adb on PATH or in %LOCALAPPDATA%/Android/Sdk/platform-tools, BENCH (the export folder),
# ORT_JNI (folder with <abi>/libonnxruntime*.so from the onnxruntime-android AAR, default D:/Novels/LLM_Train/ort_build/maven/aar/jni).
# Touches only the test APK (com.ngdtuanh.abook + .test) and /data/local/tmp/vneu; `clean` uninstalls both and removes the pushed files.
# Extra arguments become `-e name value` pairs for the speed run, e.g.  threads 1,2,4,0  models turbo  passes 1  cooldown 60  headThreads 1
set -euo pipefail
SERIAL=${1:?usage: $0 <adb serial> all|build|install|push|check|speed|results|clean [name value ...]}
STEP=${2:-all}
shift 2 || true
HERE=$(cd "$(dirname "$0")" && pwd)
ANDROID_DIR=$(cd "$HERE/../mobile/android" && (pwd -W 2>/dev/null || pwd))   # a Windows path: adb.exe does not map /d/...
ADB=${ADB:-$(command -v adb || echo "$LOCALAPPDATA/Android/Sdk/platform-tools/adb.exe")}
BENCH=${BENCH:?set BENCH to the export folder}
ORT_JNI=${ORT_JNI:-D:/Novels/LLM_Train/ort_build/maven/aar/jni}
PKG=com.ngdtuanh.abook
REMOTE=/data/local/tmp/vneu   # the app copies it into its own files/ (it cannot load a .so from here); `clean` removes it
adb() { MSYS_NO_PATHCONV=1 "$ADB" -s "$SERIAL" "$@"; }

extras() { local out=(); while [ $# -ge 2 ]; do out+=(-e "$1" "$2"); shift 2; done; printf "%s " "${out[@]}"; }

build()   { (cd "$ANDROID_DIR" && ./gradlew --offline :app:assembleDebug :app:assembleDebugAndroidTest -q); }
install() { adb install -r -t "$ANDROID_DIR/app/build/outputs/apk/debug/app-debug.apk"; adb install -r -t "$ANDROID_DIR/app/build/outputs/apk/androidTest/debug/app-debug-androidTest.apk"; }
push() {
  local abi; abi=$(adb shell getprop ro.product.cpu.abi | tr -d '\r')
  adb shell mkdir -p "$REMOTE/ort"
  # PUSH: what to send (default: the phone's int8 Turbo + codec + Nano + bundle; "models/turbo_fp32 bundle_fp32" for the fp32 reference check)
  for part in ${PUSH:-models/turbo_int8 models/codec models/nano bundle}; do
    adb shell mkdir -p "$REMOTE/$(dirname "$part")"
    adb push "$BENCH/$part" "$REMOTE/$(dirname "$part")/"
  done
  adb push "$ORT_JNI/$abi/libonnxruntime.so" "$ORT_JNI/$abi/libonnxruntime4j_jni.so" "$REMOTE/ort/"
}
run() { # $1 = method, rest = extras
  local method=$1; shift
  adb shell am instrument -w -r $(extras "$@") -e class "vn.abook.player.VieneuBenchTest#$method" "$PKG.test/androidx.test.runner.AndroidJUnitRunner"
}
results() { adb shell run-as "$PKG" cat files/vneu-results.jsonl; }
# No install, no app: both APKs on the class path of app_process, run as the shell user. Needed on phones whose app freezer stops an instrumented
# app that is not in front (ColorOS: every thread of the test process sits in the frozen cgroup). Output goes to a log on the phone (so a dropped
# Wi-Fi link does not lose the run); `wait-app` follows it. Arguments after the mode are name=value pairs (threads=1,2,4,0 models=turbo ...).
app() { # $1 = check|speed, rest = name=value
  adb shell mkdir -p "$REMOTE/apk"
  adb push "$ANDROID_DIR/app/build/outputs/apk/debug/app-debug.apk" "$REMOTE/apk/app.apk"
  adb push "$ANDROID_DIR/app/build/outputs/apk/androidTest/debug/app-debug-androidTest.apk" "$REMOTE/apk/test.apk"
  adb shell "rm -f $REMOTE/run.log; cd $REMOTE && CLASSPATH=$REMOTE/apk/app.apk:$REMOTE/apk/test.apk nohup app_process /system/bin vn.abook.player.VieneuBenchMain $* > $REMOTE/run.log 2>&1 &"
}
wait_app() { until adb shell "grep -q VNEU_FINISHED $REMOTE/run.log || ! pidof app_process >/dev/null" 2>/dev/null; do sleep 15; done; adb shell tail -n 30 "$REMOTE/run.log"; }
clean()   { adb shell rm -rf "$REMOTE" /data/local/tmp/vneu_run.log || true; adb uninstall "$PKG.test" || true; adb uninstall "$PKG" || true; }

case "$STEP" in
  build) build ;; install) install ;; push) push ;;
  check) run theTurboLoopRepeatsTheDesktop "$@"; run theNanoLoopRepeatsTheDesktop "$@" ;;
  speed) run speed "$@" ;; sustain) run sustain "$@" ;; results) results ;; clean) clean ;;
  app) app "$@" ;; wait-app) wait_app ;; app-results) adb shell cat "$REMOTE/results.jsonl" ;;
  all) build; install; push; run theTurboLoopRepeatsTheDesktop "$@"; run theNanoLoopRepeatsTheDesktop "$@"; run speed "$@"; results; clean ;;
  *) echo "unknown step $STEP" >&2; exit 2 ;;
esac
