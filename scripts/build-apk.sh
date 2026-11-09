#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
: "${ANDROID_HOME:?Set ANDROID_HOME to an installed SDK (see README)}"
if [ -n "$(git status --porcelain --untracked-files=normal)" ]; then
  echo 'BLOCKED: commit source changes before building an artifact identified by SHA' >&2
  exit 2
fi
export GIT_SHA="${GIT_SHA:-$(git rev-parse HEAD)}"
if [ "$GIT_SHA" != "$(git rev-parse HEAD)" ]; then
  echo 'BLOCKED: APK SHA must identify the checked-out source' >&2
  exit 2
fi
export APP_ENV="${APP_ENV:-development}"
case "$APP_ENV" in
  development|staging) ;;
  *) echo 'BLOCKED: debug signing is limited to development/staging' >&2; exit 2 ;;
esac
npm run prebuild --workspace apps/mobile
if [ -n "${RETIRO_GRADLE_ARCHIVE:-}" ]; then
  python3 scripts/gradle_archive.py use "$RETIRO_GRADLE_ARCHIVE"
fi
# Expo's transform cache can otherwise retain a previous environment's public values.
npm run mobile:export
mkdir -p work/artifacts
(
  cd apps/mobile/android
  # Standalone bundle, signed ONLY with the template's development/debug key.
  ./gradlew --no-daemon --rerun-tasks --max-workers=2 :app:assembleRelease -PreactNativeArchitectures=arm64-v8a
)
cp apps/mobile/android/app/build/outputs/apk/release/app-release.apk "work/artifacts/mobile-${APP_ENV}-${GIT_SHA}.apk"
uv run python scripts/verify_mobile_permissions.py "work/artifacts/mobile-${APP_ENV}-${GIT_SHA}.apk"
if [ "$APP_ENV" = staging ]; then
  uv run python scripts/verify_staging_apk.py "work/artifacts/mobile-${APP_ENV}-${GIT_SHA}.apk"
fi
uv run python scripts/artifact_manifest.py "work/artifacts/mobile-${APP_ENV}-${GIT_SHA}.apk" --kind "${APP_ENV}-apk" --sha "$GIT_SHA"
