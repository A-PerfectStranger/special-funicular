#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
: "${ANDROID_HOME:?Set ANDROID_HOME to an installed SDK (see README)}"
export GIT_SHA="${GIT_SHA:-$(git rev-parse HEAD)}"
export APP_ENV=development
npm run prebuild --workspace apps/mobile
mkdir -p work/artifacts
(
  cd apps/mobile/android
  ./gradlew --no-daemon --max-workers=2 :app:assembleDebug -PreactNativeArchitectures=arm64-v8a
)
cp apps/mobile/android/app/build/outputs/apk/debug/app-debug.apk "work/artifacts/mobile-development-${GIT_SHA}.apk"
uv run python scripts/artifact_manifest.py "work/artifacts/mobile-development-${GIT_SHA}.apk" --kind development-apk --sha "$GIT_SHA"
