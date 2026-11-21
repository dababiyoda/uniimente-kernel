#!/bin/sh
# Build the two Ollama oracles freeze.py runs: Ollama's own manifest code at the two commits GREG models.
#   sh build_oracle.sh <out-dir>            -> <out-dir>/oracle-v040.bin, <out-dir>/oracle-main.bin
# Needs git, network access to github.com and Go 1.24 or later. Only manifest/, types/model/, internal/modelref/
# and envconfig/ are taken from Ollama (no test files), so the build needs no third-party module. envconfig is
# Ollama's own: Models() reads OLLAMA_MODELS through Var(), which trims spaces and then quotes, the way the server
# does (an earlier stub read os.Getenv raw and could not see a quoted or padded value).
set -eu
here=$(cd "$(dirname "$0")" && pwd)
out=$(mkdir -p "$1" && cd "$1" && pwd)
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
build() {    # <variant> <commit> <run path>
  src="$work/src-$1" mod="$work/mod-$1"
  git init -q "$src"
  git -C "$src" remote add origin https://github.com/ollama/ollama
  git -C "$src" fetch -q --depth 1 --filter=blob:none origin "$2"
  git -C "$src" sparse-checkout set --no-cone /manifest/ /types/model/ /internal/modelref/ /envconfig/
  git -C "$src" checkout -q FETCH_HEAD
  test "$(git -C "$src" rev-parse HEAD)" = "$2"
  mkdir -p "$mod/manifest" "$mod/types/model" "$mod/internal/modelref" "$mod/envconfig" "$mod/cmd/oracle"
  for d in manifest types/model internal/modelref envconfig; do
    find "$src/$d" -maxdepth 1 -name '*.go' ! -name '*_test.go' -exec cp {} "$mod/$d/" \;
  done
  printf 'module github.com/ollama/ollama\n\ngo 1.24\n' > "$mod/go.mod"
  sed -e "s/@VARIANT@/$1/g" -e "s|@MAIN_RUN_PATH@|$3|" "$here/oracle.go.in" > "$mod/cmd/oracle/main.go"
  (cd "$mod" && CGO_ENABLED=0 GOFLAGS=-mod=mod go build -trimpath -o "$out/oracle-$1.bin" ./cmd/oracle)
  echo "oracle-$1.bin: ollama $2"
}
build v040 0d0720e51fb2fd9aa58781c3d720c06d720c2e7b 'return nil, errors.New("unreachable")'
build main e9fde36d75fea66579d84099956ce1430792737a 'return manifest.FindNamedManifestForRunner(n, runner)'
