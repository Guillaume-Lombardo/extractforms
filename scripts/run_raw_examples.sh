#! /bin/zsh
: "${file1:=data/raw/form1.pdf}"
: "${outfile11:=results/extract/form1-1pass.json}"
: "${outfile12:=results/extract/form1-2pass.json}"
: "${file2:=data/raw/form2.pdf}"
: "${outfile21:=results/extract/form2-1pass.json}"
: "${outfile22:=results/extract/form2-2pass.json}"

uv run extractforms extract --input "$file1" --output "$outfile11" --passes 1
uv run extractforms extract --input "$file1" --output "$outfile12" --passes 2
uv run extractforms extract --input "$file2" --output "$outfile21" --passes 1
uv run extractforms extract --input "$file2" --output "$outfile22" --passes 2
