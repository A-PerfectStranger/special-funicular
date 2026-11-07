#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
: "${ANDROID_HOME:?Set ANDROID_HOME to an installed SDK (see README)}"
if [ -n "$(git status --porcelain --untracked-files=normal)" ]; then
  echo 'BLOCKED: commit source changes before building an artifact identified by SHA' >&2
  exit 2
fi
export GIT_SHA="${GIT_SHA:-$(git rev-parse HEAD)}"
export APP_ENV=development
npm run prebuild --workspace apps/mobile
mkdir -p work/artifacts
(
  cd apps/mobile/android
  # Standalone bundle, signed ONLY with the template's development/debug key.
  ./gradlew --no-daemon --max-workers=2 :app:assembleRelease -PreactNativeArchitectures=arm64-v8a
)
cp apps/mobile/android/app/build/outputs/apk/release/app-release.apk "work/artifacts/mobile-development-${GIT_SHA}.apk"
uv run python scripts/artifact_manifest.py "work/artifacts/mobile-development-${GIT_SHA}.apk" --kind development-apk --sha "$GIT_SHA"
