SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_IMAGE="node:lts-bullseye-slim"
TARGET_IMAGE="desktop-commander-deeppresenter:0.1.0"

PULL_OPT=""
docker image inspect "$BASE_IMAGE" &>/dev/null && PULL_OPT="--pull=false"

docker build "$SCRIPT_DIR" -t "$TARGET_IMAGE" $PULL_OPT
