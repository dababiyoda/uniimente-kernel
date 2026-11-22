#!/usr/bin/env bash
# Use a pre-fetched, unmodified, pinned CuBFF checkout.
set -euo pipefail
cd -- "$(dirname -- "$0")"
upstream=$(realpath -- "${1:?pass the absolute path to the pinned CuBFF checkout}")
cases=${2:-10000000}
expected=f212e849027c98fcf4b242eccfb5fed435223e23
[[ "$(git -C "$upstream" rev-parse HEAD)" == "$expected" ]]
[[ -z "$(git -C "$upstream" status --porcelain --untracked-files=no)" ]]
out=$(mktemp -d)
trap 'rm -rf -- "$out"' EXIT
"${RUSTC:-rustc}" --edition=2021 --test ref_vm.rs -o "$out/unit"
"$out/unit"
"${RUSTC:-rustc}" --edition=2021 -O compare.rs -o "$out/compare"
read -r -a brotli_flags <<< "$(pkg-config --cflags --libs libbrotlienc libbrotlicommon)"
for variant in bff bff_noheads; do
  flags=()
  if [[ "$variant" == bff_noheads ]]; then flags+=(-DCUBFF_HEADLESS); fi
  "${CXX:-c++}" -std=c++17 -O3 -fopenmp "${flags[@]}" -I "$upstream" \
    cubff_pairs.cc "$upstream/common.cc" "${brotli_flags[@]}" -o "$out/oracle"
  printf '%s: ' "$variant"
  "$out/oracle" "$cases" | "$out/compare" "$variant" "$cases"
done
