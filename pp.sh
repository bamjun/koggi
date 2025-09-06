#!/usr/bin/env bash

### .env
### TestPyPI 환경
##TEST_PUBLISH_URL=https://test.pypi.org/legacy/
##TEST_CHECK_URL=https://test.pypi.org/simple/
##TEST_TOKEN=<test_token>
##
### Main PyPI 환경
##MAIN_PUBLISH_URL=https://upload.pypi.org/legacy/
##MAIN_CHECK_URL=https://pypi.org/simple/
##MAIN_TOKEN=<main_token>

# | 명령어                              | 설명                    |
# | -------------------------------- | --------------------- |
# | `./publish.sh`                   | main에 build + publish |
# | `./publish.sh test`              | test에 build + publish |
# | `./publish.sh main build-only`   | 빌드만                   |
# | `./publish.sh main -b`           | `build-only` 축약       |
# | `./publish.sh main publish-only` | 배포만 (dist 이용)         |
# | `./publish.sh main -p`           | `publish-only` 축약     |


set -euo pipefail

# --- .env 로드 ---
if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  . ./.env
  set +a
else
  echo "⚠️  .env not found. Proceeding without it."
fi

# --- 인자 파싱 ---
TARGET="${1:-main}"                  # test | main
RAW_MODE="${2:-all}"                 # build-only | -b | publish-only | -p | all

# --- 축약 인자 지원 ---
case "$RAW_MODE" in
  -b) MODE="build-only" ;;
  -p) MODE="publish-only" ;;
  build-only | publish-only | all) MODE="$RAW_MODE" ;;
  *) MODE="all" ;;  # default fallback
esac

# --- 함수: 빌드 ---
build() {
  echo "🛠  Building distributions (wheel + sdist)..."
  rm -rf dist build .eggs *.egg-info || true
  uv build
}

# --- 함수: 배포 ---
publish() {
  if [[ "$TARGET" == "test" ]]; then
    echo "🚀 Publishing to TestPyPI..."
    PUBLISH_URL="${TEST_PUBLISH_URL:-https://test.pypi.org/legacy/}"
    CHECK_URL="${TEST_CHECK_URL:-https://test.pypi.org/simple/}"
    TOKEN="${TEST_TOKEN:?TEST_TOKEN is not set}"
  else
    echo "🚀 Publishing to PyPI (main)..."
    PUBLISH_URL="${MAIN_PUBLISH_URL:-https://upload.pypi.org/legacy/}"
    CHECK_URL="${MAIN_CHECK_URL:-https://pypi.org/simple/}"
    TOKEN="${MAIN_TOKEN:?MAIN_TOKEN is not set}"
  fi

  if [[ ! -d dist ]] || [[ -z "$(ls -A dist)" ]]; then
    echo "❌ dist/ is missing or empty. Nothing to publish."
    echo "   👉 Run './publish.sh $TARGET build-only' first."
    exit 1
  fi

  uv publish -v \
    --publish-url "$PUBLISH_URL" \
    --check-url "$CHECK_URL" \
    --token "$TOKEN"

  echo "✅ Publish complete."
}

# --- 실행 흐름 ---
case "$MODE" in
  build-only)
    build
    echo "✅ Build complete. (MODE: build-only)"
    ;;
  publish-only)
    echo "ℹ️  Skipping build. Publishing existing dist/ only..."
    publish
    ;;
  all)
    build
    publish
    ;;
  *)
    echo "❌ Unknown mode: $MODE"
    exit 1
    ;;
esac
