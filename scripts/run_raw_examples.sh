#!/usr/bin/env zsh
set -u

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="data/out"
RAW_DIR="data/raw"

files=("$RAW_DIR/form1.pdf" "$RAW_DIR/form2.pdf")
exit_code=0

for input_pdf in "${files[@]}"; do
  stem="${input_pdf:t:r}"
  output_json="$OUT_DIR/${stem}.json"

  echo "[run] extractforms extract --input $input_pdf --output $output_json --passes 2"
  if ! uv run extractforms extract --input "$input_pdf" --output "$output_json" --passes 2; then
    echo "[error] Extraction failed for $input_pdf"
    exit_code=1
    continue
  fi

  echo "[ok] Wrote $output_json"
done

exit $exit_code
