#!/usr/bin/env bash
# Đo mở nguội + RAM của app ABook trên MỘT máy/máy ảo (docs/NATIVE_PHONE_UI.md §1), cho bản nào đang cài (WebView hay -PnativeUi).
#   scripts/native_perf.sh <serial> [lần=10] [chờ-giây=4]
# In: trung vị / nhỏ nhất / lớn nhất của `am start -W` TotalTime (mở nguội, force-stop trước mỗi lần), rồi PSS của tiến trình app sau khi mở
# + tổng PSS các tiến trình WebView (nếu có) để so công bằng. adb luôn qua cổng riêng 5038 (không đụng adb của Unity); không bao giờ tắt adb server.
set -u
SERIAL="${1:?dùng: native_perf.sh <serial> [lần] [chờ-giây]}"
RUNS="${2:-10}"
SETTLE="${3:-4}"
PKG="${ABOOK_PACKAGE:-com.ngdtuanh.abook}"
ADB_BIN="${ADB_BIN:-C:/Users/NGDtuanh/AppData/Local/Android/Sdk/platform-tools/adb.exe}"
export MSYS_NO_PATHCONV=1
adb() { "$ADB_BIN" -P 5038 -s "$SERIAL" "$@"; }

if ! adb get-state >/dev/null 2>&1; then
  echo "máy $SERIAL không trả lời (không mở máy ảo thay bạn)" >&2
  exit 2
fi
adb shell pm path "$PKG" >/dev/null 2>&1 || { echo "$PKG chưa cài trên $SERIAL" >&2; exit 3; }

launcher=$(adb shell cmd package resolve-activity --brief -c android.intent.category.LAUNCHER "$PKG" | tr -d '\r' | tail -1)
echo "máy=$SERIAL gói=$PKG màn mở=$launcher phiên bản=$(adb shell dumpsys package "$PKG" | tr -d '\r' | grep -m1 versionName | tr -d ' ')"

median() { sort -n | awk '{a[NR]=$1} END{ if(NR==0){print "n/a"} else if(NR%2){print a[(NR+1)/2]} else {print (a[NR/2]+a[NR/2+1])/2} }'; }

times=""
for i in $(seq 1 "$RUNS"); do
  adb shell am force-stop "$PKG" >/dev/null
  adb shell input keyevent KEYCODE_HOME >/dev/null 2>&1
  sleep 2
  total=$(adb shell am start -W -n "$launcher" | tr -d '\r' | awk -F': *' '/^TotalTime/{print $2}')
  echo "  lần $i: TotalTime=${total:-?} ms"
  [ -n "${total:-}" ] && times="$times$total"$'\n'
  sleep 1
done
printf '%s' "$times" | grep -c . | xargs -I{} echo "mở nguội: {} lần hợp lệ"
echo "mở nguội TotalTime trung vị = $(printf '%s' "$times" | grep . | median) ms (nhỏ nhất $(printf '%s' "$times" | grep . | sort -n | head -1), lớn nhất $(printf '%s' "$times" | grep . | sort -n | tail -1))"

# RAM sau lần mở cuối.
sleep "$SETTLE"
mem=$(adb shell dumpsys meminfo "$PKG" | tr -d '\r')
pss=$(printf '%s\n' "$mem" | awk '/TOTAL PSS:/{for(i=1;i<=NF;i++) if($i=="PSS:"){print $(i+1); exit}} /^ *TOTAL +[0-9]/{if(!f){print $2; f=1}}' | head -1)
echo "PSS tiến trình app = ${pss:-?} KB ($(( ${pss:-0} / 1024 )) MB)"
all=$(adb shell dumpsys meminfo | tr -d '\r')
web=$(printf '%s\n' "$all" | grep -iE '^ +[0-9,.]+K: .*(webview|chromium|sandboxed_process)' | sed -E 's/^ +([0-9,.]+)K:.*/\1/' | tr -d ',.' | awk '{s+=$1} END{print s+0}')
echo "PSS tiến trình WebView kèm theo = ${web:-0} KB ($(( ${web:-0} / 1024 )) MB)"
echo "TỔNG app + WebView = $(( ${pss:-0} + ${web:-0} )) KB ($(( (${pss:-0} + ${web:-0}) / 1024 )) MB)"
