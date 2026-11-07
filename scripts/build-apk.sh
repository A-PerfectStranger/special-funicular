#!/usr/bin/env bash
set -euo pipefail
: "${RELEASE_SHA:=$(git rev-parse HEAD)}"
export RELEASE_SHA
if [[ ! "$RELEASE_SHA" =~ ^[a-f0-9]{40}$ ]]; then
  echo 'RELEASE_SHA debe ser un SHA completo' >&2
  exit 2
fi
repo_root="$(pwd)"
mkdir -p work
template="expo-template-bare-minimum-56.0.38.tgz"
curl -fsSL "https://registry.npmjs.org/expo-template-bare-minimum/-/$template" -o "work/$template"
echo "51716d0835cb0b3f9787fc72cb68758fa98bf3e09e0bdc05386eb89b74870cb0  work/$template" | sha256sum -c -
cd apps/mobile
npx --no-install expo prebuild --platform android --no-install --clean --template "../../work/$template"
# Expo firma release con la clave debug de ensayo. NUNCA distribuir como producción.
cd android
./gradlew :app:assembleRelease --no-daemon -PreactNativeArchitectures=arm64-v8a -Dorg.gradle.workers.max=2
mkdir -p "$repo_root/artifacts"
cp app/build/outputs/apk/release/app-release.apk "$repo_root/artifacts/retiro-synthetic-${RELEASE_SHA}.apk"
cd "$repo_root"
sha256sum "artifacts/retiro-synthetic-${RELEASE_SHA}.apk" > "artifacts/apk-${RELEASE_SHA}.sha256"
